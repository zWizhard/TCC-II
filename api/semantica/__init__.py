"""Camada semantica do Analista IA (Fase 12): a ponte entre a pergunta e a base.

Nesta fase NAO ha QueryPlan, geracao de SQL, chamada a LLM nem endpoint. Ha:

- `CAMADA` — entidades, colunas, dimensoes, metricas, relacionamentos, regras de dominio,
  termos vedados e ambiguidades, em modelos Pydantic congelados (JSON + JSON Schema);
- `recuperar_contexto(pergunta)` — o recorte da camada que uma pergunta precisa;
- `cruzar_com_inventario()` — a classificacao de cada uma das 318 colunas;
- `listar_sinonimos_propostos()` — os sinonimos coloquiais que o autor ainda confirma.
"""

from api.semantica.camada import CAMADA, listar_sinonimos_propostos
from api.semantica.cobertura import RelatorioCobertura, cruzar_com_inventario
from api.semantica.modelos import CamadaSemantica, Papel, StatusSinonimo
from api.semantica.recuperacao import ContextoSemantico, recuperar_contexto

__all__ = [
    "CAMADA",
    "CamadaSemantica",
    "ContextoSemantico",
    "Papel",
    "RelatorioCobertura",
    "StatusSinonimo",
    "cruzar_com_inventario",
    "listar_sinonimos_propostos",
    "recuperar_contexto",
]
