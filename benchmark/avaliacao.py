"""Criterios de correcao do benchmark. Nenhum compara texto de SQL.

- Plano: igualdade CANONICA com o plano de referencia. O que nao muda a consulta nao conta
  (ordem de metricas, filtros, valores e dimensoes de oferta; `visualization_hint`, que e livre).
- SQL: equivalencia por EXECUCAO. O SQL gerado e reexecutado e o conjunto de linhas e comparado ao
  do SQL de referencia (multiconjunto; lista ordenada quando o caso e um ranking).
- Resultado: as linhas da resposta final do Analista, ja com rotulos, corte e arredondamento,
  comparadas ao mesmo resultado de referencia.

A comparacao usa as colunas do SQL de referencia, localizadas pelo nome nas colunas do resultado
avaliado. Metricas: inteiros exatos; razoes com tolerancia absoluta de meio digito da 4a casa (o
arredondamento da resposta).
"""

import math
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from api.analista.plano import QueryPlan

CASAS = 4
# A resposta arredonda razoes a 4 casas: meio digito da ultima casa, mais folga de ponto flutuante.
TOLERANCIA = 0.5 * 10**-CASAS + 1e-9


def plano_canonico(plano: QueryPlan | dict[str, Any]) -> dict[str, Any]:
    """Forma do plano em que dois planos equivalentes ficam iguais."""
    p = plano if isinstance(plano, QueryPlan) else QueryPlan.model_validate(plano)
    return {
        "intent": str(p.intent),
        "entity": str(p.entity),
        "metrics": sorted(p.metrics),
        "recorte": str(p.dimensions.recorte),
        "nivel_territorial": str(p.dimensions.nivel_territorial),
        "dimensao_de_oferta": sorted(str(d) for d in p.dimensions.dimensao_de_oferta),
        "filters": sorted((f.dimensao, sorted(f.valores)) for f in p.filters),
        "group_by": sorted(p.group_by),
        "having": sorted((h.metrica, str(h.operador), float(h.valor)) for h in p.having),
        "order_by": [(o.por, str(o.direcao)) for o in p.order_by],  # a ordem das chaves importa
        "limit": p.limit,
    }


def diferencas_de_plano(obtido: dict[str, Any], esperado: dict[str, Any]) -> list[str]:
    """Campos do plano canonico em que o obtido diverge do esperado."""
    return [campo for campo in esperado if obtido.get(campo) != esperado[campo]]


def _celula(valor: Any, e_metrica: bool) -> Any:
    if valor is None:
        return None
    if not e_metrica:
        return str(valor)
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, int):
        return valor
    if isinstance(valor, Decimal) and valor == valor.to_integral_value():
        return int(valor)
    return float(valor)


def normalizar(
    colunas: Sequence[str], linhas: Sequence[Sequence[Any]], metricas: Sequence[str]
) -> list[tuple[Any, ...]]:
    """Linhas com chaves como texto e metricas como numero comparavel."""
    e_metrica = [c in metricas for c in colunas]
    return [tuple(_celula(v, m) for v, m in zip(linha, e_metrica, strict=True)) for linha in linhas]


def _chave(linha: tuple[Any, ...]) -> tuple[Any, ...]:
    """Ordena pelas chaves (texto) e, no empate, pelas metricas arredondadas."""
    return tuple(
        (v is None, v if isinstance(v, str) else "", round(v, CASAS - 1) if _numero(v) else 0)
        for v in linha
    )


def _numero(v: Any) -> bool:
    return isinstance(v, int | float)


def _iguais(a: Any, b: Any) -> bool:
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return bool(a == b)
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return math.isclose(a, b, rel_tol=0.0, abs_tol=TOLERANCIA)


def mesmo_resultado(
    colunas_ref: Sequence[str],
    linhas_ref: Sequence[Sequence[Any]],
    colunas: Sequence[str],
    linhas: Sequence[Sequence[Any]],
    metricas: Sequence[str],
    ordenado: bool,
) -> bool:
    """O resultado avaliado traz as colunas de referencia com exatamente as mesmas linhas?"""
    if any(c not in colunas for c in colunas_ref):
        return False
    indices = [list(colunas).index(c) for c in colunas_ref]
    projetadas = [[linha[i] for i in indices] for linha in linhas]
    a = normalizar(colunas_ref, linhas_ref, metricas)
    b = normalizar(colunas_ref, projetadas, metricas)
    if not ordenado:
        a, b = sorted(a, key=_chave), sorted(b, key=_chave)
    return len(a) == len(b) and all(
        all(_iguais(x, y) for x, y in zip(la, lb, strict=True)) for la, lb in zip(a, b, strict=True)
    )


def ha_empate_na_ordem(
    colunas_ref: Sequence[str], linhas_ref: Sequence[Sequence[Any]], metrica: str
) -> bool:
    """Ranking com valores repetidos: a ordem dependeria do desempate, nao da pergunta."""
    i = list(colunas_ref).index(metrica)
    valores = [linha[i] for linha in linhas_ref]
    return len(set(valores)) != len(valores)
