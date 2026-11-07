# Fase 15 — Validação final, preparação do TCC e remoção do Ollama

## Objetivo

Consolidar o sistema para a redação e a defesa do TCC, sem funcionalidades novas de grande porte, e
remover o Ollama do projeto por decisão do autor ("nunca era para ter utilizado ollama, exclua-o
completamente"). Produção segue com a AWS Bedrock ([ADR-0021](../decisions/ADR-0021-provedor-llm-via-aws-bedrock.md)).

## Trabalho realizado

- `api/analista/llm.py`: removido `ProvedorOllama`; permanecem `ProvedorLLM`, `PROMPT_DE_SISTEMA`
  (inalterado), `_FABRICAS` vazio e `ProvedorIndisponivel`. `api/config.py` passa a aceitar só
  `llm_provider: Literal["bedrock"]`; `.env.example` perdeu o bloco Ollama, `LLM_TEMPERATURE` e chaves
  `SQL_*` que nenhum código lia.
- `benchmark/`: removida a medição de modelos; o executor só valida o conjunto e roda o bloco de
  sistema, e o relatório ignora pastas sem `execucoes.jsonl`.
- Testes do Analista e do benchmark reescritos, com teste-guarda contra resquício de Ollama em `api/`
  e teste de provedor inválido falhando na configuração. Ferramental do agente ajustado.
- Documentos vivos atualizados (CLAUDE.md, `AI_ANALYST.md` com oito requisitos de aceitação da futura
  fábrica Bedrock, `ENVIRONMENT.md`, `RESULTADOS.md` §9–§10). Criados
  [FECHAMENTO_TECNICO.md](../FECHAMENTO_TECNICO.md) e [DEFESA.md](../DEFESA.md).

## Decisões técnicas/metodológicas

- A supersessão do Ollama foi registrada como "Atualização em 2026-11-06" na própria ADR-0021, sem ADR
  nova. Devlogs anteriores, ADR-0019/0020 e `PROTOCOLO.md` ficam como registro histórico.
- As rodadas P_* da Fase 14 permanecem como histórico, identificadas por `codigo_sha256`, e não são
  repetíveis com o código atual.
- Modelo Bedrock ainda não escolhido; o autor autorizou inferência quando houver acesso.
- Divergência do ETL (abaixo): não re-rodar.

## Validação

- Backend: pytest 1.051 aprovados (~25 s); ruff limpo; mypy limpo em `api/` e `benchmark/`.
- Frontend: ESLint 0 erros (6 avisos react-refresh), tsc limpo, vitest 101/101, build node-server.
- Hooks: 49 casos. Seis auditorias de `scripts/analise/` sem falha.
- `benchmark.relatorio` regerou `TABELAS.md` e seis CSVs idênticos byte a byte; prompt, schema e
  conjunto com o mesmo sha256 dos manifestos da Fase 14.
- Smoke test da API: endpoints 200 em 1,3–60 ms; nenhum gargalo comprovado, nada otimizado. Sem
  provedor, o Analista devolve 503 explicado, recusa, esclarecimento ou `nao_mapeada` conforme o caso.
- Varredura de segredos sem achados. Revisão independente sem regressão de segurança ou metodologia.

## Problemas/limitações

- Regressão da remoção, achada só no smoke test: perguntas resolvidas sem LLM recebiam 503. Corrigida
  com `ProvedorIndisponivel` (503 apenas ao chamar o modelo) e teste de regressão.
- `validar_duckdb.py` deu 29/30: a origem ganhou o ano 2023 em `ibge_populacao_estimada` (150.248 vs.
  144.678 linhas) após o ETL; 2024 é idêntico. Nenhum número muda, mas a premissa de origem estática
  não se sustenta. Evidência: `docs/data/raw/diagnostics/2026-11-06_validacao_duckdb.csv`.
- Sem provedor, o Analista não chega a `respondida` (crítico para a demonstração).
- Pendentes: 122 erros de mypy em `scripts/`, seis arquivos fora do `ruff format`, textos da landing,
  httpx como dependência de produção. O Ollama segue instalado na máquina (~37 GB).

Contagem de testes conferida: a coleta da cópia anterior à remoção dá 1.051 + 13
(`test_descobrir_bedrock.py`, não coletado na cópia por falta de `scripts/aws/`) = 1.064, o número
de 2026-10-19. A redução para 1.051 vem só da troca dos 20 testes do cliente Ollama (envelope,
falhas HTTP, travas M5, configuração `OLLAMA_*`) pelos testes do provedor indisponível, da
validação de `LLM_PROVIDER`, do teste-guarda e da regressão.

## Próximo passo

Commitar as Fases 7–15; login no Bedrock e escolha do modelo; decidir sobre a correção dos defeitos
do pipeline antes de medir o Bedrock (protocolo v2), a exclusão dos resultados históricos do Ollama e
sua desinstalação; piso de supressão; tela do Analista.
