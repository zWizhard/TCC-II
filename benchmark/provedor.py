"""Provedores de teste do benchmark: plano fixo (validacao do conjunto) e proibido (bloco S).

A medicao de modelos reais aguarda o provedor de producao (AWS Bedrock, ADR-0021).
"""

import json
from typing import Any


class ProvedorRoteirizado:
    """Devolve um plano fixo: valida o conjunto de teste (o plano de referencia tem de acertar)."""

    def __init__(self, plano: dict[str, Any]) -> None:
        self._texto = json.dumps(plano)

    def gerar_json(self, sistema: str, usuario: str, schema: dict[str, Any]) -> str:
        return self._texto


class ProvedorProibido:
    """Bloco S: a pergunta tem de ser resolvida sem LLM. Ser chamado e a falha."""

    def __init__(self) -> None:
        self.chamado = False

    def gerar_json(self, sistema: str, usuario: str, schema: dict[str, Any]) -> str:
        self.chamado = True
        raise AssertionError("o LLM foi chamado em um caso do bloco de sistema")
