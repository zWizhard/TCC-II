"""Analista IA (Fase 13): da pergunta em linguagem natural a resposta, sem SQL livre.

    Pergunta -> contexto semantico -> LLM (JSON) -> QueryPlan -> validacao (camada + contexto)
             -> SQL gerado pelo backend -> validacao AST -> execucao read-only -> analise
             -> spec de visualizacao -> explicacao

O LLM so escolhe identificadores; a aplicacao valida; o backend gera e valida o SQL. Cada etapa e
um modulo: `plano`, `validacao`, `sql`, `validador_sql`, `llm`, `analise`, `visualizacao`,
`pipeline` e `rotas`.
"""

from api.analista.pipeline import RespostaAnalista, responder
from api.analista.plano import QueryPlan

__all__ = ["QueryPlan", "RespostaAnalista", "responder"]
