"""Erros de dominio da API e o formato unico de resposta de erro.

Nenhuma resposta de erro expoe SQL, caminho de arquivo ou stack trace: o detalhe vai para o log.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

log = logging.getLogger("api.erros")


class ErroApi(Exception):
    status = 500
    codigo = "erro_interno"

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class ParametroInvalido(ErroApi):
    """Combinacao de parametros que a metodologia nao admite (ex.: vagas de EAD por municipio)."""

    status = 422
    codigo = "parametro_invalido"


class IndicadorNaoEncontrado(ErroApi):
    status = 404
    codigo = "indicador_nao_encontrado"


class BaseAnaliticaIndisponivel(ErroApi):
    status = 503
    codigo = "base_analitica_indisponivel"


class ConsultaExcedeuTempo(ErroApi):
    status = 504
    codigo = "consulta_excedeu_tempo"


def _corpo(codigo: str, mensagem: str) -> dict[str, dict[str, str]]:
    return {"erro": {"codigo": codigo, "mensagem": mensagem}}


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Mesmo envelope dos demais erros; so o local e a mensagem de cada problema, sem o input.
        problemas = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return JSONResponse(status_code=422, content=_corpo("parametro_invalido", problemas))

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException) -> JSONResponse:
        # 404 de rota e 405 de metodo no mesmo envelope dos erros de dominio.
        return JSONResponse(
            status_code=exc.status_code,
            content=_corpo(f"http_{exc.status_code}", str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(ErroApi)
    async def _erro_api(_: Request, exc: ErroApi) -> JSONResponse:
        if exc.status >= 500:
            log.error("%s: %s", exc.codigo, exc.mensagem)
        return JSONResponse(status_code=exc.status, content=_corpo(exc.codigo, exc.mensagem))

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        log.exception("erro inesperado em %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_corpo("erro_interno", "Erro interno. Consulte o log do servidor."),
        )
