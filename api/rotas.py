"""Endpoints. Somente GET, somente parametros enumerados — nenhuma consulta livre."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import StringConstraints

from api.analises import (
    LIMITE_COMPOSICAO,
    LIMITE_INSTITUICOES,
    consultar_composicao,
    listar_instituicoes,
)
from api.comparacoes import MAX_UNIDADES, MIN_UNIDADES, consultar_comparacao
from api.consultas import (
    ANO_CENSO,
    LIMITE_MAXIMO,
    FiltrosConsulta,
    consultar_indicador,
    info,
    listar_municipios,
)
from api.db import BaseAnalitica
from api.erros import BaseAnaliticaIndisponivel, IndicadorNaoEncontrado
from api.fluxo import consultar_razao, info_razao
from api.indicadores import (
    AREA_CINE,
    CATALOGO,
    DIMENSOES_COM_TERRITORIO,
    MODALIDADE_DA_DIMENSAO,
    RAZOES,
    REDE_DA_CATEGORIA,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_GRAU,
    ROTULO_ORGANIZACAO,
    ROTULO_REGIAO,
    UF,
    UF_INFO,
    Agrupamento,
    AreaCine,
    BaseFluxo,
    Categoria,
    Dimensao,
    Eixo,
    Grau,
    Nivel,
    NivelComparacao,
    NivelMalha,
    OrdemInstituicoes,
    Organizacao,
    Recorte,
    Rede,
    Regiao,
)
from api.mapas import CLASSES_PADRAO, caminho_malha, consultar_coropletico
from api.schemas import (
    AreaCineInfo,
    CategoriaInfo,
    DimensaoOferta,
    GrauInfo,
    IndicadorInfo,
    Metadados,
    OrganizacaoInfo,
    RazaoInfo,
    RegiaoInfo,
    RespostaComparacao,
    RespostaComposicao,
    RespostaCoropletico,
    RespostaIndicador,
    RespostaInstituicoes,
    RespostaMunicipios,
    RespostaRazao,
    Saude,
    UFInfo,
)

router = APIRouter(prefix="/api")


def base_analitica(request: Request) -> BaseAnalitica:
    base: BaseAnalitica | None = request.app.state.base
    if base is None:
        raise BaseAnaliticaIndisponivel(
            "Camada analítica local indisponível. Gere-a com scripts/etl/pg_to_duckdb.py."
        )
    return base


@router.get("/health", response_model=Saude)
def health(request: Request) -> Saude:
    ok = request.app.state.base is not None
    return Saude(status="ok", base_analitica="disponivel" if ok else "indisponivel")


@router.get("/v1/metadados", response_model=Metadados)
def metadados(request: Request) -> Metadados:
    extraido_em = None
    try:
        manifesto = json.loads(request.app.state.settings.etl_manifest_path.read_text("utf-8"))
        extraido_em = manifesto.get("gerado_em")
    except (OSError, ValueError):
        pass
    return Metadados(
        ano_censo=ANO_CENSO,
        fonte="Censo da Educação Superior 2024 (INEP), cópia local do Big Data IESB",
        extraido_em=extraido_em,
        recortes=list(Recorte),
        niveis=list(Nivel),
        dimensoes_oferta=[
            DimensaoOferta(
                slug=d,
                rotulo=r,
                territorializavel=d in DIMENSOES_COM_TERRITORIO,
                modalidade=MODALIDADE_DA_DIMENSAO[d],
            )
            for d, r in ROTULO_DIMENSAO.items()
        ],
        regioes=[RegiaoInfo(slug=r, nome=n) for r, n in ROTULO_REGIAO.items()],
        ufs=[UFInfo(sigla=u, nome=n, regiao=r) for u, (n, r) in UF_INFO.items()],
        categorias=[
            CategoriaInfo(slug=c, rotulo=r, rede=REDE_DA_CATEGORIA[c])
            for c, r in ROTULO_CATEGORIA.items()
        ],
        organizacoes=[OrganizacaoInfo(slug=o, rotulo=r) for o, r in ROTULO_ORGANIZACAO.items()],
        areas_cine=[AreaCineInfo(slug=a, codigo=c, nome=n) for a, (c, n) in AREA_CINE.items()],
        graus=[GrauInfo(slug=g, rotulo=r) for g, r in ROTULO_GRAU.items()],
        aviso="Retrato transversal de um único ano: não há série temporal.",
    )


@router.get("/v1/indicadores", response_model=list[IndicadorInfo])
def listar_indicadores() -> list[IndicadorInfo]:
    return [info(i) for i in CATALOGO.values()]


@router.get("/v1/indicadores/{slug}", response_model=RespostaIndicador)
def indicador(
    slug: str,
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    nivel: Annotated[Nivel, Query()],
    recorte: Annotated[Recorte, Query(description="Obrigatório e explícito (ADR-0004).")],
    dimensao: Annotated[
        list[Dimensao],
        Query(description="tp_dimensao incluídas; obrigatória para indicadores de cursos."),
    ] = [],  # noqa: B006 — FastAPI copia o default a cada requisicao
    rede: Annotated[Rede | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    organizacao: Annotated[Organizacao | None, Query()] = None,
    regiao: Annotated[Regiao | None, Query(description="Níveis regiao, uf e municipio.")] = None,
    uf: Annotated[UF | None, Query(description="Níveis uf e municipio.")] = None,
    municipio: Annotated[
        str | None,
        Query(
            pattern=r"^[0-9]{7}$", description="Código IBGE de 7 dígitos; só no nível municipio."
        ),
    ] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_MAXIMO,
) -> RespostaIndicador:
    ind = CATALOGO.get(slug)
    if ind is None:
        # O slug recebido nao e ecoado: a lista valida esta em /api/v1/indicadores.
        raise IndicadorNaoEncontrado("Indicador não existe no catálogo; ver /api/v1/indicadores.")
    filtros = FiltrosConsulta(
        rede=rede,
        categoria=categoria,
        organizacao=organizacao,
        regiao=regiao,
        uf=uf,
        municipio=municipio,
    )
    return consultar_indicador(base, ind, nivel, recorte, dimensao, filtros, limite)


@router.get("/v1/indicadores/{slug}/composicao", response_model=RespostaComposicao)
def composicao(
    slug: str,
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    por: Annotated[Eixo, Query(description="Eixo categórico da decomposição.")],
    recorte: Annotated[Recorte, Query(description="Obrigatório e explícito (ADR-0004).")],
    dimensao: Annotated[
        list[Dimensao],
        Query(description="tp_dimensao incluídas; obrigatória para indicadores de cursos."),
    ] = [],  # noqa: B006 — FastAPI copia o default a cada requisicao
    rede: Annotated[Rede | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    organizacao: Annotated[Organizacao | None, Query()] = None,
    regiao: Annotated[Regiao | None, Query()] = None,
    uf: Annotated[UF | None, Query()] = None,
    municipio: Annotated[str | None, Query(pattern=r"^[0-9]{7}$")] = None,
    area: Annotated[AreaCine | None, Query(description="Só indicadores de cursos.")] = None,
    grau: Annotated[Grau | None, Query(description="Só indicadores de cursos.")] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_COMPOSICAO)] = LIMITE_COMPOSICAO,
) -> RespostaComposicao:
    ind = CATALOGO.get(slug)
    if ind is None:
        raise IndicadorNaoEncontrado("Indicador não existe no catálogo; ver /api/v1/indicadores.")
    filtros = FiltrosConsulta(
        rede=rede,
        categoria=categoria,
        organizacao=organizacao,
        regiao=regiao,
        uf=uf,
        municipio=municipio,
    )
    return consultar_composicao(base, ind, por, recorte, dimensao, filtros, area, grau, limite)


@router.get("/v1/razoes", response_model=list[RazaoInfo])
def listar_razoes() -> list[RazaoInfo]:
    return [info_razao(d) for d in RAZOES.values()]


@router.get("/v1/razoes/{slug}", response_model=RespostaRazao)
def razao(
    slug: str,
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    recorte: Annotated[Recorte, Query(description="Obrigatório e explícito (ADR-0004).")],
    dimensao: Annotated[
        list[Dimensao], Query(description="tp_dimensao incluídas; obrigatória.")
    ] = [],  # noqa: B006 — FastAPI copia o default a cada requisicao
    por: Annotated[
        Agrupamento | None,
        Query(description="Comparação: um nível territorial ou um eixo categórico."),
    ] = None,
    base_fluxo: Annotated[
        BaseFluxo | None,
        Query(alias="base", description="Só IND-R-08 e IND-R-09, em que é obrigatória."),
    ] = None,
    rede: Annotated[Rede | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    organizacao: Annotated[Organizacao | None, Query()] = None,
    regiao: Annotated[Regiao | None, Query()] = None,
    uf: Annotated[UF | None, Query()] = None,
    municipio: Annotated[str | None, Query(pattern=r"^[0-9]{7}$")] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_MAXIMO,
) -> RespostaRazao:
    definicao = RAZOES.get(slug)
    if definicao is None:
        raise IndicadorNaoEncontrado("Razão não existe no catálogo; ver /api/v1/razoes.")
    filtros = FiltrosConsulta(
        rede=rede,
        categoria=categoria,
        organizacao=organizacao,
        regiao=regiao,
        uf=uf,
        municipio=municipio,
    )
    return consultar_razao(base, definicao, recorte, dimensao, filtros, por, base_fluxo, limite)


@router.get("/v1/instituicoes", response_model=RespostaInstituicoes)
def instituicoes(
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    dimensao: Annotated[
        list[Dimensao],
        Query(description="tp_dimensao das métricas de curso; obrigatória."),
    ] = [],  # noqa: B006 — FastAPI copia o default a cada requisicao
    rede: Annotated[Rede | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    organizacao: Annotated[Organizacao | None, Query()] = None,
    regiao: Annotated[Regiao | None, Query(description="Região da sede.")] = None,
    uf: Annotated[UF | None, Query(description="UF da sede.")] = None,
    municipio: Annotated[
        str | None, Query(pattern=r"^[0-9]{7}$", description="Município da sede.")
    ] = None,
    ordem: Annotated[OrdemInstituicoes, Query()] = OrdemInstituicoes.MATRICULAS,
    limite: Annotated[int, Query(ge=1, le=LIMITE_INSTITUICOES)] = 25,
    pagina: Annotated[int, Query(ge=1, le=3000)] = 1,
) -> RespostaInstituicoes:
    filtros = FiltrosConsulta(
        rede=rede,
        categoria=categoria,
        organizacao=organizacao,
        regiao=regiao,
        uf=uf,
        municipio=municipio,
    )
    return listar_instituicoes(base, dimensao, filtros, ordem, limite, pagina)


@router.get("/v1/mapa/malha/{nivel}", response_class=FileResponse)
def malha(nivel: NivelMalha, request: Request) -> FileResponse:
    """GeoJSON do IBGE, como baixado. A chave de cada feição é `properties.codarea`."""
    caminho = caminho_malha(request.app.state.settings.malha_dir, nivel)
    # Estatica (so muda se o script de download rodar de novo): o navegador guarda por um dia.
    return FileResponse(
        caminho,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/v1/mapa/coropletico", response_model=RespostaCoropletico)
def coropletico(
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    nivel: Annotated[NivelMalha, Query(description="Nível das unidades pintadas.")],
    recorte: Annotated[Recorte, Query(description="Obrigatório e explícito (ADR-0004).")],
    dimensao: Annotated[
        list[Dimensao], Query(description="tp_dimensao incluídas; obrigatória.")
    ] = [],  # noqa: B006 — FastAPI copia o default a cada requisicao
    rede: Annotated[Rede | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    organizacao: Annotated[Organizacao | None, Query()] = None,
    regiao: Annotated[Regiao | None, Query()] = None,
    uf: Annotated[UF | None, Query()] = None,
    municipio: Annotated[str | None, Query(pattern=r"^[0-9]{7}$")] = None,
    classes: Annotated[int, Query(ge=3, le=7, description="Classes da legenda.")] = CLASSES_PADRAO,
) -> RespostaCoropletico:
    filtros = FiltrosConsulta(
        rede=rede,
        categoria=categoria,
        organizacao=organizacao,
        regiao=regiao,
        uf=uf,
        municipio=municipio,
    )
    return consultar_coropletico(base, nivel, recorte, dimensao, filtros, classes)


@router.get("/v1/comparacoes", response_model=RespostaComparacao)
def comparacoes(
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    nivel: Annotated[NivelComparacao, Query(description="Nível de todas as unidades comparadas.")],
    unidade: Annotated[
        list[Annotated[str, StringConstraints(pattern=r"^([a-z_]{3,12}|[A-Z]{2}|[0-9]{7})$")]],
        Query(
            min_length=MIN_UNIDADES,
            max_length=MAX_UNIDADES,
            description="Slug da região, sigla da UF ou código IBGE de 7 dígitos, conforme o nível.",
        ),
    ],
    rede: Annotated[Rede | None, Query(description="Vale para todas as unidades.")] = None,
) -> RespostaComparacao:
    return consultar_comparacao(base, nivel, unidade, rede)


@router.get("/v1/territorios/municipios", response_model=RespostaMunicipios)
def municipios(
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    uf: Annotated[UF, Query()],
) -> RespostaMunicipios:
    return listar_municipios(base, uf)
