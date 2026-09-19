# ETL PostgreSQL → DuckDB — camada analítica local

Implementa a [ADR-0003](../tcc/decisions/ADR-0003-camada-analitica-local-duckdb.md).
Executado e validado em **2026-09-19**.

O PostgreSQL do IESB continua a **fonte oficial**. O arquivo local é camada de *serving*:
derivada, descartável e regerável em ~35 s. Dashboard, mapa e Analista IA consultam só ele.

## Como rodar

```
.venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py              # escopo inteiro
.venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py --recriar    # apaga e refaz, compacto
.venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py --tabelas municipio
.venv/Scripts/python.exe scripts/etl/validar_duckdb.py            # confere contra a origem
.venv/Scripts/python.exe scripts/etl/validar_duckdb.py --sem-origem
```

Ambos precisam de `dangerouslyDisableSandbox` no agente: a sandbox nega ao processo filho a
leitura do `.env`. Saída: `data/analytics/censo_2024.duckdb` (**72,0 MB**, não versionado).

O ETL faz `INSTALL postgres` / `LOAD postgres` sozinho a cada execução — não há passo de preparação.
Numa máquina limpa isso exige internet na primeira vez; ver
[`../ENVIRONMENT.md`](../ENVIRONMENT.md).

`--recriar` existe porque `CREATE OR REPLACE` não devolve ao arquivo o espaço das tabelas
substituídas: recarregar por cima levou o arquivo de 75,5 MB a 144,3 MB. Ele recusa
`--tabelas`, senão apagaria as outras três tabelas sem recarregá-las.

## O que a cópia é

Integral e literal: **todas** as linhas, **todas** as colunas, tipos da origem. Nenhuma
agregação, filtro, renomeação ou dedup. As 50 duplicatas de `ibge_populacao_estimada` e as
28 sentinelas de `municipio` são copiadas como estão — filtrar é trabalho da consulta.

Um ETL que "arruma" o dado destrói a possibilidade de auditar a cópia contra a origem.

| Tabela | Linhas | Colunas | Tempo |
|---|---|---|---|
| `inep_educacao_superior_ies` | 2.561 | 82 | 1,0 s |
| `municipio` | 5.599 | 7 | 0,9 s |
| `ibge_populacao_estimada` | 144.678 | 6 | 2,2 s |
| `inep_educacao_superior_cursos` | 720.349 | 223 | 31,2 s |

## Como o dado é transportado — e por que não é Python

Medido nesta máquina em **2026-09-19**:

O motor do DuckDB executa um `CREATE TABLE AS` de 5 milhões de linhas em **0,16 s**, e o Python puro
percorre 5 milhões de iterações em **0,48 s**. O gargalo é o *binding* de parâmetro da API Python —
não a rede, não a máquina.

**Linha/s não é comparável entre tabelas de larguras diferentes:** o custo do `executemany` acompanha
o número de **valores** vinculados. Na unidade comparável:

| Medição de `executemany` | Linhas/s | Células/s |
|---|---|---|
| Benchmark sintético, 2.561 × 82, em memória | 9,5 | 781 |
| Calibração, 50.000 × 2, em memória | 329 | 657 |
| Carga real de `inep_educacao_superior_ies`, 2.561 × 82 | 10,6 | **869** |
| Carga real de `municipio`, 5.599 × 7 | 102,7 | 719 |
| Carga real de `ibge_populacao_estimada`, 144.678 × 6 | 112,9 | **677** |

A projeção que condenou o caminho veio das **cargas reais**, não dos benchmarks sintéticos:
`cursos` tem 160.637.827 valores (720.349 × 223), e a faixa de 677 a 869 células/s projetava entre
**65,9 h e 51,3 h**. A tabela nunca chegou a ser carregada assim — a decisão foi tomada sobre a
projeção, com as três tabelas pequenas já copiadas.

A transferência passou a ser feita pela **extensão `postgres` do DuckDB**: `ATTACH` em modo
somente-leitura e `CREATE OR REPLACE TABLE … AS SELECT * FROM`. O dado vai do PostgreSQL ao
arquivo local em C++, sem passar pelo interpretador. `cursos` caiu para **31,2 s**.

O Python continua no processo, mas só para metadados, contagem e conferência, por uma segunda
conexão `psycopg` — a que já aplica as travas de sessão da [ADR-0002](../tcc/decisions/ADR-0002-sessao-somente-leitura.md).

### Somente-leitura na conexão da extensão

A extensão abre a própria conexão e **não executa os nossos `SET`**. A trava viaja como opção
de inicialização do libpq (`PGOPTIONS=-c default_transaction_read_only=on`), somada a
`READ_ONLY` no `ATTACH`, e é **conferida no servidor** antes de qualquer cópia:

```sql
SELECT current_setting('transaction_read_only')   -- precisa devolver 'on', ou o ETL aborta
```

Não se confia na configuração: mede-se. Basta o libpq ignorar a variável para o ETL passar a
rodar numa sessão gravável sem ninguém perceber.

**Credenciais nunca entram em string SQL.** Elas vão ao DuckDB apenas por variável de ambiente
do libpq, porque uma string de conexão dentro do `ATTACH` apareceria em mensagem de erro, em
plano de consulta e no histórico do DuckDB.

## O que é verificado

O ETL aborta, e a cópia é considerada inválida, se qualquer uma destas falhar:

1. **Linhas** — `COUNT(*)` da cópia = `COUNT(*)` da origem, por tabela.
2. **Classe de tipo** — o tipo de cada coluna na cópia é comparado com o esperado a partir do
   `information_schema` da origem (mapa explícito em `MAPA_TIPOS`). Mudança de **classe**
   aborta; largura diferente na mesma classe vira registro no manifesto.
   É o que protege `nu_ano_censo`: virando inteiro, todo filtro por `'2024'` devolveria vazio.
3. **Nulidade** — `CREATE TABLE AS` não carrega constraint, então a cópia não *impõe* o
   `NOT NULL` da origem. Em vez de recriar a constraint, mede-se: zero linhas com `NULL` em
   coluna que a origem declara `NOT NULL`. Constraint garante o futuro; a medição prova o
   presente, e é o presente que vira número do TCC.

O validador (`validar_duckdb.py`) acrescenta, contra a origem **ao vivo** e contra as
constantes medidas em 2026-09-05:

| Verificação | Resultado em 2026-09-19 |
|---|---|
| `SUM(qt_curso)` | 45.776 ✔ |
| `SUM(qt_mat)` | 10.227.266 ✔ |
| `SUM(qt_ing)` | 5.010.613 ✔ |
| `SUM(qt_conc)` | 1.333.988 ✔ |
| `COUNT(DISTINCT co_curso)` | 46.150 ✔ |
| Chave natural de `cursos` única | 720.349 = `COUNT(*)` ✔ |
| Chave natural de `ies` única | 2.561 ✔ |
| `nu_ano_censo` textual na cópia | VARCHAR ✔ |
| `ibge_populacao_estimada` | 50 linhas excedentes — **duplicata da origem, reproduzida** |

**30 verificações · 0 falhas.** Evidência versionada em
`docs/data/raw/diagnostics/2026-09-19_validacao_duckdb.csv`; registro da extração em
[`ETL_MANIFEST.json`](ETL_MANIFEST.json).

Código de saída ≠ 0 em qualquer `FALHA`. Tabela do catálogo ainda não carregada sai como
`PENDENTE` — nunca como sucesso.

## Ganho medido

As duas agregações que motivaram a ADR-0003, agora sobre a cópia local:

| Consulta | PostgreSQL IESB (2026-09-05) | DuckDB local (2026-09-19) | Ganho |
|---|---|---|---|
| Presenciais por município | 864 ms | **10,2 ms** | ~85× |
| EAD por município | 1.492 ms | **15,0 ms** | ~99× |

Ambas dentro do orçamento de ~200 ms de uma interação de mapa, com folga de uma ordem de
grandeza. O arquivo tem 72,0 MB contra os 609 MB da tabela de origem.

> Medido com o cache de página quente, melhor de 3. `regexp_full_match(co_municipio, '[0-9]{7}')`
> é o equivalente DuckDB do `~ '^[0-9]{7}$'` do PostgreSQL — o operador `~` não existe no DuckDB.

## Limites desta etapa

- **Retrato transversal de 2024.** A cópia é um instantâneo de uma edição fechada do Censo;
  não há série temporal. A interface precisa exibir a data de referência.
- A cópia **não corrige** nada: grain de `cursos`, contaminação por `'Cursos a distância'` em
  oito colunas, sentinelas de `municipio` e duplicatas de população continuam lá, como na
  origem. Ver [`DATA_GRAIN.md`](DATA_GRAIN.md) e [`JOIN_STRATEGY.md`](JOIN_STRATEGY.md).
- O dialeto SQL do Analista IA passa a ser **duckdb**, e a allowlist aponta para estas quatro
  tabelas locais — `SQL_ALLOWED_TABLES` no `.env.example` ainda lista só as duas do Censo.
- Nenhuma camada semântica, endpoint ou visualização foi criada. Esta etapa entrega o dado.

## Arquivos

| Arquivo | Papel |
|---|---|
| `scripts/db/conexao.py` | fonte única das travas de sessão da ADR-0002 |
| `scripts/etl/catalogo.py` | escopo, chaves naturais e somas de controle, como dado |
| `scripts/etl/pg_to_duckdb.py` | extração e conferências de fidelidade |
| `scripts/etl/validar_duckdb.py` | validação contra a origem e as constantes |
| `docs/data/ETL_MANIFEST.json` | data da extração, linhas e colunas por tabela |
