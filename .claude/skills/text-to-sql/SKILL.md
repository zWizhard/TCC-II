---
name: text-to-sql
description: Implementar ou modificar o pipeline Text-to-SQL do Analista IA — camada semântica, QueryPlan, validação, geração e validação AST de SQL, execução read-only e spec de visualização. Use em qualquer tarefa que faça o LLM influenciar uma consulta.
---

# text-to-sql

Pipeline **obrigatório**, sem atalhos:

```
Pergunta → Semântica → QueryPlan → Validação → SQL → Validação AST
        → Execução read-only → Resultado → Visualização → Explicação
```

O LLM **interpreta**. A aplicação **valida**. O backend **gera e valida** o SQL.
O modelo nunca emite SQL livre que vá direto ao banco, e nunca calcula número relevante.

## 1. Semântica

Resolver a pergunta contra a camada semântica (entidades, dimensões, métricas, sinônimos,
relacionamentos, agregações e filtros permitidos), construída a partir do **schema real**.
Termo que não mapeia para nada → rejeitar com mensagem clara, não improvisar coluna.

**Ambiguidade que altera o resultado se pergunta ao usuário.** Caso canônico: "universidade" pode ser
IES no sentido informal ou Organização Acadêmica = Universidade — respostas diferentes.

## 2. QueryPlan (Pydantic)

`intent`, `entity`, `metrics`, `dimensions`, `filters`, `group_by`, `having`, `order_by`, `limit`,
`visualization_hint`. Structured output do LLM; parse falho é erro, não motivo para regex de resgate.

## 3. Validação semântica do plano

Toda métrica, dimensão e filtro existe na camada semântica? A agregação é válida para aquela métrica?
Os campos de `group_by` são compatíveis com o grain? `limit` presente e dentro do teto?
Plano inválido é **rejeitado** — nunca "consertado" por adivinhação.

## 4. Geração de SQL

Gerada **pelo backend a partir do plano validado**, não copiada do texto do modelo.
Valores do usuário sempre parametrizados. `LIMIT` e timeout sempre aplicados.

## 5. Validação AST (SQLGlot)

Rejeitar: DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, MERGE, CALL, EXECUTE;
múltiplos statements; qualquer tabela/schema fora da allowlist, **inclusive dentro de CTE e subquery**;
ausência de LIMIT. Validar a árvore — não confie em regex sobre a string.

## 6. Execução

Usuário de banco somente leitura + timeout + limite de linhas. Falha de permissão no banco é a
última linha de defesa, não a primeira.

## 7. Resultado e visualização

Números vêm do banco. O LLM só **interpreta** o resultado já calculado.
A visualização é uma **spec estruturada** validada contra o allowlist (KPI, tabela, bar, line,
composição, ranking, mapa, heatmap). **Nunca** executar JavaScript vindo do modelo; nunca renderizar
texto do modelo como HTML.

## 8. Explicação e log

Devolver ao usuário: a interpretação da pergunta, os filtros aplicados e as limitações do dado.
Logar pergunta, QueryPlan, SQL final e tempo — **sem credenciais**.
**Nunca** enviar credencial, connection string ou `.env` ao LLM.

## Modelo

Local via Ollama, configurável por `LLM_PROVIDER` / `OLLAMA_MODEL`. Trocar o modelo não pode exigir
mudança na lógica. Sem dependência de API paga.

## Encerramento

Mudança no pipeline ou na postura de segurança é decisão estruturante — chame `tcc-documentarian`
(vira ADR) e atualize `docs/tcc/architecture/AI_ANALYST.md`.
