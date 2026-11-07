"""Comparacoes (Fase 11): de duas a cinco unidades territoriais de um mesmo nivel, lado a lado.

Mesmas garantias de `api/consultas.py`: SQL montado so com fragmentos fixos, valores de usuario
como parametros nomeados. Auditoria previa em scripts/analise/auditar_comparacoes.py (2026-10-07).

O que torna as colunas comparaveis:

- mesmas definicoes: toda unidade (e o Brasil, a coluna de referencia) passa pelas MESMAS consultas;
- mesmo periodo: Censo 2024 e populacao estimada de 2024;
- mesmo nivel: regiao com regiao, UF com UF, municipio com municipio — nunca niveis misturados;
- mesmos filtros: a rede, quando escolhida, vale para todas as colunas;
- mesmas dimensoes de oferta: presencial + polo EAD, as unicas com municipio, fixas.

A lista de indicadores e fechada e separada em dois grupos: valores absolutos, que medem sobretudo
o porte da unidade, e valores relativos, os unicos que comparam unidades de portes diferentes
(entre UFs, a ordem por matriculas e a ordem por matriculas por 100 mil habitantes tem correlacao
de postos de 0,06). As unidades voltam na ordem pedida: a API nao ordena nem classifica.

Nenhuma consulta junta IES com cursos, e nenhuma razao cruza as duas tabelas (IND-Q-03) nem os
dois recortes (IND-Q-06): cada linha declara o seu recorte, e a comparacao e sempre ENTRE
unidades, dentro de uma mesma linha. O que NAO e servido: IES x IES (ja ha a tabela de
instituicoes, e as metricas de uma IES vivem em dois grains), qualquer variacao temporal
(IND-Q-04) e IND-R-08 a IND-R-11 (dependem de base ou de dimensao unica; ficam em /razoes).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from api.consultas import (
    _COLUNA_MUNICIPIO,
    _COLUNA_REDE,
    _COLUNA_REGIAO,
    _COLUNA_UF,
    _COM_TERRITORIO,
    _NOTA_PUBLICA,
    _TABELA,
    ANO_CENSO,
)
from api.db import BaseAnalitica
from api.erros import ParametroInvalido
from api.indicadores import (
    CATALOGO,
    CODIGO_REGIAO,
    MATRICULAS_POR_HABITANTE,
    ROTULO_DIMENSAO,
    ROTULO_REDE,
    ROTULO_REGIAO,
    UF,
    UF_DO_CODIGO,
    UF_INFO,
    Dimensao,
    Nivel,
    NivelComparacao,
    Recorte,
    Rede,
    Regiao,
    TipoComparacao,
)
from api.mapas import _UNIDADE_REAL, ANO_POPULACAO, POPULACAO_PEQUENA, POR_HABITANTES, _n
from api.schemas import (
    IndicadorComparado,
    RespostaComparacao,
    UnidadeComparada,
    ValorComparado,
)

MIN_UNIDADES = 2
# Cabe as cinco regioes; acima disso a tela deixa de ser lida lado a lado.
MAX_UNIDADES = 5
# As unicas dimensoes com municipio, UF e regiao: fixas, iguais para todas as unidades.
DIMENSOES = (Dimensao.PRESENCIAL, Dimensao.EAD_POLO)
# So para o aviso de leitura — nada e suprimido. 1.271 das 3.551 unidades com oferta tem de 1 a
# 99 matriculas (2026-10-07); o piso de supressao continua pendente em INDICADORES.md.
BASE_PEQUENA = 100

_NOTA_RETRATO = (
    "Retrato de 2024: todas as unidades são medidas no mesmo ano, com as mesmas definições e os "
    "mesmos filtros. Não há série temporal — a comparação é entre unidades, nunca entre anos."
)
_NOTA_RECORTES = (
    "Cada linha declara o seu recorte: instituições e docentes são atribuídos à sede da IES; "
    "cursos e matrículas, ao local de oferta (inclusive polos EAD). Compare as unidades dentro de "
    "uma mesma linha; linhas de recortes diferentes não se dividem uma pela outra."
)
_NOTA_REDE_FILTRADA = (
    "Com a rede fixada, os valores absolutos e os numeradores contam só as instituições e as "
    "matrículas dessa rede; a população, no denominador de matrículas por 100 mil habitantes, "
    "continua sendo a total."
)
_NOTA_DIMENSOES = (
    "Cursos e matrículas usam só as dimensões de oferta com município — presencial e polo EAD "
    "—, e a contagem de cursos existe apenas no presencial. Por isso o Brasil desta tabela é "
    "menor que o total nacional da base: sem filtro de rede, ficam fora 2.580 de 10.227.266 "
    "matrículas (EAD no exterior e polo sem município) e os cursos EAD (34.479 de 45.776 são "
    "presenciais)."
)
_NOTA_COORTES = (
    "Ingressantes e concluintes de 2024 são turmas diferentes observadas no mesmo ano: aparecem "
    "lado a lado como contagens e não se dividem um pelo outro."
)
_NOTA_SEM_REGISTRO_NA_REDE = (
    "Com a rede fixada, célula vazia significa sem registro dessa rede na unidade — pode haver "
    "oferta da outra rede. Instituições aparecem como zero porque a tabela de IES é o universo: "
    "zero IES dessa rede com sede ali."
)
_NOTA_SEM_REGISTRO = (
    "Célula vazia não é zero: é unidade sem registro na base para aquela linha (sem curso "
    "presencial, sem oferta ou sem IES com sede no recorte) ou razão com denominador zero."
)
_NAO_SE_APLICA_REDE = "Não se aplica com a rede fixada: a participação seria 0% ou 100%."
_LIM_REDE = (
    "Depende fortemente da rede: sem fixá-la, a diferença entre unidades reflete em grande parte "
    "quanto da oferta de cada uma é pública ou privada."
)


@dataclass(frozen=True)
class _Medidas:
    """Somas de uma unidade. None = sem linha na base (ausencia), nunca zero."""

    populacao: int
    ies: int = 0  # a tabela de IES e o universo: sem linha = zero IES com sede, zero real
    docentes: int | None = None
    doutores: int | None = None
    cursos: int | None = None
    matriculas: int | None = None
    ingressantes: int | None = None
    concluintes: int | None = None
    privada: int | None = None
    ead: int | None = None


def _absoluto(valor: int | None) -> ValorComparado:
    return ValorComparado(valor=valor, numerador=None, denominador=None)


def _razao(numerador: int | None, denominador: int | None, fator: int) -> ValorComparado:
    """Denominador ausente ou zero = razao nao aplicavel (nula), nunca zero."""
    if numerador is None or not denominador:
        return ValorComparado(valor=None, numerador=numerador, denominador=denominador)
    return ValorComparado(
        valor=numerador / denominador * fator, numerador=numerador, denominador=denominador
    )


@dataclass(frozen=True)
class _Def:
    slug: str
    codigo: str
    nome: str
    unidade: str
    tipo: TipoComparacao
    recorte: Recorte
    dimensoes: tuple[Dimensao, ...]
    limitacoes: tuple[str, ...]
    medir: Callable[[_Medidas], ValorComparado]
    numerador_nome: str | None = None
    denominador_nome: str | None = None


def _direto(
    slug: str, medir: Callable[[_Medidas], int | None], dims: tuple[Dimensao, ...] = ()
) -> _Def:
    ind = CATALOGO[slug]
    return _Def(
        slug=ind.slug,
        codigo=ind.codigo,
        nome=ind.nome,
        unidade=ind.unidade,
        tipo=TipoComparacao.ABSOLUTO,
        recorte=ind.recorte,
        dimensoes=dims,
        limitacoes=ind.limitacoes,
        medir=lambda m: _absoluto(medir(m)),
    )


_SO_PRESENCIAL = (Dimensao.PRESENCIAL,)

# Ordem de exibicao. Ingressantes e concluintes aparecem so como valores absolutos: nenhuma razao
# entre eles e servida (IND-Q-01).
_DEFINICOES: tuple[_Def, ...] = (
    _direto("ies", lambda m: m.ies),
    # Sem IES com sede na unidade, docentes nao se aplicam (sao atribuidos a sede): nulo, nao zero.
    _direto("docentes", lambda m: m.docentes),
    _direto("cursos", lambda m: m.cursos, _SO_PRESENCIAL),
    _direto("matriculas", lambda m: m.matriculas, DIMENSOES),
    _direto("ingressantes", lambda m: m.ingressantes, DIMENSOES),
    _direto("concluintes", lambda m: m.concluintes, DIMENSOES),
    _Def(
        slug=MATRICULAS_POR_HABITANTE.slug,
        codigo=MATRICULAS_POR_HABITANTE.codigo,
        nome=MATRICULAS_POR_HABITANTE.nome,
        unidade=MATRICULAS_POR_HABITANTE.unidade,
        tipo=TipoComparacao.RELATIVO,
        recorte=Recorte.OFERTA,
        dimensoes=DIMENSOES,
        limitacoes=MATRICULAS_POR_HABITANTE.limitacoes,
        medir=lambda m: _razao(m.matriculas, m.populacao, POR_HABITANTES),
        numerador_nome="Matrículas",
        denominador_nome=f"População estimada (IBGE, {ANO_POPULACAO})",
    ),
    _Def(
        slug="participacao_privada",
        codigo="IND-R-03",
        nome="Participação da rede privada nas matrículas",
        unidade="%",
        tipo=TipoComparacao.RELATIVO,
        recorte=Recorte.OFERTA,
        dimensoes=DIMENSOES,
        limitacoes=(
            "Descreve a rede da IES ofertante, não o financiamento do estudante.",
            "O complemento é a rede Pública, que inclui as 28 IES de categoria Especial.",
        ),
        medir=lambda m: _razao(m.privada, m.matriculas, 100),
        numerador_nome="Matrículas na rede privada",
        denominador_nome="Matrículas",
    ),
    _Def(
        slug="participacao_ead",
        codigo="IND-R-04",
        nome="Participação da educação a distância nas matrículas",
        unidade="%",
        tipo=TipoComparacao.RELATIVO,
        recorte=Recorte.OFERTA,
        dimensoes=DIMENSOES,
        limitacoes=(
            "Medida por tp_dimensao: matrículas em polo EAD sobre matrículas presenciais e em "
            "polo EAD. Ficam fora os registros sem município: no país, 2.539 matrículas de EAD "
            "no exterior e 41 de polo sem município identificado.",
            "A matrícula EAD é contada no município do polo, não no de residência do estudante.",
            _LIM_REDE,
        ),
        medir=lambda m: _razao(m.ead, m.matriculas, 100),
        numerador_nome="Matrículas em polo EAD",
        denominador_nome="Matrículas",
    ),
    _Def(
        slug="docentes_doutorado",
        codigo="IND-R-12",
        nome="Docentes com doutorado",
        unidade="%",
        tipo=TipoComparacao.RELATIVO,
        recorte=Recorte.SEDE,
        dimensoes=(),
        limitacoes=(
            "Titulação descreve o corpo docente; não é medida de qualidade de ensino.",
            "Docentes são atribuídos à sede da IES, não ao local de atuação.",
            _LIM_REDE,
        ),
        medir=lambda m: _razao(m.doutores, m.docentes, 100),
        numerador_nome="Docentes com doutorado",
        denominador_nome="Docentes em exercício",
    ),
)


def _chaves(nivel: NivelComparacao, unidades: list[str]) -> list[str]:
    """Valida as unidades contra o nivel e devolve a chave de cada uma nas tabelas do Censo."""
    if not MIN_UNIDADES <= len(unidades) <= MAX_UNIDADES:
        raise ParametroInvalido(
            f"A comparação recebe de {MIN_UNIDADES} a {MAX_UNIDADES} unidades do mesmo nível."
        )
    if len(set(unidades)) != len(unidades):
        raise ParametroInvalido("A mesma unidade foi informada mais de uma vez.")
    try:
        if nivel == NivelComparacao.REGIAO:
            return [CODIGO_REGIAO[Regiao(u)] for u in unidades]
        if nivel == NivelComparacao.UF:
            return [str(UF(u)) for u in unidades]
    except ValueError:
        # O valor recebido nao e ecoado.
        raise ParametroInvalido(
            f"Unidade inválida para o nível '{nivel}': use "
            + ("o slug da região." if nivel == NivelComparacao.REGIAO else "a sigla da UF.")
        ) from None
    if any(len(u) != 7 or not u.isdigit() for u in unidades):
        raise ParametroInvalido("No nível 'municipio', cada unidade é um código IBGE de 7 dígitos.")
    return unidades


def _cursos(
    base: BaseAnalitica, coluna: str | None, chaves: list[str], rede: Rede | None
) -> dict[str, tuple[Any, ...]]:
    """Somas de `cursos` por unidade; com `coluna` nula, a linha unica do Brasil."""
    condicoes = ["nu_ano_censo = $ano", "list_contains($dims, tp_dimensao)", _COM_TERRITORIO]
    params: dict[str, Any] = {
        "ano": ANO_CENSO,
        "dims": [ROTULO_DIMENSAO[d] for d in DIMENSOES],
        "presencial": ROTULO_DIMENSAO[Dimensao.PRESENCIAL],
        "polo": ROTULO_DIMENSAO[Dimensao.EAD_POLO],
        "privada": ROTULO_REDE[Rede.PRIVADA],
    }
    if rede is not None:
        condicoes.append(f"{_COLUNA_REDE['cursos']} = $rede")
        params["rede"] = ROTULO_REDE[rede]
    if coluna is not None:
        condicoes.append(f"list_contains($chaves, {coluna})")
        params["chaves"] = chaves
    # Contagem de cursos = SUM(qt_curso), que so existe territorializada no presencial. O FILTER
    # sem linha devolve NULL: unidade so com polo EAD nao tem "zero cursos", tem ausencia.
    rows = base.consultar(
        f"""
        SELECT {coluna or "'BR'"} AS chave, COUNT(*),
               CAST(SUM(qt_curso) FILTER (WHERE tp_dimensao = $presencial) AS BIGINT),
               CAST(SUM(qt_mat) AS BIGINT), CAST(SUM(qt_ing) AS BIGINT),
               CAST(SUM(qt_conc) AS BIGINT),
               CAST(coalesce(SUM(qt_mat) FILTER (WHERE tp_rede = $privada), 0) AS BIGINT),
               CAST(coalesce(SUM(qt_mat) FILTER (WHERE tp_dimensao = $polo), 0) AS BIGINT)
        FROM {_TABELA["cursos"]}
        WHERE {" AND ".join(condicoes)}
        {"GROUP BY 1" if coluna is not None else ""}
        """,
        params,
    )
    return {r[0]: r[2:] for r in rows if r[1]}


def _ies(
    base: BaseAnalitica, coluna: str | None, chaves: list[str], rede: Rede | None
) -> dict[str, tuple[Any, ...]]:
    """Contagem e docentes na tabela de IES (sede), nunca apos JOIN com cursos."""
    condicoes = ["nu_ano_censo = $ano"]
    params: dict[str, Any] = {"ano": ANO_CENSO}
    if rede is not None:
        condicoes.append(f"{_COLUNA_REDE['ies']} = $rede")
        params["rede"] = ROTULO_REDE[rede]
    if coluna is not None:
        condicoes.append(f"list_contains($chaves, {coluna})")
        params["chaves"] = chaves
    rows = base.consultar(
        f"""
        SELECT {coluna or "'BR'"} AS chave, COUNT(*), CAST(SUM(qt_doc_total) AS BIGINT),
               CAST(SUM(qt_doc_ex_dout) AS BIGINT)
        FROM {_TABELA["ies"]}
        WHERE {" AND ".join(condicoes)}
        {"GROUP BY 1" if coluna is not None else ""}
        """,
        params,
    )
    return {r[0]: r[1:] for r in rows if r[1]}


def _populacao_por_uf(base: BaseAnalitica) -> dict[UF, int]:
    """Populacao de 2024 reagregada por UF: todas as unidades reais, com ou sem oferta."""
    rows = base.consultar(
        f"""
        SELECT m.cd_uf, CAST(SUM(p.populacao) AS BIGINT)
        FROM municipio m
        JOIN ibge_populacao_estimada p
          ON p.cod_municipio = m.codigo_municipio AND p.ano = $ano_populacao
        WHERE {_UNIDADE_REAL}
        GROUP BY 1
        """,
        {"ano_populacao": ANO_POPULACAO},
    )
    return {UF_DO_CODIGO[r[0]]: int(r[1]) for r in rows}


def _municipios(base: BaseAnalitica, codigos: list[str]) -> dict[str, tuple[str, int]]:
    """(nome, populacao) das unidades reais de `municipio`; a ponte de 6 digitos e 1:1 em 2024."""
    rows = base.consultar(
        f"""
        SELECT m.codigo_municipio_dv, m.nome_municipio, CAST(p.populacao AS BIGINT)
        FROM municipio m
        JOIN ibge_populacao_estimada p
          ON p.cod_municipio = m.codigo_municipio AND p.ano = $ano_populacao
        WHERE {_UNIDADE_REAL} AND list_contains($codigos, m.codigo_municipio_dv)
        """,
        {"ano_populacao": ANO_POPULACAO, "codigos": codigos},
    )
    return {r[0]: (r[1], int(r[2])) for r in rows}


def _medidas(
    populacao: int, cursos: tuple[Any, ...] | None, ies: tuple[Any, ...] | None
) -> _Medidas:
    c = cursos or (None,) * 6
    i = ies or (0, None, None)
    return _Medidas(
        populacao=populacao,
        ies=i[0],
        docentes=i[1],
        doutores=i[2],
        cursos=c[0],
        matriculas=c[1],
        ingressantes=c[2],
        concluintes=c[3],
        privada=c[4],
        ead=c[5],
    )


def consultar_comparacao(
    base: BaseAnalitica,
    nivel: NivelComparacao,
    unidades: list[str],
    rede: Rede | None = None,
) -> RespostaComparacao:
    """As unidades pedidas e o Brasil, medidos pelas mesmas consultas, na ordem pedida."""
    chaves = _chaves(nivel, unidades)
    nivel_censo = Nivel(nivel.value)
    coluna = {
        NivelComparacao.REGIAO: _COLUNA_REGIAO,
        NivelComparacao.UF: _COLUNA_UF,
        NivelComparacao.MUNICIPIO: _COLUNA_MUNICIPIO,
    }[nivel]

    pop_uf = _populacao_por_uf(base)
    cabecalho: list[tuple[str, str | None, int]]  # (nome, uf, populacao), na ordem pedida
    if nivel == NivelComparacao.REGIAO:
        cabecalho = [
            (
                ROTULO_REGIAO[Regiao(u)],
                None,
                sum(p for uf, p in pop_uf.items() if UF_INFO[uf][1] == Regiao(u)),
            )
            for u in unidades
        ]
    elif nivel == NivelComparacao.UF:
        cabecalho = [(UF_INFO[UF(u)][0], u, pop_uf[UF(u)]) for u in unidades]
    else:
        reais = _municipios(base, chaves)
        if len(reais) != len(chaves):
            # Codigo bem formado que nao e unidade real (inexistente ou sentinela de `municipio`).
            raise ParametroInvalido(
                "Ao menos um código de município não é uma unidade territorial da base."
            )
        cabecalho = [(reais[u][0], str(UF_DO_CODIGO[u[:2]]), reais[u][1]) for u in unidades]

    cursos = _cursos(base, coluna["cursos"], chaves, rede)
    ies = _ies(base, coluna["ies"], chaves, rede)
    medidas = [
        _medidas(pop, cursos.get(chave), ies.get(chave))
        for chave, (_, _, pop) in zip(chaves, cabecalho, strict=True)
    ]
    brasil = _medidas(
        sum(pop_uf.values()),
        _cursos(base, None, [], rede).get("BR"),
        _ies(base, None, [], rede).get("BR"),
    )

    indicadores = []
    for d in _DEFINICOES:
        fora = _NAO_SE_APLICA_REDE if d.slug == "participacao_privada" and rede else None
        vazio = ValorComparado(valor=None, numerador=None, denominador=None)
        indicadores.append(
            IndicadorComparado(
                slug=d.slug,
                codigo=d.codigo,
                nome=d.nome,
                unidade=d.unidade,
                tipo=d.tipo,
                recorte=d.recorte,
                dimensoes=[ROTULO_DIMENSAO[x] for x in d.dimensoes],
                numerador_nome=d.numerador_nome,
                denominador_nome=d.denominador_nome,
                limitacoes=list(d.limitacoes),
                nao_se_aplica=fora,
                valores=[vazio if fora else d.medir(m) for m in medidas],
                referencia=vazio if fora else d.medir(brasil),
            )
        )

    populacoes = [m.populacao for m in medidas]
    pequenas = sum(1 for p in populacoes if p < POPULACAO_PEQUENA)
    base_pequena = sum(
        1 for m in medidas if m.matriculas is not None and 0 < m.matriculas < BASE_PEQUENA
    )
    poucos_docentes = sum(
        1 for m in medidas if m.docentes is not None and 0 < m.docentes < BASE_PEQUENA
    )
    vazia = any(v.valor is None for i in indicadores if not i.nao_se_aplica for v in i.valores)
    notas = [
        _NOTA_RETRATO,
        (
            f"A maior unidade selecionada tem {_n(round(max(populacoes) / min(populacoes)))} vezes "
            "a população da menor: os valores absolutos medem sobretudo o porte. Para comparar "
            "unidades de portes diferentes, leia os valores relativos."
            if max(populacoes) >= 2 * min(populacoes)
            else "Os valores absolutos acompanham o porte da unidade; os relativos descontam-no."
        ),
        _NOTA_RECORTES,
        _NOTA_DIMENSOES,
        _NOTA_COORTES,
        *([_NOTA_SEM_REGISTRO] if vazia else []),
        *([_NOTA_SEM_REGISTRO_NA_REDE] if vazia and rede else []),
        *(
            [
                f"Unidades selecionadas com menos de {_n(POPULACAO_PEQUENA)} habitantes: "
                f"{_n(pequenas)}. Nelas, poucas matrículas deslocam muito a razão por habitante."
            ]
            if pequenas
            else []
        ),
        *(
            [
                f"Unidades selecionadas com menos de {_n(BASE_PEQUENA)} matrículas: "
                f"{_n(base_pequena)}. Nelas, as participações percentuais mudam muito com poucos "
                "registros: leia o numerador e o denominador."
            ]
            if base_pequena
            else []
        ),
        *(
            [
                f"Unidades selecionadas com menos de {_n(BASE_PEQUENA)} docentes: "
                f"{_n(poucos_docentes)}. Nelas, a proporção de doutores muda muito com poucos "
                "docentes: leia o numerador e o denominador."
            ]
            if poucos_docentes
            else []
        ),
        *([_NOTA_REDE_FILTRADA] if rede else []),
        *([_NOTA_PUBLICA] if rede == Rede.PUBLICA else []),
    ]
    return RespostaComparacao(
        ano_censo=ANO_CENSO,
        ano_populacao=ANO_POPULACAO,
        nivel=nivel_censo,
        rede=ROTULO_REDE[rede] if rede else None,
        dimensoes=[ROTULO_DIMENSAO[d] for d in DIMENSOES],
        unidades=[
            UnidadeComparada(codigo=u, nome=nome, uf=uf, populacao=pop)
            for u, (nome, uf, pop) in zip(unidades, cabecalho, strict=True)
        ],
        referencia=UnidadeComparada(
            codigo="BR", nome="Brasil", uf=None, populacao=brasil.populacao
        ),
        indicadores=indicadores,
        notas=notas,
    )
