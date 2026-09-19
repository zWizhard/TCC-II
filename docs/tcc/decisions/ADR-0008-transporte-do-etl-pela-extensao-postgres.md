# ADR-0008 — Transporte do ETL pela extensão `postgres` do DuckDB

- **Data:** 2026-09-19
- **Status:** Aceita

## Contexto
A [ADR-0003](ADR-0003-camada-analitica-local-duckdb.md) definiu o DuckDB local como camada analítica
e exigiu um ETL que copie as tabelas do PostgreSQL IESB. A primeira implementação movia as linhas
pelo processo Python, via `executemany` da API do DuckDB.

As medições feitas nesta máquina em 2026-09-19 isolaram o gargalo na própria API Python: o motor do
DuckDB executa um `CREATE TABLE AS` de 5 milhões de linhas em 0,16 s e o Python puro percorre 5
milhões de iterações em 0,48 s, mas o `executemany` ficou entre duas e três ordens de grandeza
abaixo disso. Nem a máquina nem a rede eram o limite.

Linha por segundo não é comparável entre tabelas de larguras diferentes — o custo do `executemany`
acompanha o número de **valores** vinculados, não de linhas. As medições, na unidade comparável:

| Medição | Linhas/s | Células/s |
|---|---|---|
| Benchmark sintético, 2.561 × 82, em memória | 9,5 | 781 |
| Calibração, 50.000 × 2, em memória | 329 | 657 |
| Carga real de `inep_educacao_superior_ies`, 2.561 × 82 | 10,6 | **869** |
| Carga real de `municipio`, 5.599 × 7 | 102,7 | 719 |
| Carga real de `ibge_populacao_estimada`, 144.678 × 6 | 112,9 | **677** |

A projeção que condenou o caminho veio das **cargas reais**, não dos benchmarks sintéticos:
`inep_educacao_superior_cursos` tem 160.637.827 valores (720.349 × 223), e a faixa medida de
677 a 869 células/s projetava entre **65,9 h e 51,3 h**. A tabela nunca chegou a ser carregada por
esse caminho: a decisão foi tomada sobre a projeção, com as três tabelas pequenas já copiadas.

## Decisão
O transporte do dado passa a ser feito pela extensão `postgres` do DuckDB, com `ATTACH` do banco de
origem e `CREATE TABLE AS SELECT`. Python deixa de carregar linhas e permanece responsável por
metadados, contagens e conferência, usando `psycopg` com as travas da
[ADR-0002](ADR-0002-sessao-somente-leitura.md).

Como a extensão abre a própria conexão e não executa os `SET` da aplicação, a trava somente-leitura
viaja por `PGOPTIONS=-c default_transaction_read_only=on` somada a `READ_ONLY` no `ATTACH`. O ETL
não confia nessa configuração: mede-a no servidor com
`SELECT current_setting('transaction_read_only')` através de `postgres_query` e aborta se o valor
não for `'on'`. As credenciais chegam ao DuckDB apenas por variáveis de ambiente do libpq, nunca
dentro de string SQL — uma string de conexão em SQL apareceria em mensagens de erro, planos de
consulta e histórico.

## Alternativas consideradas
- **Manter `executemany` em Python.** Descartada pela projeção de 51,3 h a 65,9 h para `cursos`.
- **Exportar para CSV/Parquet intermediário e importar no DuckDB.** Adicionaria etapa, arquivo
  temporário com dado da origem e risco de conversão de tipos, sem ganho sobre a extensão.
- **Recriar as constraints `NOT NULL` na cópia.** Substituída por verificação: `CREATE TABLE AS` não
  transporta constraint, e o ETL mede zero linhas com NULL onde a origem declara `NOT NULL`.

## Consequências
- `cursos` passou de projeção de 51,3 h a 65,9 h para 31,2 s medidos; a base inteira é regerável em cerca de 35 s
  e ocupa 72,0 MB contra 609 MB na origem.
- A superfície de segurança muda: existe uma segunda conexão ao banco institucional, fora do pool da
  ADR-0002, cuja condição somente-leitura é verificada por medição no servidor a cada execução.
- A cópia não possui constraints; a integridade é assegurada por verificação no ETL e pelas somas de
  controle do validador (30 verificações, 0 falhas em 2026-09-19).
- O mapa explícito de tipos deixa de gerar DDL e passa a ser conferência da cópia contra a origem:
  divergência de classe aborta, diferença de largura é apenas registrada.
- Cria-se dependência da extensão `postgres` do DuckDB (1.5.5), que **não** vem no pacote Python nem
  no `uv.lock`: o ETL a obtém com `INSTALL postgres` / `LOAD postgres` a cada execução, o que exige
  internet na primeira vez numa máquina limpa. Registrada em
  [`../../ENVIRONMENT.md`](../../ENVIRONMENT.md).
