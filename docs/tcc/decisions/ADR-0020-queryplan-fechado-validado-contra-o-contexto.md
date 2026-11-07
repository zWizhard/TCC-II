# ADR-0020 — QueryPlan fechado validado contra o contexto da pergunta e SQL gerado pelo backend

- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

O Analista IA recebe texto livre e precisa devolver números do Censo 2024 a partir do DuckDB local
([ADR-0003](ADR-0003-camada-analitica-local-duckdb.md)). A saída de um LLM é entrada não confiável:
o modelo pode errar ou ser induzido pela própria pergunta (prompt injection). A camada semântica
([ADR-0019](ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md)) já deriva da pergunta,
de forma determinística e sem LLM, um contexto com métricas, recorte, nível territorial, filtros e
ambiguidades. O modelo a ser usado ainda não foi escolhido nem testado (Ollama ausente).

## Decisão

1. **O LLM só escolhe identificadores de um plano fechado.** O QueryPlan é um modelo Pydantic
   congelado, com `extra=forbid` e modo estrito, sem string livre: apenas ids
   (`^[A-Za-z0-9_]{1,64}$`) e enums. Recorte, nível territorial e dimensão de oferta são
   obrigatórios e sem padrão.
2. **O plano é validado contra a camada e contra o contexto determinístico da pergunta.** Métricas,
   recorte, nível, dimensão de oferta, filtros, quebras, papel de cada número, operador e ordem têm
   de ser os da pergunta. Esta validação, e não o prompt, é a defesa contra prompt injection e
   contra erro do modelo. Plano divergente é rejeitado, nunca corrigido.
3. **O LLM só é chamado com contexto `pronta`.** O que não se deriva com segurança vira
   esclarecimento antes do modelo.
4. **O SQL é montado pelo backend** apenas com fragmentos da camada semântica, e todo valor é
   parametrizado.
5. **Validador AST por allowlist** (SQLGlot, dialeto `duckdb`), executado sempre antes da consulta:
   exatamente um `SELECT` sobre uma tabela da entidade do plano, sem CTE, subconsulta ou JOIN,
   colunas restritas às expostas, funções em allowlist, sem comentário e `LIMIT` até o teto.
6. **Explicação e análise são determinísticas**, sem texto gerado por LLM na resposta.
7. **Spec de visualização fechada**, com título definido pelo backend; o tipo `line` é sempre
   rejeitado, por haver apenas o ano de 2024.
8. **O SQL validado e seus parâmetros aparecem na resposta**, por transparência acadêmica.

## Alternativas consideradas

- **LLM gerar o SQL e validá-lo por AST** — rejeitada: o validador passaria a ser a única barreira contra SQL arbitrário, e a revisão mostrou que uma allowlist larga tem furos (I-1 a I-3); além disso o modelo erraria em silêncio as regras de grain (`SUM(qt_curso)`, filtro de 7 dígitos, `tp_dimensao`).
- **Validar o plano apenas contra a camada semântica** — rejeitada: um plano bem formado pode
  responder a uma pergunta diferente da que foi feita.
- **Explicação gerada pelo modelo** — rejeitada: texto do LLM pode trazer número ausente do resultado, linguagem temporal (só há 2024) ou causalidade; a explicação determinística não tem esse risco.
- **Nova tentativa ou resgate por regex** quando a resposta do modelo não é um plano válido —
  rejeitada: a resposta inválida é erro (502).

## Consequências

- O escopo da v1 fica restrito ao que o plano representa: 11 métricas diretas e duas razões por
  vaga, uma tabela por consulta, sem JOIN. Composições, decomposições, rótulo CINE, razão por
  habitante, `financiamento` e `reserva_vagas` saem como `nao_suportada`.
- Formulações que o contexto não classifica com segurança geram esclarecimento em vez de resposta
  ("com menos X"), e união e negação seguem não representadas.
- A qualidade da resposta depende da cobertura da recuperação léxica; o modelo não compensa lacuna
  da camada.
- O validador AST é defesa em profundidade: na revisão adversarial de 2026-10-07, três falhas
  (alias, nome de CTE e JOIN) foram encontradas e corrigidas, nenhuma alcançável pelo gerador.
- O comportamento com modelo real — aderência ao JSON Schema, taxa de plano inválido e robustez a
  injeção — permanece não medido.

Detalhe de implementação em [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) e
registro da fase no [devlog](../devlog/2026-10-07_fase-13-analista-ia-text-to-sql.md).
