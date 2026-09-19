# ETL do PostgreSQL IESB para a camada analítica em DuckDB

## Objetivo
Implementar a camada analítica local prevista na [ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md),
copiando integral e literalmente as quatro tabelas do escopo para um arquivo DuckDB local, com
manifesto de extração e validação por somas de controle. Trata-se do primeiro código de produto do
projeto.

## Trabalho realizado
Criados `scripts/db/conexao.py` (fonte única das travas de sessão da ADR-0002, extraída de
`run_sql.py`), `scripts/etl/catalogo.py` (escopo, chaves naturais e somas de controle tratados como
dado), `scripts/etl/pg_to_duckdb.py`, `scripts/etl/validar_duckdb.py`, a documentação
`docs/data/ETL_DUCKDB.md`, o manifesto `docs/data/ETL_MANIFEST.json` e a evidência
`docs/data/raw/diagnostics/2026-09-19_validacao_duckdb.csv`. Alterados `scripts/db/run_sql.py`,
`pyproject.toml` (duckdb 1.5.5), `.gitignore` (`*.duckdb`, `*.duckdb.wal`, `data/analytics/`) e
`CLAUDE.md`.

O escopo, definido pelo autor, ficou nas quatro tabelas já auditadas em 2026-09-05:
`inep_educacao_superior_ies`, `inep_educacao_superior_cursos`, `municipio` e
`ibge_populacao_estimada`. Tabelas não auditadas (pib, densidade, unidade_federacao, regiao) foram
deliberadamente excluídas.

## Decisões técnicas/metodológicas
O transporte do dado passou a ser feito pela extensão `postgres` do DuckDB, e não por Python —
registrado em [ADR-0008](../decisions/ADR-0008-transporte-do-etl-pela-extensao-postgres.md).

`cursos` **nunca chegou a ser carregado** por `executemany`: a projeção que condenou esse caminho
veio da carga real das três tabelas pequenas, medida entre **677 e 869 células/s**. Aplicada aos
160.637.827 valores de `cursos` (720.349 × 223), a mais favorável das três já projetava **51,3 h**,
e a menos favorável, 65,9 h. Com a extensão, a tabela levou 31,2 s.

Linhas por segundo não são comparáveis entre tabelas de larguras diferentes e não devem ser citadas
soltas: **9,5 linhas/s** num benchmark sintético de 2.561 × 82 e **329 linhas/s** numa calibração de
50.000 × 2 são a mesma ordem de grandeza em células/s (781 e 657). A métrica comparável é célula/s.

Como `CREATE TABLE AS` não transporta constraint, optou-se por não recriar o `NOT NULL` da origem e
sim medi-lo: zero linhas com NULL nas 223 colunas de `cursos` e nas 81 de `ies`. O mapa explícito de
tipos deixou de gerar DDL e passou a servir de conferência da cópia contra a origem — divergência de
classe aborta, largura diferente é apenas registrada.

Corrigiu-se um número de trabalho: `inep_educacao_superior_ies` tem **82 colunas** (81 `NOT NULL`
mais `qt_tec_total`), não 81. A correção ocorreu antes de qualquer execução e nenhum documento do
repositório estava errado.

## Validação
Arquivo gerado: `data/analytics/censo_2024.duckdb`, 72,0 MB contra 609 MB na origem, regerável em
cerca de 35 s.

| Tabela | Linhas | Colunas | Tempo |
|---|---|---|---|
| ies | 2.561 | 82 | 1,0 s |
| municipio | 5.599 | 7 | 0,9 s |
| ibge_populacao_estimada | 144.678 | 6 | 2,2 s |
| cursos | 720.349 | 223 | 31,2 s |

Trinta verificações, zero falhas. As somas de controle batem com as constantes de 2026-09-05 e com a
origem ao vivo: `SUM(qt_curso)`=45.776, `SUM(qt_mat)`=10.227.266, `SUM(qt_ing)`=5.010.613,
`SUM(qt_conc)`=1.333.988, `COUNT(DISTINCT co_curso)`=46.150. A chave natural de `cursos` é única nas
720.349 linhas, `nu_ano_censo` permanece VARCHAR e as 50 duplicatas de `ibge_populacao_estimada` são
reproduzidas fielmente, marcadas como ESPERADO.

As duas agregações que motivaram a ADR-0003 caíram de 864 ms para 10,2 ms (presenciais por
município) e de 1.492 ms para 15,0 ms (EAD por município), uma ordem de grandeza abaixo do orçamento
de cerca de 200 ms do mapa.

`ruff check scripts/`, `mypy scripts/` e `ruff format --check` nos arquivos novos sem apontamentos;
autoteste dos hooks com 49 casos aprovados. Nenhum segredo versionado — o manifesto não contém host
nem usuário.

## Problemas/limitações
O repositório ainda não possui suíte de testes; a garantia desta etapa vem das somas de controle e
do lint. `scripts/db/run_sql.py` segue fora do formato do `ruff format`, situação anterior a esta
tarefa, já que o projeto não adota o formatador. A cópia não impõe constraints, apenas verifica que
os dados as satisfazem.

## Próximo passo
Atualizar `SQL_ALLOWED_TABLES` no `.env.example`, hoje restrito às duas tabelas do Censo, para as
quatro tabelas locais quando o Analista IA entrar em pauta; o dialeto SQLGlot passa a ser `duckdb`.
Nada de API, frontend, dashboard ou IA foi criado nesta etapa, por instrução.
