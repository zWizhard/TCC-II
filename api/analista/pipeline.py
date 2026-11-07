"""Orquestracao do Analista IA: da pergunta a resposta tipada.

    recuperar_contexto -> (para aqui se ha recusa, ambiguidade ou termo nao mapeado: SEM LLM)
    -> LLM (JSON) -> QueryPlan -> validar_plano -> gerar_sql -> validar_sql -> execucao read-only
    -> analise deterministica -> spec de visualizacao -> explicacao

Decisoes registradas:
- O LLM so e chamado quando o contexto esta `pronta`, ha metrica servida na v1 e a dimensao de
  oferta foi dita pela pergunta. Tudo o mais e respondido pela camada semantica.
- Dimensao de oferta nao citada em pergunta sobre cursos vira pedido de esclarecimento: nao ha
  padrao (INDICADORES.md, regra transversal 2) e escolher seria chute.
- O SQL aparece na resposta (transparencia academica do TCC): e o SQL ja validado pelo AST, com
  marcadores `$nome`, e os parametros vinculados — ano, rotulos da propria base, limiar e limite.
  Nao ha credencial, caminho nem connection string em parte alguma deste fluxo.
- Log (`api.analista`): pergunta com %r, plano, SQL final, tempo, numero de linhas e desfecho.
- Plano invalido e uma RESPOSTA (`plano_invalido`, com os motivos), nao um erro HTTP. Resposta do
  modelo que nem e um QueryPlan e erro 502; modelo fora do ar, 503.
"""

import logging
import threading
import time
import unicodedata
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict

from api.analista.analise import (
    Analise,
    analisar,
    declarar_oferta,
    explicar,
    interpretar,
    numeros_do_resultado,
    resumir,
    verificar_texto,
)
from api.analista.llm import PROMPT_DE_SISTEMA, ProvedorLLM
from api.analista.plano import MAX_METRICAS, TETO_LINHAS, QueryPlan, interpretar_plano
from api.analista.sql import ColunaSaida, ConsultaGerada, gerar_sql
from api.analista.validacao import (
    PlanoInvalido,
    PlanoValidado,
    metricas_servidas,
    motivo_fora_da_v1,
    pendencias_do_contexto,
    validar_plano,
)
from api.analista.validador_sql import validar_sql
from api.analista.visualizacao import SpecVisualizacao, decidir_spec
from api.consultas import ANO_CENSO
from api.db import BaseAnalitica
from api.erros import ConsultaFalhou, ErroApi, ModeloOcupado, SqlRejeitado
from api.indicadores import Dimensao, Nivel, Recorte
from api.semantica import CAMADA, ContextoSemantico, recuperar_contexto
from api.semantica.recuperacao import MAX_PERGUNTA

log = logging.getLogger("api.analista")

Situacao = Literal[
    "respondida",
    "requer_esclarecimento",
    "recusada",
    "nao_mapeada",
    "nao_suportada",
    "pergunta_invalida",
    "plano_invalido",
]
_DIMENSAO_DE_OFERTA = "dimensao"
_VAGA_DO_MODELO = threading.BoundedSemaphore(1)


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Coluna(_Modelo):
    id: str
    nome: str
    papel: Literal["dimensao", "codigo", "metrica"]
    unidade: str | None = None


class Recusa(_Modelo):
    id: str
    nome: str
    motivo: str
    ficha: str | None = None
    alternativas: tuple[str, ...] = ()


class Motivo(_Modelo):
    codigo: str
    mensagem: str


class ConsultaExecutada(_Modelo):
    sql: str
    parametros: dict[str, Any]


class RespostaAnalista(_Modelo):
    situacao: Situacao
    pergunta: str
    ano_censo: str = ANO_CENSO
    mensagem: str
    # Preenchidos quando ha plano validado:
    interpretacao: str | None = None
    plano: QueryPlan | None = None
    recorte: Recorte | None = None
    nivel: Nivel | None = None
    dimensoes_de_oferta: tuple[Dimensao, ...] = ()
    dimensoes_de_oferta_rotulos: tuple[str, ...] = ()
    colunas: tuple[Coluna, ...] = ()
    linhas: tuple[tuple[Any, ...], ...] = ()
    truncado: bool = False
    analise: Analise | None = None
    visualizacao: SpecVisualizacao | None = None
    explicacao: str | None = None
    limitacoes: tuple[str, ...] = ()
    # Leitura adotada em cada ambiguidade que a pergunta disparou (sempre declarada).
    leituras_adotadas: tuple[str, ...] = ()
    terminologia: tuple[str, ...] = ()
    consulta: ConsultaExecutada | None = None
    # Preenchidos quando a pergunta nao segue adiante:
    esclarecimentos: tuple[str, ...] = ()
    recusas: tuple[Recusa, ...] = ()
    termos_nao_mapeados: tuple[str, ...] = ()
    motivos: tuple[Motivo, ...] = ()
    tempo_ms: float = 0.0


# --- desfechos sem LLM ----------------------------------------------------------------------------


def _esclarecimentos(contexto: ContextoSemantico) -> tuple[str, ...]:
    perguntas: list[str] = []
    for a in contexto.ambiguidades:
        if a.estado in ("pendente", "inviavel"):
            amb = CAMADA.ambiguidade(a.id)
            leituras = "; ".join(x.descricao for x in amb.leituras if x.servida)
            perguntas.append(f"{amb.pergunta} Leituras possíveis: {leituras}")
            if a.nota:
                perguntas.append(a.nota)
    perguntas += [*contexto.esclarecimentos, *contexto.incompatibilidades]
    return tuple(dict.fromkeys(perguntas))


def _sem_llm(contexto: ContextoSemantico) -> RespostaAnalista | None:
    """Resposta da propria camada semantica, quando a pergunta nao pode virar plano."""
    pergunta = contexto.pergunta
    s = contexto.situacao
    if s in ("vazia", "pergunta_longa"):
        mensagem = (
            "A pergunta está vazia."
            if s == "vazia"
            else f"A pergunta passa de {MAX_PERGUNTA} caracteres e não foi processada."
        )
        return RespostaAnalista(situacao="pergunta_invalida", pergunta=pergunta, mensagem=mensagem)
    if s == "recusada":
        recusas = tuple(
            Recusa(
                id=t.id,
                nome=t.nome,
                motivo=t.motivo,
                ficha=t.ficha,
                alternativas=tuple(str(a) for a in t.alternativas),
            )
            for t in (CAMADA.termo_vedado(r.id) for r in contexto.recusas)
        )
        return RespostaAnalista(
            situacao="recusada",
            pergunta=pergunta,
            mensagem="A pergunta pede algo que a plataforma não calcula com esta base.",
            recusas=recusas,
        )
    if s == "termo_nao_mapeado":
        return RespostaAnalista(
            situacao="nao_mapeada",
            pergunta=pergunta,
            mensagem=(
                "Há termos na pergunta que não correspondem a nenhuma métrica ou dimensão da "
                "base. Reformule com os termos do catálogo."
            ),
            termos_nao_mapeados=contexto.nao_reconhecidos,
        )
    if s == "requer_esclarecimento":
        return RespostaAnalista(
            situacao="requer_esclarecimento",
            pergunta=pergunta,
            mensagem="A pergunta admite mais de uma leitura, e a diferença muda o resultado.",
            esclarecimentos=_esclarecimentos(contexto),
        )
    if s == "lugar_nao_resolvido":
        return RespostaAnalista(
            situacao="requer_esclarecimento",
            pergunta=pergunta,
            mensagem="A pergunta cita um lugar pelo nome, e ele não foi identificado.",
            esclarecimentos=(
                "Município é identificado pelo código IBGE de 7 dígitos; UF, pela sigla em "
                "maiúsculas ou pelo nome do estado. Informe o lugar dessa forma.",
            ),
        )
    if s == "sem_metrica":
        return RespostaAnalista(
            situacao="requer_esclarecimento",
            pergunta=pergunta,
            mensagem="Não identifiquei o que medir na pergunta.",
            esclarecimentos=(
                "Diga a medida desejada: instituições, cursos, matrículas, ingressantes, "
                "concluintes, vagas, inscrições, docentes ou técnicos.",
            ),
        )
    return _fora_da_v1(contexto) or _oferta_nao_declarada(contexto) or _pendencias(contexto)


def _fora_da_v1(contexto: ContextoSemantico) -> RespostaAnalista | None:
    # Metrica fora da v1 PEDIDA pela pergunta nao e descartada em silencio: responder so com
    # a metrica-base seria responder outra pergunta. A composicao que a camada acrescenta por
    # conta de um 'por <dimensao>' pode ficar de fora: a quebra da metrica-base a substitui.
    motivos = [
        motivo
        for m in contexto.metricas
        if (motivo := motivo_fora_da_v1(CAMADA.metrica(m.id))) is not None
        and m.origem != "composicao"
    ]
    servidas = metricas_servidas(contexto)
    if not servidas and not motivos:
        motivos = [x for m in contexto.metricas if (x := motivo_fora_da_v1(CAMADA.metrica(m.id)))]
    if len({m.entidade for m in servidas}) > 1:
        motivos.append(
            "A pergunta reúne medidas da tabela de IES e da tabela de cursos; o Analista IA "
            "consulta uma tabela por vez. Pergunte por elas separadamente."
        )
    if len(servidas) > MAX_METRICAS:
        motivos.append(f"A pergunta reúne mais de {MAX_METRICAS} medidas.")
    if motivos:
        return RespostaAnalista(
            situacao="nao_suportada",
            pergunta=contexto.pergunta,
            mensagem="O Analista IA ainda não responde a este tipo de pergunta.",
            motivos=tuple(Motivo(codigo="nao_suportado", mensagem=x) for x in motivos),
        )
    fora = [
        d
        for d in (CAMADA.dimensao(x.id) for x in contexto.dimensoes)
        if d.tipo == "decomposicao" or (d.tipo == "categorica" and not d.valores_enumerados)
    ]
    # `municipio` nao e enumerado, mas e servido: como nivel e como filtro por codigo.
    fora = [d for d in fora if d.id != "municipio"]
    if fora:
        nomes = ", ".join(d.nome for d in fora)
        return RespostaAnalista(
            situacao="nao_suportada",
            pergunta=contexto.pergunta,
            mensagem="O Analista IA ainda não responde a este tipo de pergunta.",
            motivos=(
                Motivo(
                    codigo="nao_suportado",
                    mensagem=f"A quebra ou o filtro por {nomes} ainda não é feito pelo Analista IA.",
                ),
            ),
        )
    return None


def _pendencias(contexto: ContextoSemantico) -> RespostaAnalista | None:
    """Numero sem papel, ordem ou limiar indefinidos, dois niveis: pergunta-se, nao se chuta."""
    pendencias = pendencias_do_contexto(contexto)
    if not pendencias:
        return None
    return RespostaAnalista(
        situacao="requer_esclarecimento",
        pergunta=contexto.pergunta,
        mensagem="A pergunta deixa em aberto algo que muda o resultado.",
        esclarecimentos=tuple(pendencias),
    )


def _oferta_nao_declarada(contexto: ContextoSemantico) -> RespostaAnalista | None:
    de_cursos = [
        m
        for m in (CAMADA.metrica(x.id) for x in contexto.metricas)
        if m.exige_dimensao_oferta and motivo_fora_da_v1(m) is None
    ]
    oferta = contexto.dimensao(_DIMENSAO_DE_OFERTA)
    if not de_cursos or (oferta is not None and (oferta.valores or oferta.origem != "obrigatoria")):
        return None
    valores = CAMADA.dimensao(_DIMENSAO_DE_OFERTA).valores
    opcoes = "; ".join(v.rotulo for v in valores)
    return RespostaAnalista(
        situacao="requer_esclarecimento",
        pergunta=contexto.pergunta,
        mensagem="A pergunta não diz quais dimensões de oferta dos cursos devem entrar.",
        esclarecimentos=(
            "Toda medida de cursos declara a dimensão de oferta, e não há padrão: presencial e "
            f"EAD ficam em dimensões diferentes da base. Opções: {opcoes}. Diga, por exemplo, "
            "'presenciais', 'em polo EAD' ou 'por modalidade'.",
        ),
    )


# --- execucao -------------------------------------------------------------------------------------


def _rotulos_por_literal(consulta: ConsultaGerada, entidade: str) -> dict[int, dict[Any, str]]:
    """Indice da coluna -> {literal da base: rotulo}, para dimensoes sem coluna de rotulo."""
    mapas: dict[int, dict[Any, str]] = {}
    com_codigo = {c.referencia for c in consulta.colunas if c.papel == "codigo"}
    for i, c in enumerate(consulta.colunas):
        if c.papel != "dimensao" or c.referencia in com_codigo:
            continue
        d = CAMADA.dimensao(c.referencia)
        mapa = {
            lit.valor: v.rotulo for v in d.valores for lit in v.literais if lit.entidade == entidade
        }
        if mapa:
            mapas[i] = mapa
    return mapas


def _linhas(
    consulta: ConsultaGerada, brutas: list[tuple[Any, ...]], entidade: str
) -> list[list[Any]]:
    """Linhas prontas para JSON: rotulos da camada, codigos como texto e razoes arredondadas."""
    mapas = _rotulos_por_literal(consulta, entidade)
    saida: list[list[Any]] = []
    for bruta in brutas:
        linha: list[Any] = []
        for i, (celula, coluna) in enumerate(zip(bruta, consulta.colunas, strict=True)):
            if coluna.papel == "metrica":
                linha.append(round(celula, 4) if isinstance(celula, float) else celula)
            elif i in mapas:
                linha.append(mapas[i].get(celula, str(celula)))
            else:
                linha.append(str(celula))
        saida.append(linha)
    return saida


def _limitacoes(validado: PlanoValidado) -> tuple[str, ...]:
    plano = validado.plano
    notas: list[str] = []
    for m in validado.metricas:
        notas += [f"{m.nome} ({m.ficha}): {x}" for x in m.limitacoes]
    usadas = [*validado.agrupamentos, *(f.dimensao for f in plano.filters)]
    for id_ in dict.fromkeys(usadas):
        d = CAMADA.dimensao(id_)
        citados = {v for f in plano.filters if f.dimensao == id_ for v in f.valores}
        for v in d.valores:
            if str(v.id) in citados:
                notas += [f"{d.nome} = {v.rotulo}: {x}" for x in v.limitacoes]
    if plano.dimensions.nivel_territorial == Nivel.MUNICIPIO:
        notas.append("No nível municipal as linhas trazem o código IBGE de 7 dígitos, sem o nome.")
    return tuple(dict.fromkeys(notas))


def _leituras_adotadas(contexto: ContextoSemantico) -> tuple[str, ...]:
    saida: list[str] = []
    for a in contexto.ambiguidades:
        if a.leitura is None:
            continue
        amb = CAMADA.ambiguidade(a.id)
        descricao = next(x.descricao for x in amb.leituras if x.id == a.leitura)
        saida.append(f"{amb.nome}: {descricao}" + (f" ({a.nota})" if a.nota else ""))
    return tuple(saida)


def _numeros_do_plano(plano: QueryPlan) -> set[float]:
    numeros = {float(h.valor) for h in plano.having}
    for f in plano.filters:
        numeros.update(float(v) for v in f.valores if v.isdigit())
    return numeros


def _responder(
    pergunta: str, base: BaseAnalitica, provedor: ProvedorLLM, teto: int, registro: dict[str, Any]
) -> RespostaAnalista:
    if any(unicodedata.category(c).startswith("C") for c in pergunta):
        # Controle e formatacao Unicode (\x00, \n, RLO...) nao tem uso legitimo numa pergunta e
        # servem para esconder texto do leitor do log ou do prompt.
        return RespostaAnalista(
            situacao="pergunta_invalida",
            pergunta="".join(c for c in pergunta if not unicodedata.category(c).startswith("C")),
            mensagem=(
                "A pergunta contém caracteres de controle ou de formatação invisível (quebra de "
                "linha, tabulação…). Escreva-a em uma linha só, em texto simples."
            ),
        )
    contexto = recuperar_contexto(pergunta)
    registro["contexto"] = contexto.situacao
    resposta = _sem_llm(contexto)
    if resposta is not None:
        return resposta

    # O modelo atende uma pergunta por vez: a segunda nao entra em fila (ocuparia uma
    # thread do servidor por minutos), recebe 503 explicado.
    if not _VAGA_DO_MODELO.acquire(blocking=False):
        raise ModeloOcupado(
            "O modelo de linguagem está atendendo outra pergunta. Tente de novo em instantes."
        )
    try:
        bruto = provedor.gerar_json(
            PROMPT_DE_SISTEMA, contexto.para_prompt(), QueryPlan.model_json_schema()
        )
    finally:
        _VAGA_DO_MODELO.release()
    registro["resposta_do_modelo"] = bruto[:2000]
    plano = interpretar_plano(bruto)
    registro["plano"] = plano.model_dump_json()
    try:
        validado = validar_plano(plano, contexto, teto)
    except PlanoInvalido as exc:
        return RespostaAnalista(
            situacao="plano_invalido",
            pergunta=pergunta,
            mensagem=(
                "A interpretação da pergunta feita pelo modelo não passou na validação e não foi "
                "executada. Reformule a pergunta."
            ),
            plano=plano,
            motivos=tuple(Motivo(codigo=e.codigo, mensagem=e.mensagem) for e in exc.erros),
        )

    consulta = gerar_sql(validado)
    registro["sql"] = consulta.sql
    # +1: a linha extra que o gerador pede so para detectar truncamento.
    validar_sql(consulta.sql, consulta.params, TETO_LINHAS + 1, str(plano.entity))
    try:
        brutas = base.consultar(consulta.sql, consulta.params)
    except duckdb.Error as exc:
        # SQL do backend, validado, que o motor recusou: defeito interno. Detalhe so no log.
        log.error("motor recusou o SQL do analista: %s", type(exc).__name__)
        raise ConsultaFalhou(
            "A consulta gerada não pôde ser executada pela base analítica."
        ) from exc
    truncado = len(brutas) > consulta.limite
    linhas = _linhas(consulta, brutas[: consulta.limite], str(plano.entity))
    registro["linhas"] = len(linhas)

    analise = analisar(validado, consulta.colunas, linhas, truncado)
    resumo = resumir(validado, analise, len(linhas), truncado)
    termos_do_usuario = [a["termo_do_usuario"] for a in contexto.aliases_de_intencao()]
    permitidos = numeros_do_resultado(linhas, analise) | _numeros_do_plano(plano)
    problemas = verificar_texto(resumo, permitidos, termos_do_usuario)
    if problemas:  # nao deve ocorrer com texto do backend; se ocorrer, o resumo nao e publicado
        log.error("resumo deterministico reprovado na verificacao: %r", problemas)
        resumo = "Resultado: ver a tabela."
    return RespostaAnalista(
        situacao="respondida",
        pergunta=pergunta,
        mensagem="Consulta executada.",
        interpretacao=interpretar(validado),
        plano=plano,
        recorte=plano.dimensions.recorte,
        nivel=plano.dimensions.nivel_territorial,
        dimensoes_de_oferta=plano.dimensions.dimensao_de_oferta,
        dimensoes_de_oferta_rotulos=tuple(declarar_oferta(validado)),
        colunas=tuple(_coluna(c) for c in consulta.colunas),
        linhas=tuple(tuple(x) for x in linhas),
        truncado=truncado,
        analise=analise,
        visualizacao=decidir_spec(validado, consulta.colunas, len(linhas), truncado),
        explicacao=explicar(validado, resumo),
        limitacoes=_limitacoes(validado),
        leituras_adotadas=_leituras_adotadas(contexto),
        terminologia=tuple(
            dict.fromkeys(a["terminologia_obrigatoria"] for a in contexto.aliases_de_intencao())
        ),
        consulta=ConsultaExecutada(sql=consulta.sql, parametros=consulta.params),
    )


def _coluna(c: ColunaSaida) -> Coluna:
    return Coluna(id=c.id, nome=c.nome, papel=c.papel, unidade=c.unidade)


def responder(
    pergunta: str, base: BaseAnalitica, provedor: ProvedorLLM, teto: int = TETO_LINHAS
) -> RespostaAnalista:
    """Responde a uma pergunta. Erros de modelo, de tempo e de validacao AST sobem como ErroApi."""
    inicio = time.perf_counter()
    registro: dict[str, Any] = {}
    desfecho = "erro_interno"
    try:
        resposta = _responder(pergunta, base, provedor, teto, registro)
        desfecho = resposta.situacao
    except SqlRejeitado as exc:
        desfecho = f"{exc.codigo}:{exc.motivo}"
        log.error("sql barrado pelo validador AST: %s (%s)", exc.motivo, exc.detalhe)
        raise
    except ErroApi as exc:
        desfecho = exc.codigo
        raise
    finally:
        tempo_ms = (time.perf_counter() - inicio) * 1000
        # %r em tudo o que vem de fora (pergunta, texto do modelo): nada injeta linha no log.
        log.info(
            "pergunta=%r contexto=%s plano=%s sql=%r linhas=%s desfecho=%s tempo_ms=%.1f",
            pergunta[:MAX_PERGUNTA],
            registro.get("contexto"),
            registro.get("plano") or repr(registro.get("resposta_do_modelo")),
            registro.get("sql"),
            registro.get("linhas"),
            desfecho,
            tempo_ms,
        )
    return resposta.model_copy(update={"tempo_ms": round(tempo_ms, 1)})
