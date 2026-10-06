"""Endpoints. Somente GET, somente parametros enumerados — nenhuma consulta livre."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from api.consultas import ANO_CENSO, LIMITE_MAXIMO, consultar_indicador, info
from api.db import BaseAnalitica
from api.erros import BaseAnaliticaIndisponivel, IndicadorNaoEncontrado
from api.indicadores import (
    CATALOGO,
    DIMENSOES_COM_TERRITORIO,
    ROTULO_DIMENSAO,
    UF,
    Dimensao,
    Nivel,
    Recorte,
    Rede,
)
from api.schemas import DimensaoOferta, IndicadorInfo, Metadados, RespostaIndicador, Saude

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
            DimensaoOferta(slug=d, rotulo=r, territorializavel=d in DIMENSOES_COM_TERRITORIO)
            for d, r in ROTULO_DIMENSAO.items()
        ],
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
    uf: Annotated[UF | None, Query(description="Só no nível municipio.")] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_MAXIMO,
) -> RespostaIndicador:
    ind = CATALOGO.get(slug)
    if ind is None:
        # O slug recebido nao e ecoado: a lista valida esta em /api/v1/indicadores.
        raise IndicadorNaoEncontrado("Indicador não existe no catálogo; ver /api/v1/indicadores.")
    return consultar_indicador(base, ind, nivel, recorte, dimensao, rede, uf, limite)
