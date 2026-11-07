"""Validacao do QueryPlan contra a camada semantica E contra o contexto da pergunta.

O plano e saida de LLM: entrada nao confiavel. Aqui ele e conferido e, na menor duvida,
REJEITADO — nunca consertado. Duas frentes:

1. Camada: metrica, dimensao e valor existem; a dimensao e permitida para a metrica; nivel,
   recorte e dimensao de oferta sao os admitidos; uma tabela so; limite dentro do teto.
2. Contexto: o plano responde a pergunta que foi feita. Nao pode usar metrica que o contexto nao
   trouxe, trocar o recorte ou a dimensao de oferta, omitir ou inventar filtro, nem inventar
   limiar. E a defesa contra prompt injection: mesmo um modelo "convencido" pela pergunta nao
   consegue trocar a consulta.

Escopo da v1 (o resto e recusado com `nao_suportado`):
- metricas `direta` e razoes de uma so tabela com numerador e denominador fixos;
- uma tabela por consulta, sem JOIN;
- agrupamento por nivel territorial e por dimensao categorica enumerada.
Ficam fora: composicoes, decomposicoes por coluna (sexo, cor/raca, titulacao...), o rotulo CINE,
`matriculas_por_100_mil_habitantes` (exige JOIN com populacao) e `financiamento`/`reserva_vagas`
(exigem uma base declarada, que o plano nao representa).
"""

import re
from dataclasses import dataclass

from api.analista.plano import (
    LIMITE_PADRAO,
    TETO_LINHAS,
    Intencao,
    Operador,
    QueryPlan,
    TipoVisualizacao,
)
from api.indicadores import (
    REDE_DA_CATEGORIA,
    UF,
    UF_INFO,
    Categoria,
    Nivel,
)
from api.semantica import CAMADA, CamadaSemantica, ContextoSemantico
from api.semantica.modelos import DimensaoSemantica, Metrica

_MUNICIPIO = re.compile(r"[0-9]{7}")
_NIVEIS_AGRUPAVEIS = frozenset({str(Nivel.REGIAO), str(Nivel.UF), str(Nivel.MUNICIPIO)})
_DIMENSAO_DE_OFERTA = "dimensao"
# Cada filtro territorial so vale do seu proprio nivel para baixo (mesma regra de api/consultas).
_NIVEIS_DO_FILTRO: dict[str, tuple[Nivel, ...]] = {
    "regiao": (Nivel.REGIAO, Nivel.UF, Nivel.MUNICIPIO),
    "uf": (Nivel.UF, Nivel.MUNICIPIO),
    "municipio": (Nivel.MUNICIPIO,),
}
# So ha malha (e, portanto, mapa) para estes niveis.
_NIVEIS_COM_MAPA = frozenset({Nivel.UF, Nivel.MUNICIPIO})
# 'mais de'/'acima de'/'pelo menos' aceitam > e >=; 'menos de'/'abaixo de'/'no maximo', < e <=.
_OPERADORES_DO_SENTIDO: dict[str, frozenset[Operador]] = {
    "maior": frozenset({Operador.MAIOR, Operador.MAIOR_OU_IGUAL}),
    "menor": frozenset({Operador.MENOR, Operador.MENOR_OU_IGUAL}),
}


@dataclass(frozen=True)
class ErroDePlano:
    codigo: str
    mensagem: str


class PlanoInvalido(Exception):
    def __init__(self, erros: list[ErroDePlano]) -> None:
        super().__init__("; ".join(f"{e.codigo}: {e.mensagem}" for e in erros))
        self.erros = tuple(erros)

    def codigos(self) -> set[str]:
        return {e.codigo for e in self.erros}


@dataclass(frozen=True)
class PlanoValidado:
    """So `validar_plano` constroi: e o unico tipo que o gerador de SQL aceita."""

    plano: QueryPlan
    metricas: tuple[Metrica, ...]
    territorial: bool  # nivel abaixo do Brasil, ou filtro/quebra por dimensao territorial
    agrupamentos: tuple[str, ...]  # nivel territorial (se houver) + group_by, na ordem de saida


def motivo_fora_da_v1(metrica: Metrica) -> str | None:
    """Por que a metrica nao e servida pelo Analista IA nesta versao (None = e servida)."""
    if metrica.tipo == "composicao":
        return (
            f"'{metrica.nome}' ({metrica.ficha}) é uma composição; o Analista IA ainda não a "
            "calcula. Pergunte pela métrica-base agrupada pela dimensão."
        )
    if metrica.relacionamentos:
        return (
            f"'{metrica.nome}' ({metrica.ficha}) exige junção entre tabelas, que o Analista IA "
            "ainda não faz."
        )
    if metrica.tipo == "razao" and (len(metrica.razoes) != 1 or metrica.razoes[0].base is not None):
        return (
            f"'{metrica.nome}' ({metrica.ficha}) exige uma base declarada (matrículas, "
            "ingressantes ou concluintes), que o plano de consulta ainda não representa."
        )
    return None


def aditiva(metrica: Metrica) -> bool:
    """Os valores dos grupos podem ser somados (contagem distinta e razao nao podem)."""
    return metrica.tipo == "direta" and "DISTINCT" not in metrica.expressao


def metricas_servidas(
    contexto: ContextoSemantico, camada: CamadaSemantica | None = None
) -> list[Metrica]:
    """Metricas do contexto que a v1 serve: o plano tem de usar todas, e so elas."""
    camada = camada or CAMADA
    todas = [camada.metrica(m.id) for m in contexto.metricas]
    return [m for m in todas if motivo_fora_da_v1(m) is None]


def pendencias_do_contexto(
    contexto: ContextoSemantico, camada: CamadaSemantica | None = None
) -> list[str]:
    """O que a pergunta `pronta` ainda deixa em aberto e mudaria o resultado.

    Nada disto pode ser decidido pelo modelo: o pipeline pede esclarecimento ANTES de chama-lo, e
    `validar_plano` rejeita qualquer plano enquanto houver pendencia.
    """
    citados = contexto.numeros_citados
    limiares = [n for n in citados if n.papel == "limiar"]
    limites = [n for n in citados if n.papel == "limite"]
    servidas = metricas_servidas(contexto, camada)
    pendencias: list[str] = []
    sem_papel = [n.texto for n in citados if n.papel == "sem_papel"]
    if sem_papel:
        pendencias.append(
            f"A pergunta cita o número {', '.join(sem_papel[:5])} sem dizer o que ele é. Escreva-o "
            "como limiar ('mais de N', 'menos de N', 'pelo menos N'), como limite ('os N maiores', "
            "'top N') ou como código de município de 7 dígitos."
        )
    if len(limiares) > 1:
        pendencias.append(
            "A pergunta traz mais de um limiar; faixas ('entre A e B') ainda não são "
            "representadas. Use um limiar só."
        )
    if len(limites) > 1 or any(n.valor < 1 for n in limites):
        pendencias.append("A pergunta traz mais de um limite de linhas, ou um limite inválido.")
    if contexto.ordem == "conflito":
        pendencias.append(
            "A pergunta pede ao mesmo tempo os maiores e os menores. Qual das duas ordens?"
        )
    if limites and contexto.ordem is None:
        pendencias.append(
            f"A pergunta pede {limites[0].texto} linhas, mas não diz por qual ordem: as com mais "
            "ou as com menos?"
        )
    if len(servidas) > 1 and (limiares or contexto.ordem in ("desc", "asc")):
        nomes = ", ".join(m.nome for m in servidas)
        pendencias.append(
            f"A pergunta traz limiar ou ordem e mais de uma medida ({nomes}): a qual delas o "
            "limiar ou a ordem se aplica? Pergunte por uma medida de cada vez."
        )
    nivel = contexto.dimensao("nivel_territorial")
    if nivel is not None and len(nivel.valores) > 1:
        pendencias.append(
            f"A pergunta cita mais de um nível territorial ({', '.join(nivel.valores)}). Em qual "
            "deles o resultado deve ser agrupado?"
        )
    return pendencias


class _Validador:
    def __init__(
        self, plano: QueryPlan, contexto: ContextoSemantico, teto: int, camada: CamadaSemantica
    ) -> None:
        self.plano = plano
        self.contexto = contexto
        self.teto = min(teto, TETO_LINHAS)
        self.camada = camada
        self.erros: list[ErroDePlano] = []
        self.metricas: list[Metrica] = []
        self._dimensoes = {d.id: d for d in camada.dimensoes}
        self._metricas = {m.id: m for m in camada.metricas}

    def erro(self, codigo: str, mensagem: str) -> None:
        self.erros.append(ErroDePlano(codigo, mensagem))

    # --- camada -----------------------------------------------------------------------------------

    def _metricas_do_plano(self) -> None:
        p = self.plano
        if len(set(p.metrics)) != len(p.metrics):
            self.erro("metrica_repetida", "O plano repete uma métrica.")
        for id_ in dict.fromkeys(p.metrics):
            m = self._metricas.get(id_)
            if m is None:
                self.erro("metrica_inexistente", f"A métrica '{id_}' não existe no catálogo.")
                continue
            motivo = motivo_fora_da_v1(m)
            if motivo is not None:
                self.erro("nao_suportado", motivo)
                continue
            self.metricas.append(m)
            if m.entidade != p.entity:
                self.erro(
                    "entidade_incompativel",
                    f"'{m.nome}' é medida na tabela de {m.entidade}, não em '{p.entity}'; uma "
                    "consulta usa uma única tabela.",
                )
            if p.dimensions.recorte not in m.recortes:
                self.erro(
                    "recorte_invalido",
                    f"'{m.nome}' ({m.ficha}) só existe no recorte "
                    f"{[str(r) for r in m.recortes]} (ADR-0004); recebido "
                    f"'{p.dimensions.recorte}'.",
                )
            nivel = p.dimensions.nivel_territorial
            if nivel not in m.niveis:
                self.erro(
                    "nivel_nao_admitido",
                    f"'{m.nome}' ({m.ficha}) não é servida no nível '{nivel}'.",
                )
            elif nivel in m.niveis_bloqueados:
                self.erro(
                    "nivel_bloqueado",
                    f"'{m.nome}' ({m.ficha}) não é servida no nível '{nivel}' (bloqueio provisório).",
                )
        com_filtro = [m for m in self.metricas if m.filtro_obrigatorio is not None]
        if com_filtro and len(self.metricas) > 1:
            self.erro(
                "metrica_nao_combinavel",
                f"'{com_filtro[0].nome}' restringe as linhas contadas e não pode dividir a "
                "consulta com outra métrica.",
            )

    def _dimensao(self, id_: str, uso: str) -> DimensaoSemantica | None:
        d = self._dimensoes.get(id_)
        if d is None:
            self.erro("dimensao_inexistente", f"A dimensão '{id_}' ({uso}) não existe na camada.")
        return d

    def _permitida(self, d: DimensaoSemantica, uso: str) -> None:
        """A dimensao existe na tabela, e permitida para cada metrica e nao esta bloqueada."""
        p = self.plano
        if p.entity not in d.entidades:
            self.erro(
                "dimensao_nao_permitida", f"'{d.nome}' ({uso}) não existe na tabela de {p.entity}."
            )
            return
        for m in self.metricas:
            if d.id not in m.dimensoes_permitidas:
                self.erro(
                    "dimensao_nao_permitida",
                    f"'{d.nome}' ({uso}) não se aplica a '{m.nome}' ({m.ficha}).",
                )
        if p.dimensions.nivel_territorial in d.niveis_bloqueados:
            self.erro(
                "nivel_bloqueado",
                f"'{d.nome}' não é servida no nível '{p.dimensions.nivel_territorial}' "
                "(bloqueio provisório).",
            )

    def _agrupamentos(self) -> None:
        p = self.plano
        if len(set(p.group_by)) != len(p.group_by):
            self.erro("agrupamento_invalido", "O plano repete uma dimensão em group_by.")
        for id_ in dict.fromkeys(p.group_by):
            if id_ in _NIVEIS_AGRUPAVEIS:
                self.erro(
                    "agrupamento_invalido",
                    f"O agrupamento por '{id_}' declara-se em dimensions.nivel_territorial, não "
                    "em group_by.",
                )
                continue
            d = self._dimensao(id_, "group_by")
            if d is None:
                continue
            if d.tipo == "virtual":
                self.erro("agrupamento_invalido", f"'{d.nome}' não é uma coluna de agrupamento.")
            elif d.tipo == "decomposicao" or not d.valores_enumerados:
                self.erro(
                    "nao_suportado", f"A quebra por '{d.nome}' ainda não é feita pelo Analista IA."
                )
            elif not d.agrupavel:
                self.erro("dimensao_nao_agrupavel", f"'{d.nome}' não pode ser usada como quebra.")
            else:
                self._permitida(d, "group_by")
                if id_ == _DIMENSAO_DE_OFERTA and any(
                    m.dimensao_oferta_unica for m in self.metricas
                ):
                    self.erro(
                        "dimensao_nao_permitida",
                        "A métrica é calculada em uma única dimensão de oferta por vez e não "
                        "admite quebra por dimensão de oferta.",
                    )

    def _filtros(self) -> None:
        p = self.plano
        ids = [f.dimensao for f in p.filters]
        if len(set(ids)) != len(ids):
            self.erro("filtro_invalido", "O plano tem mais de um filtro na mesma dimensão.")
        for f in p.filters:
            d = self._dimensao(f.dimensao, "filtro")
            if d is None:
                continue
            if d.tipo == "virtual" or d.id == _DIMENSAO_DE_OFERTA:
                self.erro(
                    "filtro_invalido",
                    f"'{d.nome}' declara-se em dimensions, não como filtro.",
                )
                continue
            if d.tipo == "decomposicao" or not d.filtravel:
                self.erro("dimensao_nao_filtravel", f"'{d.nome}' não pode ser usada como filtro.")
                continue
            if len(set(f.valores)) != len(f.valores):
                self.erro("filtro_invalido", f"O filtro em '{d.nome}' repete um valor.")
            if d.id == "municipio":
                for v in f.valores:
                    if not _MUNICIPIO.fullmatch(v):
                        self.erro(
                            "municipio_mal_formado",
                            "Município é identificado pelo código IBGE de 7 dígitos.",
                        )
            elif not d.valores_enumerados:
                self.erro(
                    "nao_suportado", f"O filtro por '{d.nome}' ainda não é feito pelo Analista IA."
                )
                continue
            else:
                dominio = {str(v.id) for v in d.valores}
                for v in f.valores:
                    if v not in dominio:
                        self.erro(
                            "valor_fora_do_dominio",
                            f"'{d.nome}' não tem o valor informado; o domínio é {sorted(dominio)}.",
                        )
            self._permitida(d, "filtro")
            niveis = _NIVEIS_DO_FILTRO.get(d.id)
            if niveis is not None and p.dimensions.nivel_territorial not in niveis:
                self.erro(
                    "filtro_territorial_fora_do_nivel",
                    f"O filtro por '{d.nome}' só se aplica aos níveis {[str(n) for n in niveis]}; "
                    f"o plano declara o nível '{p.dimensions.nivel_territorial}'.",
                )
        self._filtros_contraditorios()

    def _valores(self, dimensao: str) -> set[str]:
        return {v for f in self.plano.filters if f.dimensao == dimensao for v in f.valores}

    def _filtros_contraditorios(self) -> None:
        regioes, ufs = self._valores("regiao"), self._valores("uf")
        siglas = {str(u) for u in UF}
        if regioes and any(u in siglas and str(UF_INFO[UF(u)][1]) not in regioes for u in ufs):
            self.erro("filtros_contraditorios", "Há UF filtrada fora da região filtrada.")
        redes, categorias = self._valores("rede"), self._valores("categoria")
        validas = {str(c) for c in Categoria}
        if redes and any(
            c in validas and str(REDE_DA_CATEGORIA[Categoria(c)]) not in redes for c in categorias
        ):
            self.erro(
                "filtros_contraditorios", "Há categoria administrativa fora da rede filtrada."
            )

    def _territorial(self) -> bool:
        p = self.plano
        usadas = [f.dimensao for f in p.filters] + list(p.group_by)
        return p.dimensions.nivel_territorial != Nivel.BRASIL or any(
            self._dimensoes[i].territorial for i in usadas if i in self._dimensoes
        )

    def _oferta(self, territorial: bool) -> None:
        p = self.plano
        oferta = p.dimensions.dimensao_de_oferta
        if p.entity == "ies":
            if oferta:
                self.erro(
                    "dimensao_de_oferta_indevida",
                    "A tabela de IES não tem dimensão de oferta: o campo deve ficar vazio.",
                )
            return
        if not oferta:
            self.erro(
                "dimensao_de_oferta_ausente",
                "Toda métrica de cursos declara as dimensões de oferta incluídas; não há padrão.",
            )
            return
        if len(set(oferta)) != len(oferta):
            self.erro("dimensao_de_oferta_repetida", "O plano repete uma dimensão de oferta.")
        for m in self.metricas:
            fora = [str(d) for d in oferta if d not in m.dimensoes_oferta]
            if fora:
                self.erro(
                    "dimensao_de_oferta_nao_admitida",
                    f"'{m.nome}' ({m.ficha}) não é definida nas dimensões de oferta {fora}.",
                )
            sem_territorio = [str(d) for d in oferta if d not in m.dimensoes_oferta_territoriais]
            if territorial and sem_territorio and not fora:
                self.erro(
                    "dimensao_de_oferta_sem_territorio",
                    f"'{m.nome}' ({m.ficha}) não existe por território nas dimensões de oferta "
                    f"{sem_territorio}.",
                )
            if m.dimensao_oferta_unica and len(set(oferta)) != 1:
                self.erro(
                    "dimensao_de_oferta_unica",
                    f"'{m.nome}' ({m.ficha}) é calculada em uma única dimensão de oferta por vez.",
                )

    def _demais(self, agrupamentos: tuple[str, ...]) -> None:
        p = self.plano
        for h in p.having:
            if h.metrica not in p.metrics:
                self.erro(
                    "having_fora_do_plano",
                    "O limiar refere-se a uma métrica que não está no plano.",
                )
        limitadas = [h.metrica for h in p.having]
        if len(set(limitadas)) != len(limitadas):
            self.erro("having_repetido", "O plano traz mais de um limiar para a mesma métrica.")
        if p.order_by and p.intent != Intencao.RANKING:
            self.erro("intencao_incoerente", "Só um ranking tem ordenação.")
        ordenaveis = set(p.metrics) | set(agrupamentos)
        chaves = [o.por for o in p.order_by]
        if len(set(chaves)) != len(chaves) or any(c not in ordenaveis for c in chaves):
            self.erro(
                "ordenacao_invalida",
                "A ordenação só pode usar, uma vez cada, métricas e agrupamentos do plano.",
            )
        if p.limit > self.teto:
            self.erro(
                "limite_acima_do_teto",
                f"O limite de linhas ({p.limit}) passa do teto de {self.teto}.",
            )
        if p.intent == Intencao.VALOR:
            if agrupamentos or p.having or p.order_by:
                self.erro(
                    "intencao_incoerente",
                    "Um valor único não tem agrupamento, limiar nem ordenação.",
                )
        elif not agrupamentos:
            self.erro("intencao_incoerente", f"A intenção '{p.intent}' exige um agrupamento.")
        elif p.intent == Intencao.RANKING and (
            not p.order_by or p.order_by[0].por not in p.metrics
        ):
            self.erro("intencao_incoerente", "Um ranking é ordenado por uma métrica do plano.")
        self._visualizacao(agrupamentos)

    def _visualizacao(self, agrupamentos: tuple[str, ...]) -> None:
        p = self.plano
        hint = p.visualization_hint
        if hint is None or hint == TipoVisualizacao.TABLE:
            return
        n, uma_metrica = len(agrupamentos), len(p.metrics) == 1
        motivo: str | None = None
        if hint == TipoVisualizacao.LINE:
            motivo = "a base tem um único ano (2024): não há série para um gráfico de linha"
        elif hint == TipoVisualizacao.KPI and n:
            motivo = "um KPI mostra um valor único, sem agrupamento"
        elif hint in (TipoVisualizacao.BAR, TipoVisualizacao.RANKING) and n != 1:
            motivo = "barras e ranking exigem exatamente um agrupamento"
        elif hint == TipoVisualizacao.COMPOSITION and not (
            n == 1 and uma_metrica and all(aditiva(m) for m in self.metricas)
        ):
            motivo = "composição exige um agrupamento e uma única métrica somável"
        elif hint == TipoVisualizacao.MAP and not (
            n == 1 and uma_metrica and p.dimensions.nivel_territorial in _NIVEIS_COM_MAPA
        ):
            motivo = "mapa exige uma métrica agrupada só por UF ou por município"
        elif hint == TipoVisualizacao.HEATMAP and not (n == 2 and uma_metrica):
            motivo = "heatmap exige dois agrupamentos e uma única métrica"
        if motivo is not None:
            self.erro("visualizacao_incompativel", f"Visualização '{hint}' incompatível: {motivo}.")

    # --- contexto ---------------------------------------------------------------------------------

    def _contexto(self, territorial: bool, agrupamentos: tuple[str, ...]) -> None:
        p, c = self.plano, self.contexto
        if not c.pode_prosseguir:
            self.erro(
                "contexto_nao_pronto",
                f"A pergunta não está pronta para consulta (situação '{c.situacao}').",
            )
            return
        for pendencia in pendencias_do_contexto(c, self.camada):
            self.erro("contexto_requer_esclarecimento", pendencia)
        # O plano usa TODAS as metricas servidas que a pergunta trouxe, e so elas.
        esperadas = {m.id for m in metricas_servidas(c, self.camada)}
        for id_ in p.metrics:
            if id_ not in esperadas:
                self.erro(
                    "metrica_fora_do_contexto", f"A métrica '{id_}' não foi pedida na pergunta."
                )
        for id_ in sorted(esperadas - set(p.metrics)):
            self.erro(
                "metrica_do_contexto_omitida",
                f"A pergunta pede '{self._metricas[id_].nome}', e o plano não a traz.",
            )
        recorte = c.ambiguidade("recorte")
        if (
            recorte is not None
            and recorte.leitura is not None
            and str(p.dimensions.recorte) != recorte.leitura
        ):
            self.erro(
                "recorte_diverge_do_contexto",
                f"A pergunta fixa o recorte '{recorte.leitura}'; o plano declara "
                f"'{p.dimensions.recorte}'.",
            )
        self._nivel_do_contexto()
        self._oferta_do_contexto(territorial)
        self._filtros_do_contexto()
        self._quebras_do_contexto()
        self._numeros_do_contexto()
        self._ordem_do_contexto(agrupamentos)

    def _quebras_do_contexto(self) -> None:
        """group_by e exatamente o conjunto de dimensoes citadas como quebra (sem valor)."""
        p, c = self.plano, self.contexto
        pedidas = {
            d.id
            for d in c.dimensoes
            if d.origem == "termo"
            and not d.valores
            and d.id not in _NIVEIS_AGRUPAVEIS
            and d.id in self._dimensoes
            and self._dimensoes[d.id].tipo == "categorica"
        }
        for id_ in p.group_by:
            if id_ not in pedidas:
                self.erro(
                    "agrupamento_fora_do_contexto",
                    f"A quebra por '{id_}' não foi pedida na pergunta.",
                )
        for id_ in sorted(pedidas - set(p.group_by)):
            self.erro(
                "agrupamento_do_contexto_omitido",
                f"A pergunta pede a quebra por '{self._dimensoes[id_].nome}', e o plano não a traz.",
            )

    def _nivel_do_contexto(self) -> None:
        p, c = self.plano, self.contexto
        nivel = str(p.dimensions.nivel_territorial)
        citado = c.dimensao("nivel_territorial")
        if citado is not None and citado.valores:
            esperados = set(citado.valores)  # mais de um: ja e pendencia de esclarecimento
        else:
            # Sem nivel citado, vale o do filtro territorial mais fino; sem filtro, o Brasil.
            filtradas = {f.dimensao for f in p.filters}
            esperados = {
                next(
                    (n for n in ("municipio", "uf", "regiao") if n in filtradas),
                    str(Nivel.BRASIL),
                )
            }
        if nivel not in esperados:
            self.erro(
                "nivel_diverge_do_contexto",
                f"A pergunta pede o nível {sorted(esperados)}; o plano declara '{nivel}'.",
            )

    def _oferta_do_contexto(self, territorial: bool) -> None:
        p, c = self.plano, self.contexto
        if p.entity != "cursos" or not self.metricas:
            return
        oferta = {str(d) for d in p.dimensions.dimensao_de_oferta}
        citada = c.dimensao(_DIMENSAO_DE_OFERTA)
        if citada is not None and citada.valores:
            if oferta != set(citada.valores):
                self.erro(
                    "dimensao_de_oferta_diverge_do_contexto",
                    f"A pergunta declara as dimensões de oferta {sorted(citada.valores)}; o plano "
                    f"declara {sorted(oferta)}.",
                )
            return
        # A pergunta nao escolheu dimensao: so e aceito mostrar TODAS as admitidas, uma por linha.
        completas = [
            {
                str(d)
                for d in (m.dimensoes_oferta_territoriais if territorial else m.dimensoes_oferta)
            }
            for m in self.metricas
        ]
        if _DIMENSAO_DE_OFERTA not in p.group_by or any(oferta != x for x in completas):
            self.erro(
                "dimensao_de_oferta_nao_declarada",
                "A pergunta não diz quais dimensões de oferta incluir (presencial, EAD em polo…) "
                "e não há padrão: sem isso, só é aceita a quebra por dimensão de oferta com todas "
                "as admitidas.",
            )

    def _filtros_do_contexto(self) -> None:
        p, c = self.plano, self.contexto
        codigos = {n.texto for n in c.numeros_citados if n.papel == "municipio"}
        filtradas = {f.dimensao for f in p.filters}
        for f in p.filters:
            if f.dimensao == "municipio":
                if any(v not in codigos for v in f.valores):
                    self.erro(
                        "filtro_fora_do_contexto",
                        "O código de município do filtro não aparece na pergunta como código.",
                    )
                continue
            citada = c.dimensao(f.dimensao)
            if citada is None or set(citada.valores) != set(f.valores):
                self.erro(
                    "filtro_diverge_do_contexto",
                    f"O filtro em '{f.dimensao}' não corresponde ao que a pergunta cita.",
                )
        for d in c.dimensoes:
            dim = self._dimensoes.get(d.id)
            if (
                dim is not None
                and dim.tipo != "virtual"
                and d.id != _DIMENSAO_DE_OFERTA
                and d.valores
                and d.id not in filtradas
            ):
                self.erro(
                    "filtro_do_contexto_omitido",
                    f"A pergunta restringe '{dim.nome}', e o plano não traz esse filtro.",
                )
        if codigos - self._valores("municipio"):
            self.erro(
                "filtro_do_contexto_omitido",
                "A pergunta cita um código de município, e o plano não filtra por ele.",
            )

    def _numeros_do_contexto(self) -> None:
        """Cada numero da pergunta tem UM papel, e o plano so pode usa-lo nesse papel.

        Limiar -> `having.valor`, com operador no sentido da pergunta; limite -> `limit`; codigo
        de municipio -> filtro (conferido em `_filtros_do_contexto`). Sem limite na pergunta, o
        `limit` e o padrao: o modelo nao escolhe quantas linhas mostrar.
        """
        p, c = self.plano, self.contexto
        limiares = [n for n in c.numeros_citados if n.papel == "limiar"]
        limites = [n for n in c.numeros_citados if n.papel == "limite"]
        pendentes = list(limiares)
        for h in p.having:
            casado = next((n for n in pendentes if n.valor == float(h.valor)), None)
            if casado is None:
                self.erro(
                    "having_fora_do_contexto",
                    "O limiar do plano não é um limiar da pergunta ('mais de N', 'menos de N'…).",
                )
                continue
            pendentes.remove(casado)
            if casado.sentido is None or h.operador not in _OPERADORES_DO_SENTIDO[casado.sentido]:
                self.erro(
                    "operador_diverge_do_contexto",
                    f"A pergunta pede valores no sentido '{casado.sentido}' que {casado.texto}; o "
                    f"plano usa o operador '{h.operador}'.",
                )
        for n in pendentes:
            self.erro(
                "limiar_do_contexto_omitido",
                f"A pergunta traz o limiar {n.texto}, e o plano não o aplica.",
            )
        if p.limit > self.teto:
            return  # ja apontado como limite_acima_do_teto
        esperado = int(limites[0].valor) if len(limites) == 1 else min(LIMITE_PADRAO, self.teto)
        if p.limit != esperado:
            self.erro(
                "limite_diverge_do_contexto",
                f"O limite de linhas tem de ser {esperado} "
                + ("(o N da pergunta)" if limites else "(o padrão: a pergunta não pede um N)")
                + f"; o plano declara {p.limit}.",
            )

    def _ordem_do_contexto(self, agrupamentos: tuple[str, ...]) -> None:
        """A direcao vem da pergunta ('com mais' = desc, 'menores' = asc); sem pedido, sem ordem."""
        p, c = self.plano, self.contexto
        if c.ordem in ("desc", "asc"):
            if not agrupamentos:
                return  # um valor unico nao tem ordem
            primeira = p.order_by[0] if p.order_by else None
            if primeira is None or primeira.por not in p.metrics or primeira.direcao != c.ordem:
                self.erro(
                    "ordenacao_diverge_do_contexto",
                    f"A pergunta pede ordem '{c.ordem}' pela métrica; o plano não ordena assim.",
                )
        elif p.order_by:
            self.erro(
                "ordenacao_diverge_do_contexto",
                "A pergunta não pede ordenação; o plano não pode escolher uma.",
            )

    # --- resultado --------------------------------------------------------------------------------

    def validar(self) -> PlanoValidado:
        p = self.plano
        self._metricas_do_plano()
        self._agrupamentos()
        self._filtros()
        territorial = self._territorial()
        self._oferta(territorial)
        nivel = p.dimensions.nivel_territorial
        agrupamentos = (*(() if nivel == Nivel.BRASIL else (str(nivel),)), *p.group_by)
        self._demais(agrupamentos)
        self._contexto(territorial, agrupamentos)
        if self.erros:
            raise PlanoInvalido(list({e: None for e in self.erros}))
        return PlanoValidado(p, tuple(self.metricas), territorial, agrupamentos)


def validar_plano(
    plano: QueryPlan,
    contexto: ContextoSemantico,
    teto: int = TETO_LINHAS,
    camada: CamadaSemantica | None = None,
) -> PlanoValidado:
    """Devolve o plano validado ou levanta `PlanoInvalido` com TODOS os problemas encontrados."""
    return _Validador(plano, contexto, teto, camada or CAMADA).validar()
