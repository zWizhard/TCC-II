"""Mapa (Fase 10): coropletico de IND-R-01 e a malha territorial que o desenha.

Mesmas garantias de `api/consultas.py`: SQL montado so com fragmentos fixos, valores de usuario
como parametros nomeados. Auditoria previa em scripts/analise/auditar_mapas.py (2026-10-07).

Pontos e heatmap NAO passam por aqui: usam `/api/v1/indicadores/{slug}?nivel=municipio`, que ja
devolve uma linha por municipio com a coordenada de `municipio`.

O coropletico e o unico lugar da API em que o Censo encontra a populacao:

    cursos --pre-agrega por co_municipio--> municipio --codigo de 6 digitos--> populacao 2024

- `municipio` e a ponte obrigatoria: o Censo usa 7 digitos e a populacao 6;
- a populacao e filtrada por ano: so 2024 (e 2022+) nao tem pares duplicados e divergentes;
- o universo sao as 5.571 unidades reais de `municipio` (sem as 28 sentinelas), e NAO as
  unidades com oferta: quem nao tem linha em `cursos` sai com numerador nulo (ausencia), e a sua
  populacao continua no denominador de qualquer nivel acima (ficha de IND-R-01).
"""

from bisect import bisect_left
from pathlib import Path

from api.analises import _filtros_resposta
from api.consultas import (
    _COM_TERRITORIO,
    _NOTA_PUBLICA,
    _TABELA,
    ANO_CENSO,
    FiltrosConsulta,
    _sem_territorio,
    _where,
    info,
    validar,
)
from api.db import BaseAnalitica
from api.erros import MalhaIndisponivel, ParametroInvalido
from api.indicadores import (
    CODIGO_UF,
    MATRICULAS_POR_HABITANTE,
    ROTULO_REGIAO,
    UF,
    UF_DO_CODIGO,
    UF_INFO,
    Dimensao,
    Nivel,
    NivelMalha,
    Recorte,
    Rede,
)
from api.schemas import (
    ClasseCoropletico,
    Filtros,
    LinhaCoropletico,
    RespostaCoropletico,
    ValorCoropletico,
)

# Casar com o ano do Censo. A coluna `ano` e texto.
ANO_POPULACAO = "2024"
CLASSES_PADRAO = 5
POR_HABITANTES = 100_000
# As 5.571 unidades de nivel municipal; as outras 28 linhas de `municipio` sao sentinelas.
_UNIDADE_REAL = "right(m.codigo_municipio_dv, 5) <> '00000' AND m.codigo_municipio_dv <> '9999999'"

_ARQUIVO_MALHA: dict[NivelMalha, str] = {
    NivelMalha.MUNICIPIO: "municipios.geojson",
    NivelMalha.UF: "ufs.geojson",
}

_NOTA_FILTRO_INSTITUCIONAL = (
    "Com filtro de rede, categoria ou organização, o numerador são só as matrículas dessas "
    "instituições; o denominador continua sendo a população total. Unidade sem cor não tem "
    "matrícula registrada nessas instituições — pode ter oferta de outras."
)
_NOTA_AREA = (
    "A área pintada é a do território, não a da população: unidades extensas e pouco povoadas "
    "dominam a mancha visual sem pesar mais no valor do país."
)
_NOTA_QUANTIS = (
    "As classes são quantis das unidades com registro neste recorte: cada cor reúne um número "
    "parecido de unidades, e os limites mudam com os filtros. Cores iguais em mapas com filtros "
    "diferentes não significam o mesmo valor."
)
# Abaixo disto, poucas matriculas deslocam muito a razao (Urutai-GO: 1.104 / 3.667 hab.).
POPULACAO_PEQUENA = 10_000


def _n(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _nota_municipio_pequeno(pequenas: int) -> str:
    return (
        f"Em municípios pequenos poucas matrículas deslocam muito a razão: {_n(pequenas)} das "
        f"unidades com registro neste recorte têm menos de {_n(POPULACAO_PEQUENA)} habitantes. "
        "Leia o numerador e o denominador, não só a cor."
    )


def _nota_sem_municipio(matriculas: int) -> str:
    return (
        f"Ficam fora do numerador {_n(matriculas)} matrículas de polo EAD sem município "
        "identificado neste recorte."
    )


def _validar_municipio(filtros: FiltrosConsulta) -> None:
    """O universo usa so o filtro mais fino; o numerador, todos. Tem de ser o mesmo territorio."""
    if filtros.municipio is None:
        return
    uf = UF_DO_CODIGO.get(filtros.municipio[:2])
    if uf is None:
        raise ParametroInvalido("O código de município não pertence a nenhuma UF.")
    if filtros.uf is not None and filtros.uf != uf:
        raise ParametroInvalido(f"O município informado pertence à UF {uf}, não a {filtros.uf}.")
    if filtros.regiao is not None and UF_INFO[uf][1] != filtros.regiao:
        raise ParametroInvalido(
            f"O município informado pertence à região {ROTULO_REGIAO[UF_INFO[uf][1]]}, "
            f"não à região {ROTULO_REGIAO[filtros.regiao]}."
        )


def caminho_malha(diretorio: Path, nivel: NivelMalha) -> Path:
    """Arquivo GeoJSON do nivel. O nome vem de um mapa fixo, nunca da requisicao."""
    caminho = diretorio / _ARQUIVO_MALHA[nivel]
    if not caminho.is_file():
        raise MalhaIndisponivel(
            "Malha territorial indisponível. Baixe-a com scripts/etl/baixar_malha_ibge.py."
        )
    return caminho


def _valor(numerador: int | None, denominador: int) -> float | None:
    if numerador is None or denominador == 0:
        return None
    return numerador / denominador * POR_HABITANTES


def _classificar(
    linhas: list[LinhaCoropletico], quantidade: int
) -> tuple[list[LinhaCoropletico], list[ClasseCoropletico]]:
    """Quantis sobre as unidades com valor. Empates podem fundir classes; valor nulo fica sem."""
    valores = sorted(linha.valor for linha in linhas if linha.valor is not None)
    if not valores:
        return linhas, []
    # Limite superior de cada classe, exceto a ultima; valor igual ao limite fica na de baixo.
    # Com menos unidades que classes a posicao do corte cai antes do primeiro valor: sem corte.
    posicoes = [(len(valores) * i) // quantidade - 1 for i in range(1, quantidade)]
    cortes = sorted({valores[p] for p in posicoes if p >= 0 and valores[p] < valores[-1]})
    classificadas = [
        linha
        if linha.valor is None
        else linha.model_copy(update={"classe": bisect_left(cortes, linha.valor)})
        for linha in linhas
    ]
    classes = []
    for indice in range(len(cortes) + 1):
        da_classe = [
            li.valor for li in classificadas if li.classe == indice and li.valor is not None
        ]
        classes.append(
            ClasseCoropletico(
                indice=indice,
                minimo=min(da_classe),
                maximo=max(da_classe),
                unidades=len(da_classe),
            )
        )
    return classificadas, classes


def consultar_coropletico(
    base: BaseAnalitica,
    nivel: NivelMalha,
    recorte: Recorte,
    dimensoes: list[Dimensao],
    filtros: FiltrosConsulta | None = None,
    classes: int = CLASSES_PADRAO,
) -> RespostaCoropletico:
    """IND-R-01 por municipio ou por UF, com as classes da legenda calculadas no servidor."""
    filtros = filtros or FiltrosConsulta()
    ind = MATRICULAS_POR_HABITANTE
    dims = validar(ind, Nivel(nivel.value), recorte, dimensoes, filtros)
    _validar_municipio(filtros)

    condicoes, params = _where(ind, dims, filtros)
    condicoes.append(_COM_TERRITORIO)
    universo = [_UNIDADE_REAL]
    params["ano_populacao"] = ANO_POPULACAO
    if filtros.municipio is not None:
        universo.append("m.codigo_municipio_dv = $municipio")
    elif filtros.uf is not None:
        universo.append("m.cd_uf = $cd_uf")
        params["cd_uf"] = CODIGO_UF[filtros.uf]
    elif filtros.regiao is not None:
        universo.append("list_contains($cd_ufs, m.cd_uf)")
        params["cd_ufs"] = [CODIGO_UF[u] for u, (_, r) in UF_INFO.items() if r == filtros.regiao]

    # Pre-agregacao: 1 linha por codigo. Os dois JOINs sao 1:1 sobre o universo (5.571 unidades,
    # 5.571 codigos de 6 digitos distintos, 5.571 linhas de populacao em 2024 — auditado).
    rows = base.consultar(
        f"""
        WITH agg AS (
            SELECT co_municipio AS codigo, CAST({ind.expressao} AS BIGINT) AS matriculas
            FROM {_TABELA["cursos"]}
            WHERE {" AND ".join(condicoes)}
            GROUP BY 1
        )
        SELECT m.codigo_municipio_dv, m.nome_municipio, m.cd_uf,
               CAST(p.populacao AS BIGINT), a.matriculas
        FROM municipio m
        JOIN ibge_populacao_estimada p
          ON p.cod_municipio = m.codigo_municipio AND p.ano = $ano_populacao
        LEFT JOIN agg a ON a.codigo = m.codigo_municipio_dv
        WHERE {" AND ".join(universo)}
        ORDER BY 1
        """,
        params,
    )

    municipios = [
        LinhaCoropletico(
            codigo=r[0],
            nome=r[1],
            uf=UF_DO_CODIGO[r[2]],
            numerador=r[4],
            denominador=r[3],
            valor=_valor(r[4], r[3]),
            classe=None,
        )
        for r in rows
    ]
    if not municipios:
        # Codigo de 7 digitos bem formado que nao e unidade real (inexistente ou sentinela).
        raise ParametroInvalido("O município informado não é uma unidade territorial da base.")
    # Sem nenhuma unidade com registro o territorio e ausencia, como cada linha — nao zero.
    registrados = [m.numerador for m in municipios if m.numerador is not None]
    numerador = sum(registrados) if registrados else None
    denominador = sum(m.denominador for m in municipios)
    pequenas = sum(
        1 for m in municipios if m.numerador is not None and m.denominador < POPULACAO_PEQUENA
    )
    sem_municipio = (
        _sem_territorio(base, ind, dims, filtros)
        if Dimensao.EAD_POLO in dims and not filtros.territorial
        else 0
    )

    if nivel == NivelMalha.MUNICIPIO:
        linhas = municipios
    else:
        # O denominador e reagregado: populacao de TODAS as unidades da UF, nao a media das razoes.
        por_uf: dict[UF, list[LinhaCoropletico]] = {}
        for m in municipios:
            por_uf.setdefault(UF(m.uf), []).append(m)
        linhas = []
        for sigla, grupo in sorted(por_uf.items(), key=lambda par: CODIGO_UF[par[0]]):
            com_dado = [g.numerador for g in grupo if g.numerador is not None]
            num = sum(com_dado) if com_dado else None
            den = sum(g.denominador for g in grupo)
            linhas.append(
                LinhaCoropletico(
                    codigo=CODIGO_UF[sigla],
                    nome=UF_INFO[sigla][0],
                    uf=sigla,
                    numerador=num,
                    denominador=den,
                    valor=_valor(num, den),
                    classe=None,
                )
            )

    linhas, legenda = _classificar(linhas, classes)
    com_registro = sum(1 for linha in linhas if linha.numerador is not None)
    institucional = any((filtros.rede, filtros.categoria, filtros.organizacao))
    notas = [
        _NOTA_QUANTIS,
        _NOTA_AREA,
        *(
            [_nota_municipio_pequeno(pequenas)]
            if nivel == NivelMalha.MUNICIPIO and pequenas
            else []
        ),
        *([_NOTA_FILTRO_INSTITUCIONAL] if institucional else []),
        *([_nota_sem_municipio(sem_municipio)] if sem_municipio else []),
        *([_NOTA_PUBLICA] if filtros.rede == Rede.PUBLICA else []),
    ]
    return RespostaCoropletico(
        indicador=info(ind),
        numerador_nome="Matrículas",
        denominador_nome=f"População estimada (IBGE, {ANO_POPULACAO})",
        ano_censo=ANO_CENSO,
        ano_populacao=ANO_POPULACAO,
        recorte=ind.recorte,
        nivel=nivel,
        filtros=Filtros(**_filtros_resposta(filtros, dims)),
        geral=ValorCoropletico(
            numerador=numerador, denominador=denominador, valor=_valor(numerador, denominador)
        ),
        unidades=len(linhas),
        com_registro=com_registro,
        sem_registro=len(linhas) - com_registro,
        metodo_classes="quantis",
        classes=legenda,
        notas=notas,
        linhas=linhas,
    )
