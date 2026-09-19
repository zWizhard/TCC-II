# Commit inicial do repositório

## Objetivo
Iniciar o histórico versionado do projeto, após revisar o que entra e o que permanece fora do
versionamento, encerrando a pendência registrada em 2026-09-05, quando o repositório foi
inicializado sem nenhum commit.

## Trabalho realizado
Criado o commit inicial `a2e4dad` na branch `main`, com 62 arquivos e 6.442 inserções
(aproximadamente 493 KB). O conteúdo versionado abrange: `CLAUDE.md`; o diretório `.claude/`
(5 subagents, 6 skills, 5 hooks e `settings.json`); `docs/` com 7 ADRs, 10 devlogs, o dicionário
de dados, o documento de grain, a estratégia de JOIN e 7 CSVs de diagnóstico; o executor
`scripts/db/run_sql.py`; `pyproject.toml` e `uv.lock`; e os arquivos de configuração
`.gitignore`, `.gitattributes` e `.env.example`.

A identidade do autor (`Eduardo Gonçalves <eduardogoncalves0009@gmail.com>`) foi configurada
com `git config --local`, aplicando-se apenas a este repositório.

## Decisões técnicas/metodológicas
Identidade git definida em escopo local, e não global, para não alterar a configuração da
máquina fora do contexto do TCC. O commit foi feito diretamente em `main`: o repositório não
possuía histórico anterior, de modo que ramificar para o commit inicial não traria benefício.

Os dois CSVs brutos do Censo (536 MB) permanecem fora do versionamento, filtrados pelo
`.gitignore`; as evidências de auditoria em `docs/data/raw/diagnostics/` foram incluídas,
conforme a [ADR-0005](../decisions/ADR-0005-versionamento-das-evidencias-de-auditoria.md).

## Validação
`git check-ignore` confirmou que `.env` e os dois CSVs brutos estão ignorados, e `git ls-files`
não lista nenhum arquivo `.env`. Uma varredura por padrões de senha, token e chave de API sobre
os 62 arquivos não retornou ocorrências. Os CSVs de diagnóstico não contêm host nem endereço IP;
expõem apenas `PostgreSQL 17.9`, o database `iesb` e o usuário `data_iesb`, já públicos no
`CLAUDE.md`. O `.env.example` foi conferido e não contém valores reais. A árvore de trabalho
ficou limpa após o commit.

## Problemas/limitações
O git não tinha identidade configurada na máquina e o primeiro commit falhou até que isso fosse
resolvido. O repositório continua **sem remoto**, de modo que o histórico existe apenas
localmente e não há cópia externa.

> A confirmar: destino do repositório remoto (provedor e visibilidade) e momento do primeiro push.

## Próximo passo
Fase 3 — ETL versionado do PostgreSQL para o DuckDB
([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)).
