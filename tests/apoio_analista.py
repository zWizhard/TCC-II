"""Apoio dos testes do Analista IA: provedor falso e montagem de planos. Nenhum teste usa rede."""

import json
from typing import Any

from api.analista.plano import QueryPlan, interpretar_plano


class ProvedorFalso:
    """Devolve um texto roteirizado e guarda o que recebeu (sistema, usuario, schema)."""

    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta if isinstance(resposta, str) else json.dumps(resposta)
        self.chamadas: list[tuple[str, str, dict[str, Any]]] = []

    def gerar_json(self, sistema: str, usuario: str, schema: dict[str, Any]) -> str:
        self.chamadas.append((sistema, usuario, schema))
        return self.resposta


def dims(recorte: str, nivel: str, *oferta: str) -> dict[str, Any]:
    return {"recorte": recorte, "nivel_territorial": nivel, "dimensao_de_oferta": list(oferta)}


def filtro(dimensao: str, *valores: str) -> dict[str, Any]:
    return {"dimensao": dimensao, "valores": list(valores)}


def plano_dict(**campos: Any) -> dict[str, Any]:
    """Plano de 'matrículas presenciais no Brasil'; `campos` sobrescreve o que o teste quiser."""
    base: dict[str, Any] = {
        "intent": "valor",
        "entity": "cursos",
        "metrics": ["matriculas"],
        "dimensions": dims("oferta", "brasil", "presencial"),
    }
    base.update(campos)
    return base


def plano(**campos: Any) -> QueryPlan:
    return interpretar_plano(json.dumps(plano_dict(**campos)))


# Pergunta e plano corretos do caso mais usado nos testes.
P_UF_PRIVADA = "matrículas presenciais por UF na rede privada"


def plano_uf_privada(**campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "intent": "distribuicao",
        "dimensions": dims("oferta", "uf", "presencial"),
        "filters": [filtro("rede", "privada")],
    }
    base.update(campos)
    return plano_dict(**base)


P_IES_BRASIL = "Quantas IES existem no Brasil?"
PLANO_IES_BRASIL = plano_dict(entity="ies", metrics=["ies"], dimensions=dims("sede", "brasil"))
