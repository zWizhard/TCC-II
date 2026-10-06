"""Aplicacao FastAPI do Observatorio.

    .venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

A API expoe apenas indicadores do catalogo fechado (`api/indicadores.py`): o frontend nao envia
SQL, nome de coluna nem expressao — so escolhe entre opcoes enumeradas.
"""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings, get_settings
from api.db import BaseAnalitica
from api.erros import BaseAnaliticaIndisponivel, registrar_tratadores
from api.rotas import router

log = logging.getLogger("api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Base ausente nao derruba a API: /api/health informa, e as consultas devolvem 503.
        try:
            app.state.base = BaseAnalitica(
                settings.analytics_duckdb_path, settings.api_query_timeout_seconds
            )
            log.info("camada analitica aberta (somente leitura)")
        except BaseAnaliticaIndisponivel as exc:
            app.state.base = None
            log.error(exc.mensagem)
        yield
        if app.state.base is not None:
            app.state.base.fechar()

    app = FastAPI(
        title="Observatorio Inteligente da Educacao Superior — API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=[],
    )

    @app.middleware("http")
    async def _log_requisicao(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inicio = time.perf_counter()
        resposta = await call_next(request)
        # !r: um %0A decodificado no path nao injeta linha falsa no log.
        log.info(
            "%s %r -> %d (%.1f ms)",
            request.method,
            request.url.path,
            resposta.status_code,
            (time.perf_counter() - inicio) * 1000,
        )
        return resposta

    registrar_tratadores(app)
    app.include_router(router)
    return app


app = create_app()
