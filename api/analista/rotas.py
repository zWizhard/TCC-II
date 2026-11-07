"""Endpoint do Analista IA. O corpo so tem a pergunta: nenhum SQL, coluna ou plano vem do cliente."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from api.analista.llm import ProvedorLLM, criar_provedor
from api.analista.pipeline import RespostaAnalista, responder
from api.db import BaseAnalitica
from api.rotas import base_analitica
from api.semantica.recuperacao import MAX_PERGUNTA

router = APIRouter(prefix="/api/v1/analista", tags=["analista"])


class PerguntaAnalista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pergunta: str = Field(min_length=1, max_length=MAX_PERGUNTA)


def provedor_llm(request: Request) -> ProvedorLLM:
    """Provedor guardado em `app.state` (os testes injetam um falso); criado no primeiro uso."""
    provedor: ProvedorLLM | None = getattr(request.app.state, "provedor_llm", None)
    if provedor is None:
        provedor = criar_provedor(request.app.state.settings)
        request.app.state.provedor_llm = provedor
    return provedor


# `def` (nao `async`): a chamada ao modelo e a consulta bloqueiam, e rodam no threadpool.
@router.post("/perguntas")
def perguntar(
    corpo: PerguntaAnalista,
    request: Request,
    base: Annotated[BaseAnalitica, Depends(base_analitica)],
    provedor: Annotated[ProvedorLLM, Depends(provedor_llm)],
) -> RespostaAnalista:
    return responder(corpo.pergunta, base, provedor, request.app.state.settings.analista_max_linhas)
