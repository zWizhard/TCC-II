# Fase 5 — Base do backend e primeiros endpoints de indicadores

## Objetivo

Construir a base do backend (FastAPI + Pydantic) que servirá o dashboard, expondo inicialmente
apenas os indicadores diretos já validados na Fase 4 (Bloco A de
[INDICADORES.md](../methodology/INDICADORES.md)).

## Trabalho realizado

- Pacote `api/` (`config`, `db`, `erros`, `indicadores`, `consultas`, `schemas`, `rotas`, `main`)
  e suíte `tests/` (`conftest`, `test_indicadores`, `test_seguranca`).
- Dependências `fastapi`, `uvicorn`, `pydantic-settings` e, em desenvolvimento, `httpx`;
  configuração do pytest em `pyproject.toml`; variáveis `ANALYTICS_DUCKDB_PATH` e
  `API_QUERY_TIMEOUT_SECONDS` em `.env.example`.
- Estrutura, endpoints, regras e segurança descritos em
  [API.md](../architecture/API.md); os dois JOINs usados pela API registrados em
  [JOIN_STRATEGY.md](../../data/JOIN_STRATEGY.md).

## Decisões técnicas/metodológicas

A API consulta exclusivamente o DuckDB local ([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)),
não lê `.env` e não mantém credencial em processo. O cliente escolhe apenas enums de um catálogo
fechado de nove indicadores (IND-D-01..09); o servidor recusa com 422 explicativo as combinações
metodologicamente inválidas. A decisão está formalizada na
[ADR-0010](../decisions/ADR-0010-api-de-catalogo-fechado.md). Não se adotou ORM: as nove
agregações fixas são auditadas como SQL explícito. Base ausente, corrompida ou travada não
derruba a API (health `indisponivel`, 503).

Em apoio, o `data-engineer` mediu no DuckDB os literais de `tp_dimensao`, o tipo das colunas
territoriais (`co_regiao_ies` SMALLINT contra `co_regiao` VARCHAR, exigindo `CAST`), a relação
1:1 código↔nome e a identidade das 27 UFs nas duas tabelas. Os JOINs do mapa preservaram
linhas (3.551 e 698 antes e depois) e somas, com 0 órfãos e 0 sentinelas.

**Correção documental.** A regra 8 de INDICADORES.md afirmava que o filtro territorial descarta
41 matrículas. Sobre o universo total, descarta 2.580 (41 de polo sem município + 2.539 da
dimensão exterior); o valor 41 vale apenas dentro das dimensões com território. O total
territorializável (10.224.686) não se altera. DATA_DICTIONARY.md foi ajustado em conformidade.

## Validação

- 70 testes pytest aprovados: somas de controle nacionais dos nove indicadores; fechamento
  região/UF/município; São Paulo (3550308) com 859.026 matrículas presencial+polo; Brasília com
  63 IES; DF Pública com 5 IES e 44.532 matrículas presenciais; 18 combinações recusadas; travas da
  conexão; timeout; base ausente/corrompida; 404/405 no envelope de erro; slug não ecoado.
- ruff e mypy sem apontamentos. Com uvicorn, o mapa municipal de matrículas respondeu em ~45 ms.
- Revisão independente (`reviewer`) sem bloqueantes; os achados foram aplicados.

## Problemas/limitações

- `CREATE TEMP TABLE` é aceito pelo DuckDB mesmo em `read_only`. Não é explorável sem SQL livre,
  mas é requisito para o validador AST do Analista IA.
- No Windows, o ETL não grava com a API aberta; é preciso pará-la antes.
- `/docs` exposto (aceitável em uso local); deprecação do `httpx` no TestClient filtrada.
- Apenas o Bloco A é servido; derivados (Bloco B) e cache ausentes.

## Próximo passo

Frontend React + TypeScript mínimo (dashboard e mapa MapLibre) consumindo estes endpoints;
em seguida, os derivados IND-R-01 (JOIN com população) e IND-R-02.
