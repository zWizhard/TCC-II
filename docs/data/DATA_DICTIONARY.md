# Dicionário de dados — Censo da Educação Superior 2024

**Fonte verificada em 2026-09-05:** extrações completas em CSV fornecidas pelo autor
(UTF-8 sem BOM — confirmado byte a byte —, delimitador `,`, aspas `"`, cabeçalho no topo,
categóricas como rótulo). Origem: banco acadêmico **PostgreSQL** do IESB.

Escopo: Educação Superior. Nível espacial: município (código IBGE de 7 dígitos).

> **Proveniência.** A Fase 2 (2026-09-05) auditou as duas tabelas em duas etapas: as extrações
> completas — provadas idênticas ao banco em cinco somas de controle — deram contagem, grain,
> cardinalidade, categorias e formato dos identificadores; em seguida, **conexão direta ao
> PostgreSQL** (`scripts/db/run_sql.py`, sessão somente-leitura) fechou o que a exportação não
> carrega: tipo SQL das 305 colunas, nulidade declarada, padding e privilégios.
>
> **Não resta tipo inferido neste documento.** O que ainda não foi verificado está marcado
> `A confirmar` e listado em "Pendências que permanecem".

## Confirmado contra o banco (2026-09-05)

Servidor **PostgreSQL 17.9**, database `iesb`, schema `public`. Tabelas pertencem ao papel `iesb`;
a conta `data_iesb` tem **apenas `SELECT`** sobre elas.

**A auditoria dos CSVs bate exatamente com o banco** — os CSVs são as tabelas completas, não recortes:

| Verificação | Banco | CSV auditado |
|---|---|---|
| `ies` linhas (2024) | 2.561 | 2.561 ✔ |
| `cursos` linhas (2024) | 720.349 | 720.349 ✔ |
| `SUM(qt_curso)` | 45.776 | 45.776 ✔ |
| `SUM(qt_mat)` | 10.227.266 | 10.227.266 ✔ |
| `COUNT(DISTINCT co_curso)` | 46.150 | 46.150 ✔ |

### Tipos reais — divergem entre as tabelas

Inventário completo das **305 colunas** lido do `information_schema` em 2026-09-05
(evidência: `raw/diagnostics/2026-09-05_06a.csv`). Distribuição:

| Tabela | Tipos |
|---|---|
| `inep_educacao_superior_ies` (82) | `integer` 49 · `character varying` 13 · `character` 13 · `smallint` 7 |
| `inep_educacao_superior_cursos` (223) | `smallint` 182 · `character varying` 23 · `integer` 18 |

| Coluna | `inep_educacao_superior_ies` | `inep_educacao_superior_cursos` |
|---|---|---|
| `nu_ano_censo` | `character(4)` | `character varying(4)` |
| `co_ies` | **`smallint`** | **`integer`** |
| município | `co_municipio_ies` **`character(7)`** | `co_municipio` `character varying(18)` |
| UF | `co_uf_ies` `character(2)` · `sg_uf_ies` `varchar(2)` | `co_uf` / `sg_uf` `character varying(18)` |
| região | `co_regiao_ies` **`smallint`** | `co_regiao` `character varying(18)` |
| meso / microrregião | `co_mesorregiao_ies` / `co_microrregiao_ies` **`smallint`** | — |
| capital | `in_capital_ies` `character(3)` | `in_capital` `character varying(18)` |
| rede | `tp_rede` **`integer`** · **`ds_rede` `varchar(7)`** | `tp_rede` **`character varying(7)`** |
| `co_curso` | — | `integer` |
| `qt_curso` / `qt_mat` | — | `smallint` / `integer` |
| `sg_ies` / `nu_cep_ies` | `varchar(20)` / `character(12)` | — |

⚠️ **`nu_ano_censo` é texto nos dois lados** — filtrar com `'2024'`, nunca `2024`.
⚠️ **`tp_rede` é `integer` em IES e `varchar` em cursos** — a divergência é do schema, não da exportação.

### ✅ NÃO há padding em `co_municipio_ies` — `btrim()` é desnecessário

Correção de 2026-09-05. A documentação anterior afirmava que `co_municipio_ies`, por ser `CHAR`,
vinha "preenchido com espaços à direita" e exigia `btrim()` antes de comparar. **Isso está errado.**

O tipo é **`character(7)`** e o conteúdo tem **exatamente 7 caracteres**: os comprimentos distintos
são `7` tanto no valor bruto quanto após `btrim()`. Não há espaço a aparar. Do mesmo modo,
`nu_ano_censo` é `character(4)` com 4 caracteres, e o filtro `nu_ano_censo = '2024'` casa as
**2.561 linhas** sem nenhuma normalização.

`btrim()` continua inofensivo, mas não é requisito e não deve ser apresentado como tal.

> A única coluna onde o padding é real é **`nu_cep_ies`, `character(12)`** — um CEP tem 8–9
> caracteres, então sobra espaço. O projeto não usa essa coluna; se vier a usar, aí sim `btrim()`.

### O schema foi dimensionado para caber `'Cursos a distância'`

Em `cursos`, as colunas `co_municipio`, `no_municipio`, `co_uf`, `sg_uf`, `no_uf`, `co_regiao`,
`no_regiao` e `in_capital` são todas **`character varying(18)`** — e `'Cursos a distância'` tem
**exatamente 18 caracteres**. Até `sg_uf`, que guardaria 2 caracteres, é `varchar(18)`.

A contaminação é, portanto, **estrutural e intencional na origem**, não acidente de exportação.

### Nulidade — declarada no schema

| Tabela | Colunas que aceitam `NULL` |
|---|---|
| `inep_educacao_superior_cursos` | **0 de 223** — todas `NOT NULL` |
| `inep_educacao_superior_ies` | **1 de 82** — só `qt_tec_total` (e tem 0 nulos de fato) |

Consequência: **não existe `NULL` nestas tabelas**. Os 459 `sg_ies` e 26 `nu_cep_ies` "vazios"
são **string vazia**, garantida pelo schema — nunca `NULL`. Filtrar com `IS NULL` não encontra nada;
o teste correto é `btrim(coluna) = ''`.

### Índices — praticamente inexistentes

Só existe **um** índice em todo o conjunto:
`pk_inep_educacao_superior_ies` UNIQUE em `(nu_ano_censo, co_ies)`.

**`inep_educacao_superior_cursos` não tem nenhum índice** — 720.349 linhas × 223 colunas.
Todo filtro por ano, UF, município ou dimensão faz *sequential scan* da tabela inteira.
Como `data_iesb` só tem `SELECT` e não é dona da tabela, **não é possível criar índices**.
Isso tem consequência direta de arquitetura — ver `docs/ENVIRONMENT.md`.

### Catálogo — o universo de Educação Superior tem exatamente duas tabelas

Levantado no catálogo do banco em 2026-09-05
(evidência: `raw/diagnostics/2026-09-05_01_diagnostico.csv`).

| Item | Verificado |
|---|---|
| Tecnologia | PostgreSQL 17.9 (Linux x86_64) |
| Database | `iesb` |
| Acesso | login/senha nativo; DBeaver (JDBC) e `psycopg` na aplicação |
| Usuário | `data_iesb` — `rolsuper=false`, `rolcreaterole=false` |
| Schemas com tabelas | `public` (a grande maioria), `Procuradoria`, `SUS_SINAN`, `aurya`, `dataiesb-aurya`, `dataiesb_site`, `kafka` |
| Dono das tabelas do Censo | papel `iesb` (não `data_iesb`) |
| Permissão nas duas tabelas | `SELECT` = true · `INSERT`/`UPDATE`/`DELETE` = false |
| Read-only na sessão | `SET default_transaction_read_only = on` aceito ([ADR-0002](../tcc/decisions/ADR-0002-sessao-somente-leitura.md)) |

**Todas as tabelas cujo nome começa por `inep`:**

| Tabela | Escopo |
|---|---|
| **`inep_educacao_superior_ies`** | ✅ **Educação Superior — no escopo** |
| **`inep_educacao_superior_cursos`** | ✅ **Educação Superior — no escopo** |
| `inep_censo_escolar` | ❌ Educação Básica |
| `inep_censo_escolar_curso_tecnico` | ❌ Educação Básica |
| `inep_censo_escolar_docente` | ❌ Educação Básica |
| `inep_censo_escolar_gestor` | ❌ Educação Básica |
| `inep_censo_escolar_matricula` | ❌ Educação Básica |
| `inep_censo_escolar_turmas` | ❌ Educação Básica |
| `inep_escola_coordenadas_novas` | ❌ Educação Básica |

> **Não existe tabela de docentes, de alunos nem de mantenedoras da Educação Superior** neste banco.
> Corpo docente e técnico só existem como colunas agregadas `qt_doc_*` / `qt_tec_*` dentro de
> `inep_educacao_superior_ies`, no grain da IES — nunca no grain da pessoa. Igualmente,
> `censo_escolar_2024`, `educacao_basica`, `enem_2024`, `ed_enem_2024_*` são Educação Básica
> ou ENEM e estão **fora do escopo**.

---

## `inep_educacao_superior_ies` — Instituições

- **Finalidade:** cadastro das IES, com localização, natureza jurídica, corpo docente e técnico, infraestrutura de biblioteca.
- **Grain:** uma linha = **uma IES no ano do censo**.
- **Chave:** `co_ies` (única no arquivo). Chave completa: `(nu_ano_censo, co_ies)`.
- **Volume:** 2.561 linhas · 82 colunas · 1,2 MB.
- **Período:** **somente 2024** (100% das linhas).

### Colunas-chave e dimensões

Tipos lidos do `information_schema` em 2026-09-05. Nada nesta tabela é inferido.

| Coluna | Tipo | Distintos | Observação |
|---|---|---|---|
| `nu_ano_censo` | `character(4)` | 1 | `'2024'` em 100% das linhas; sem padding |
| `co_ies` | `smallint` | 2.561 | **PK.** 2.561 distintos = 2.561 linhas, 0 nulos |
| `no_ies` | `character varying` | 2.547 | ⚠️ **não é chave** — 14 nomes repetidos |
| `sg_ies` | `character varying(20)` | 1.826 | ⚠️ **vazia em 459 linhas (17,92%)** — string vazia, nunca `NULL` |
| `co_municipio_ies` | **`character(7)`** | 698 | **código IBGE.** 7 caracteres exatos, sem padding, 0 nulos |
| `no_municipio_ies` | `character varying` | **695** | ⚠️ 3 nomes a menos que códigos: `Valença`, `Cascavel`, `Redenção` são homônimos entre UFs |
| `co_uf_ies` / `sg_uf_ies` | `character(2)` / `varchar(2)` | 27 / 27 | hierarquia territorial |
| `co_regiao_ies` | **`smallint`** | 5 | `1`=Norte · `2`=Nordeste · `3`=Sudeste · `4`=Sul · `5`=Centro-Oeste |
| `co_mesorregiao_ies` / `no_mesorregiao_ies` | `smallint` / `varchar` | **15 / 131** | ⚠️ ver alerta abaixo |
| `co_microrregiao_ies` / `no_microrregiao_ies` | `smallint` / `varchar` | **65 / 382** | ⚠️ ver alerta abaixo |
| `in_capital_ies` | `character(3)` | 2 | `'Sim'` 919 · `'Não'` 1.642 |
| `co_mantenedora` / `no_mantenedora` | `integer` / `varchar` | 1.755 / 1.741 | mantenedora da IES; o nome também tem homônimos |
| `nu_cep_ies` | `character(12)` | 2.255 | ⚠️ **único caso de padding real**; vazio em 26 linhas |
| `ds_endereco_ies` | `character varying` | — | endereço textual; não usado no projeto |

### ⚠️ `co_mesorregiao_ies` e `co_microrregiao_ies` NÃO são códigos nacionais

Confirmado no banco em 2026-09-05. Ambas são `smallint`:

| Nível | Códigos distintos | Nomes distintos | `(co_uf_ies, código)` |
|---|---|---|---|
| Mesorregião | **15** | 131 | **131** ✅ |
| Microrregião | **65** | 382 | **383** ⚠️ |

O código é **local à UF**, não nacional. **Agrupar por `co_mesorregiao_ies` sozinho funde
mesorregiões de estados diferentes** e devolve número errado sem gerar erro de execução.
A chave correta é **`(co_uf_ies, co_mesorregiao_ies)`**, que reproduz exatamente os 131 nomes.

⚠️ Na microrregião nem o par resolve: há **383 pares para 382 nomes**, ou seja, duas microrregiões
de UFs diferentes compartilham o mesmo nome. Agrupar microrregião **por nome** funde as duas;
use sempre o par `(co_uf_ies, co_microrregiao_ies)` como identidade.

### `ds_rede` — resolve a incompatibilidade de `tp_rede` entre as tabelas

A tabela de IES tem **duas** colunas de rede, e a segunda não estava documentada:

| `tp_rede` | `ds_rede` | Linhas |
|---|---|---|
| `1` | `Pública` | 317 |
| `2` | `Privada` | 2.244 |

Confirmado no banco em 2026-09-05: o mapeamento é **1:1 perfeito** (nenhum par fora desses dois),
e `cursos.tp_rede` tem exatamente os dois rótulos `Privada | Pública`. As duas colunas são
`character varying(7)`. Consequência prática: comparar rede entre as tabelas deve usar
**`ies.ds_rede` ↔ `cursos.tp_rede`**, sem tradução manual de código.

> ⚠️ A ressalva permanece: `ds_rede = 'Pública'` inclui as 28 IES de categoria **Especial**,
> exatamente como `tp_rede = '1'`. Para "pública" no sentido estrito, filtrar por
> `tp_categoria_administrativa`.

### `in_comunitaria` e `in_confessional` — codificação diferente dos demais `in_*`

| Coluna | Valores | Linhas |
|---|---|---|
| `in_comunitaria` | `'0'` / `'1'` | 2.475 / 86 |
| `in_confessional` | `'0'` / `'1'` | 2.505 / 56 |
| `in_capital_ies` | `'Sim'` / `'Não'` | 919 / 1.642 |

⚠️ Colunas do mesmo prefixo `in_` **não têm codificação uniforme**: umas são `0`/`1`, outra é
`Sim`/`Não`. Não escrever filtro genérico por prefixo.

### Categorias verificadas

**`tp_organizacao_academica`** (rótulo)

| Valor | Freq. |
|---|---|
| Faculdade | 1.897 |
| Centro Universitário | 417 |
| **Universidade** | **206** |
| Instituto Federal de Educação, Ciência e Tecnologia | 39 |
| Centro Federal de Educação Tecnológica | 2 |

**`tp_categoria_administrativa`** (rótulo)

| Valor | Freq. |
|---|---|
| Privada com fins lucrativos | 1.486 |
| Privada sem fins lucrativos | 758 |
| Pública Estadual | 139 |
| Pública Federal | 122 |
| Especial | 28 |
| Pública Municipal | 28 |

**`tp_rede`** — ⚠️ **neste arquivo vem como código, não rótulo:** `'1'` (317) e `'2'` (2.244).
Cruzamento com `tp_categoria_administrativa` resolve o significado sem ambiguidade:

- `'2'` = as duas categorias privadas (1.486 + 758 = **2.244** ✓)
- `'1'` = Pública Federal + Estadual + Municipal + **Especial** (122+139+28+28 = **317** ✓)

> Atenção: `tp_rede = '1'` **não é sinônimo de "pública"** — inclui as 28 IES de categoria
> *Especial*. Para "pública" no sentido estrito, filtrar por `tp_categoria_administrativa`.

### Métricas (somas de controle, 2024)

`qt_doc_total` = 374.501 · `qt_tec_total` = 350.752.
Famílias de colunas: `qt_doc_ex_*` (docentes por titulação, faixa etária, cor/raça, regime),
`qt_tec_*` (técnicos por escolaridade e sexo), `in_*` de infraestrutura de biblioteca.

⚠️ **`qt_doc_total` e `qt_doc_exe` são idênticas** — mesmo valor nas **2.561 linhas**, soma 374.501
nas duas. São a mesma medida sob dois nomes. **Usar apenas `qt_doc_total`**; somar as duas
duplica o total de docentes. **A confirmar no banco** (script `06`, bloco B8).

**Nulos (verificado no CSV):** das 82 colunas, só duas têm valor vazio — `sg_ies` (459 · 17,92%)
e `nu_cep_ies` (26 · 1,02%). As 80 restantes estão preenchidas em 100% das linhas.
Se o vazio é `NULL` ou string vazia no banco é distinção que a exportação apaga —
**A confirmar** (script `06`, bloco B1).

---

## `inep_educacao_superior_cursos` — Cursos

- **Finalidade:** oferta de cursos de graduação, com vagas, inscritos, ingressantes, matrículas, concluintes, financiamento, reserva de vagas e situação.
- **Grain:** uma linha = **curso × município × dimensão de oferta**. **Não é uma linha por curso.**
- **Volume:** 720.349 linhas · 223 colunas · **560 MB**.
- **Período:** **somente 2024**.

### Chaves

| Coluna | Observação |
|---|---|
| `co_curso` | 46.150 distintos. **Determina a IES:** `0` cursos aparecem com mais de um `co_ies` (verificado linha a linha) — logo `co_ies` é redundante na chave |
| `co_ies` | 2.561 distintos — casa exatamente com o arquivo de IES |
| `co_municipio` | ⚠️ **coluna poluída** — ver abaixo |
| **`(nu_ano_censo, co_curso, co_municipio, tp_dimensao)`** | ✅ **chave natural exata: 720.349 combinações distintas = `COUNT(*)`.** Nenhuma linha duplicada |

A chave de 4 partes fecha o grain sem sobra. A documentação anterior parava em
`(ano, co_curso, co_municipio)` = 719.897 e deixava as 452 sobras sem explicação fechada:
elas se resolvem ao acrescentar `tp_dimensao`. **A confirmar no banco** (script `06`, bloco B5).

### Colunas de identificação e dimensão — cardinalidade verificada

| Coluna | Distintos | Observação |
|---|---|---|
| `no_curso` | **1.497** | nome do curso; 46.150 cursos compartilham 1.497 nomes — **não é identificador** |
| `co_cine_rotulo` / `no_cine_rotulo` | 353 / 353 | 1:1 |
| `co_cine_area_geral` / `no_cine_area_geral` | 11 / 11 | códigos `'0'` a `'10'` |
| `co_cine_area_especifica` | 39 | |
| `co_cine_area_detalhada` | 89 | |
| `in_gratuito` | 2 | `'Não'` 701.299 · `'Sim'` 19.050 |
| `in_comunitaria` | 2 | `'0'` 705.591 · `'1'` 14.758 — mesma codificação `0`/`1` da tabela de IES |
| `in_confessional` | 2 | `'0'` 712.852 · `'1'` 7.497 |

`tp_categoria_administrativa` usa em cursos **os mesmos 6 rótulos** da tabela de IES — essa
coluna é comparável entre as duas tabelas, ao contrário de `tp_rede`.

### ⚠️ A contaminação atinge TODA a hierarquia territorial, não só `co_municipio`

Correção da Fase 2 — a documentação anterior citava apenas `co_municipio` e `in_capital`.
O literal `'Cursos a distância'` ocupa **as mesmas 11.778 linhas em oito colunas**:

| Coluna | Valores válidos | Linhas com `'Cursos a distância'` | Distintos (incl. o literal) |
|---|---|---|---|
| `co_municipio` | código IBGE, 7 dígitos, 708.571 linhas | **11.778** | 3.552 (= 3.551 + 1) |
| `no_municipio` | nome do município | **11.778** | 3.429 ⚠️ |
| `co_uf` | 2 dígitos, 708.571 linhas | **11.778** | 28 (= 27 + 1) |
| `sg_uf` | sigla da UF | **11.778** | 28 |
| `no_uf` | nome da UF | **11.778** | 28 |
| `co_regiao` | 1 dígito, 708.571 linhas | **11.778** | 6 (= 5 + 1) |
| `no_regiao` | nome da região | **11.778** | 6 |
| `in_capital` | `'Sim'` 73.400 · `'Não'` 635.171 | **11.778** | 3 |

Consequência: **qualquer agregação por UF ou região tem o mesmo problema que a agregação
municipal** — não apenas o mapa. Um `GROUP BY sg_uf` sem filtro devolve **28 "UFs"**, com uma
28ª linha fantasma somando 11.778 registros de EAD sem território.

**Filtrar antes de qualquer agregação ou JOIN territorial**, em qualquer nível:
`co_municipio ~ '^[0-9]{7}$'` (ou o equivalente para `co_uf` / `co_regiao`).

> ⚠️ `no_municipio` tem **3.429 nomes distintos para 3.551 códigos** — ~122 municípios são
> homônimos entre UFs. **Nunca agrupar nem juntar por nome de município**; sempre por código.

**Nulos (verificado no CSV):** **nenhuma** das 223 colunas tem valor vazio — 720.349 linhas
preenchidas em 100% em todas elas. Se há `NULL` real no banco é distinção que a exportação
apaga — **A confirmar** (script `06`, bloco B3).

### `tp_dimensao` — a coluna mais importante da tabela

| Valor | Linhas | Σ `qt_mat` | Σ `qt_curso` | Linhas sem território |
|---|---|---|---|---|
| Cursos a distância ofertados no Brasil | 673.756 | 5.186.852 | **0** | **9** ⚠️ |
| Cursos presenciais ofertados no Brasil | 34.824 | 5.037.875 | 34.479 | 0 |
| Cursos a distância com dimensão de dados somente a nível Brasil | 11.319 | **0** | 11.297 | **11.319** (todas) |
| Cursos a distância ofertados por instituições brasileiras no exterior | 450 | 2.539 | 0 | **450** (todas) |
| **Total** | **720.349** | **10.227.266** ✓ | **45.776** ✓ | **11.778** |

**93,5% das linhas são EAD replicadas por município de polo.** Cursos presenciais têm
exatamente **1 linha por curso** (34.824 cursos × 1 linha). A explosão de linhas é inteiramente EAD.

**De onde vêm as 11.778 linhas sem território:** 11.319 da dimensão "somente a nível Brasil"
+ 450 da dimensão "no exterior" + **9 linhas da dimensão principal de EAD por polo**.

As 9 foram investigadas no banco (2026-09-05): são **9 cursos de 9 IES distintas**, somando
**41 matrículas** e `qt_curso = 0`. Todos os 9 cursos **também têm linhas com município válido**
(291 no total) — são, portanto, um resíduo de matrícula sem polo identificado, não cursos
inteiros perdidos.

**Consequência prática:** filtrar `tp_dimensao` **não** elimina essas 9 linhas — é preciso filtrar
a coluna territorial. Dentro das dimensões com território, o filtro descarta **41 matrículas**;
sobre o universo total descarta **2.580** (as 41 + 2.539 da dimensão "exterior", sem município
em nenhuma linha — medido em 2026-09-26). Irrelevante para o número, mas o total do mapa não
fecha com o total nacional, e a diferença deve ser declarada em vez de parecer erro.

**`tp_dimensao` determina `tp_modalidade_ensino`** — as três dimensões de EAD dão sempre
`'Curso a distância'` e a presencial sempre `'Presencial'`, sem uma única exceção nas 720.349
linhas. A modalidade é redundante; `tp_dimensao` é a coluna com informação real, porque separa
oferta física, polo de EAD, agregado nacional e oferta no exterior — distinção que
`tp_modalidade_ensino` não faz.

### Semântica das métricas — verificada

**As métricas são DISTRIBUÍDAS entre os municípios, não replicadas.** Comprovado por inspeção:
para o curso `1576073` (695 linhas), `qt_mat` assume valores distintos por município
(2, 5, 0, 0, 0, 1…). Portanto **`SUM(qt_mat)` está correto e não infla**.

`qt_curso` é **0** em todas as linhas de EAD por polo. Ele só marca a existência do curso nas
linhas presenciais e nas de dimensão "somente a nível Brasil". Consequência direta:

| Objetivo | Correto | **Errado** |
|---|---|---|
| Contar cursos | `SUM(qt_curso)` = 45.776 | `COUNT(*)` = 720.349 |
| Contar cursos | — | `COUNT(DISTINCT co_curso)` = 46.150 (≠ 45.776) |
| Cursos por município | `SUM(qt_curso)` | `COUNT(DISTINCT co_curso)` → conta o mesmo curso EAD em cada polo |

Somas de controle nacionais 2024: `qt_mat` = **10.227.266** · `qt_ing` = 5.010.613 ·
`qt_conc` = 1.333.988 · `qt_curso` = 45.776.

### Categorias verificadas

| Coluna | Valores |
|---|---|
| `tp_modalidade_ensino` | `Curso a distância` 685.525 · `Presencial` 34.824 |
| `tp_grau_academico` | `Tecnológico` 338.574 · `Bacharelado` 243.210 · `Licenciatura` 136.519 · `Não aplicável` 2.046 |
| `tp_nivel_academico` | `Graduação` 720.345 · `Sequencial de Formação Específica` 4 |
| `tp_organizacao_academica` | `Centro Universitário` 370.724 · `Universidade` 323.102 · `Faculdade` 23.985 · IF 2.474 · CEFET 64 |
| `tp_rede` | ⚠️ **rótulos** aqui: `Privada` 700.198 · `Pública` 20.151 |

> ⚠️ **Inconsistência entre os dois arquivos:** `tp_rede` vem como **código** (`'1'`/`'2'`) em IES
> e como **rótulo** (`Pública`/`Privada`) em cursos. Nunca comparar as duas colunas diretamente.

### Classificação CINE

`co_cine_rotulo`/`no_cine_rotulo`, e a hierarquia `area_geral` → `area_especifica` → `area_detalhada`,
cada uma com par código/nome. Sem nulos nas colunas-chave verificadas.

### Famílias de métricas

`qt_vg_*` vagas · `qt_inscrito_*`/`qt_insc_*` inscritos · `qt_ing_*` ingressantes ·
`qt_mat_*` matrículas · `qt_conc_*` concluintes — cada uma desdobrada por sexo, turno, faixa etária,
cor/raça, nacionalidade, deficiência, financiamento (FIES, ProUni), reserva de vagas e
procedência escolar. `qt_sit_*` cobre trancamento, desvinculação, transferência e óbito.

---

---

## Tabelas auxiliares — leitura confirmada (2026-09-05)

`data_iesb` tem `SELECT = true` nas oito tabelas abaixo. Todas usam **código municipal do IBGE**,
o que dispensa download externo para população, área e PIB.

| Tabela | Colunas relevantes | Uso no projeto |
|---|---|---|
| **`municipio`** | `codigo_municipio_dv`, `codigo_municipio`, `nome_municipio`, `cd_uf`, `municipio_capital`, **`longitude`**, **`latitude`** | **Coordenadas para pontos e heatmap** — sem depender de GeoJSON externo |
| **`ibge_populacao_estimada`** | `ano`, **`cod_municipio` (6 dígitos!)**, `populacao`, `uf` | **Denominador do coroplético.** Anos 2000–2022, 2024, 2025, 2026 (**sem 2023**). Em 2026: 5.568 municípios, 214.131.050 hab. |
| `ibge_munic_2024` | `codigo_municipio_dv`, `populacao`, `faixa_pop`, `regiao` + ~250 colunas `mreh*`/`mtic*` (pesquisa MUNIC) | População alternativa; MUNIC fora do escopo |
| `ibge_densidade_populacional_area_municipios_2010` | `codigo_municipio_dv`, `area_km2`, `densidade_populacional` | Área para métricas por km² |
| `pib_municipios` | `ano_pib`, `codigo_municipio_dv`, `vl_pib`, `vl_pib_per_capta` | Contexto socioeconômico |
| `IBGE_agregados_por_municipio_basico` | `cd_mun`, `nm_mun`, `cd_uf`, `nm_uf`, `v0001`…`v0007` | Agregados do Censo 2022 — colunas `v*` **a decodificar** |
| `regiao` | `cd_regiao`, `nome_regiao` | Hierarquia territorial |
| `unidade_federacao` | `cd_uf`, `sigla_uf`, `nome_uf`, `cd_regiao` | Hierarquia territorial |

### `municipio` — verificado (2026-09-05)

**5.599 linhas**, 5.599 códigos distintos. O `27` do catálogo era estatística podre, como suspeitado.

| Coluna | Dígitos | Exemplo | Casa com o Censo? |
|---|---|---|---|
| `codigo_municipio_dv` | **7** | `1100015` | ✅ **0 órfãos** — é a chave |
| `codigo_municipio` | 6 | `110001` | ❌ **3.551 órfãos** (todos) |

Sede de IES → `municipio`: **0 órfãos** também. As duas tabelas do Censo casam perfeitamente.

**Coordenadas:** `latitude`/`longitude` preenchidas em **100%** das linhas (0 nulos).
Amostra coerente: `Abadia de Goiás (-16.7588120, -49.4405480)`.

### ✅ Resolvido: `municipio` tem 28 linhas que NÃO são municípios

As duas pendências abertas — as coordenadas fora do Brasil e o excedente de ~29 registros — têm a
**mesma causa**, identificada no banco em 2026-09-05.

| Grupo | Linhas | Código | Exemplo |
|---|---|---|---|
| `Município Ignorado - <UF>` | **26** | termina em `00000` | `3500000 = Município Ignorado - SP` |
| `MUNICIPIO IGNORADO - EXTERIOR` | 1 | `9900000` | coordenada de **Paris** (48,86 / 2,34) |
| `Exterior ou EAD` | 1 | `9999999` | coordenada (−38,67 / −18,00) |
| **Municípios e equivalentes** | **5.571** | prefixo `1`–`5` | — |
| **Total da tabela** | **5.599** | | |

As **5.571** unidades territoriais de nível municipal são o universo real da tabela. O "excedente"
era uma linha-sentinela de *município ignorado* por UF (26 UFs — Rondônia não tem a sua), mais as
duas de exterior. As coordenadas absurdas eram só as das sentinelas de exterior.

> ⚠️ **Correção de denominação, 2026-09-19 (Fase 4).** Este bloco dizia "Municípios reais" e
> "5.571 é exatamente a contagem oficial". **O número está certo; a palavra estava errada.**
> Verificado na Fase 4: excluindo `2605459` restam **5.570** — Fernando de Noronha é
> **distrito estadual de Pernambuco**, não município, e por isso PE aparece na tabela com 185
> unidades. O Distrito Federal entra com uma única unidade (Brasília, `5300108`).
>
> **5.571 = 5.570 municípios + Fernando de Noronha.** A denominação correta é
> **"municípios e equivalentes"** ou "unidades territoriais de nível municipal"; escrever
> "5.571 municípios" é incorreto. Ver
> [`../tcc/methodology/INDICADORES.md`](../tcc/methodology/INDICADORES.md) (IND-R-02).

Filtro para uso como denominador ou para plotagem:

```sql
WHERE right(codigo_municipio_dv::text, 5) <> '00000'
  AND codigo_municipio_dv::text <> '9999999'
```

✅ **O Censo não usa nenhuma sentinela:** `0` IES sediadas e `0` linhas de cursos apontam para
esses códigos. O mapa não herda o problema — mas **o denominador sim**, se a tabela for contada
inteira. O universo do denominador é **5.571 municípios e equivalentes** (5.570 municípios mais
Fernando de Noronha) — ou outro critério, desde que declarado.

### ⚠️ `ibge_populacao_estimada` tem 50 pares (ano, município) **duplicados e divergentes**

Verificado no banco em 2026-09-05: 144.678 linhas para **144.628** pares `(ano, cod_municipio)`
distintos. São **50 duplicatas — e todas as 50 têm população divergente**, não repetida.

Amostra do conflito:

| Município | Ano | Valores concorrentes |
|---|---|---|
| `150680` | 2006 | **276.074** vs **2.606** |
| `251380` | 2013 | 4.612 vs 10.423 |
| `210920` | 2000 | 8.162 vs 6.723 |

A diferença chega a **100×**. Não há, no banco, critério para decidir qual linha vale.

**Anos afetados: 2000–2009 e 2011–2020.** Os anos de interesse do projeto — **2024**, além de
2022, 2025 e 2026 — **não têm duplicata**. Como o Censo disponível é só 2024, o denominador do
coroplético está a salvo, mas o JOIN **precisa** filtrar o ano:

```sql
JOIN ibge_populacao_estimada p ON ... AND p.ano = 2024
```

Sem o filtro de ano, o JOIN multiplica linhas *e* mistura valores contraditórios.
Qual dos dois valores é o correto nos anos afetados: **A confirmar** (só importa se o projeto
vier a usar série histórica de população, o que hoje está fora de escopo).

### Tamanho físico das tabelas (verificado)

| Tabela | Tamanho | Linhas (estimativa do catálogo) |
|---|---|---|
| `inep_educacao_superior_cursos` | **609 MB** | 718.906 (real: 720.349) |
| `pib_municipios` | 10 MB | 77.965 |
| `ibge_populacao_estimada` | 9,8 MB | 144.678 |
| `inep_educacao_superior_ies` | 1,6 MB | 2.561 |
| `municipio` | 800 kB | 27 ⚠️ |

⚠️ `n_live_tup` vem de `pg_stat_user_tables` e é **estimativa**, não contagem — repare que `cursos`
aparece com 718.906 quando o valor real é 720.349. O `27` de `municipio` é quase certamente
estatística desatualizada (800 kB é compatível com ~5.570 municípios), mas **precisa de
`COUNT(*)` real** antes de qualquer conclusão sobre a cobertura das coordenadas.

> **Não há geometria de polígono** em nenhuma dessas tabelas — só ponto (lat/long).
> Um coroplético municipal ainda exige a malha do IBGE (GeoJSON, download gratuito).
> Pontos, clusters e heatmap já são possíveis apenas com o banco.

### ⚠️ As auxiliares NÃO usam todas o mesmo formato de código

| Origem | Coluna | Dígitos |
|---|---|---|
| Censo (`ies`, `cursos`) | `co_municipio_ies` / `co_municipio` | **7** |
| `municipio` | `codigo_municipio_dv` / `codigo_municipio` | **7 e 6** (tem as duas) |
| **`ibge_populacao_estimada`** | `cod_municipio` | **6** ⚠️ |
| `pib_municipios`, `ibge_munic_2024`, densidade | `codigo_municipio_dv` | 7 (a confirmar) |

Juntar população (6 dígitos) direto ao Censo (7 dígitos) retorna **zero linhas em silêncio**.
`municipio` é a **tabela-ponte** obrigatória — ver `JOIN_STRATEGY.md`.

### Fora de escopo

O banco contém muitas tabelas alheias ao projeto (SUS, criminalidade, TSE, Censo Escolar da
Educação Básica, entre outras). A allowlist do Analista IA deve listar **apenas** as tabelas
das duas seções acima.

---

## Pendências

- [x] ~~Confirmar se o banco contém mais anos além de 2024~~ — **confirmado pelo autor em 2026-09-05:
  somente 2024.** O trabalho é um retrato transversal; **não há série temporal**.
- [x] ~~Confirmar schema/tabela e se `tp_rede` é inconsistente no banco~~ — **é do schema**, não da exportação.
- [x] ~~Confirmar tipos reais das colunas~~ — feito; ver seção de tipos acima.
- [x] ~~Confirmar se o banco bate com os CSVs~~ — **bate exatamente** nas cinco somas de controle.
- [x] ~~Verificar se o banco tem população / coordenadas~~ — **tem ambas** (`municipio`, `ibge_populacao_estimada`).
- [x] ~~Qual coluna de `municipio` é a chave~~ — **`codigo_municipio_dv`** (7 díg., 0 órfãos).
- [x] ~~Enumerar todas as tabelas de Educação Superior~~ — **são exatamente duas**; ver "Catálogo" acima.
- [x] ~~Inventário completo dos nomes de coluna~~ — 82 em IES, 223 em cursos, extraídos das
  extrações completas em 2026-09-05.
- [x] ~~Grain de `cursos` com chave exata~~ — `(nu_ano_censo, co_curso, co_municipio, tp_dimensao)`
  é única: 720.349 = `COUNT(*)`.
- [x] ~~Nulos~~ — cursos: zero vazios em todas as 223 colunas. IES: só `sg_ies` e `nu_cep_ies`.

### Fechadas contra o banco em 2026-09-05

Conexão direta via `scripts/db/run_sql.py` (sessão somente-leitura). Evidências:
`raw/diagnostics/2026-09-05_06a.csv`, `_06b.csv` e `_07a.csv`.

- [x] ~~Tipo SQL real das 305 colunas~~ — inventário completo lido do `information_schema`.
- [x] ~~`NULL` real vs string vazia~~ — **não existe `NULL`**: cursos é `NOT NULL` em todas as 223
  colunas, IES só admite em `qt_tec_total` (e lá há 0). Os "vazios" são string vazia.
- [x] ~~Padding de `co_municipio_ies`~~ — **não há padding**; `character(7)` com 7 caracteres.
  `btrim()` é desnecessário. **Desbloqueia a Fase 3.**
- [x] ~~Contaminação em `co_uf` / `co_regiao`~~ — confirmada, 11.778 linhas em cada.
- [x] ~~Unicidade da chave de 4 partes~~ — 720.349 = `COUNT(*)`, e 0 cursos com mais de um `co_ies`.
- [x] ~~`ds_rede` como ponte de rede~~ — confirmado, mapeamento 1:1.
- [x] ~~`co_mesorregiao_ies` é local à UF~~ — confirmado (15 códigos, 131 nomes, 131 pares).
- [x] ~~`qt_doc_total` = `qt_doc_exe`~~ — confirmado, 0 linhas divergentes.
- [x] ~~`SELECT` nas oito auxiliares~~ — `true` nas oito. Escrita segue `false` nas duas do Censo.
- [x] ~~Coordenadas fora do Brasil em `municipio`~~ — são as 2 sentinelas de exterior.
- [x] ~~Excedente de municípios~~ — 5.599 = 5.571 municípios e equivalentes + 26 "Município
  Ignorado - UF" + 2 exterior.
- [x] ~~Duplicata em `ibge_populacao_estimada`~~ — **existe**: 50 pares divergentes, anos 2000–2020.
  2024 está limpo; o JOIN precisa filtrar o ano.
- [x] ~~As 9 linhas de EAD sem território~~ — 41 matrículas residuais de 9 cursos que também
  aparecem com município válido.

### Pendências que permanecem

- [ ] Nos 50 pares duplicados de `ibge_populacao_estimada` (2000–2020), qual valor é o correto.
  Só bloqueia se o projeto usar série histórica de população — hoje fora de escopo.
- [ ] Decodificar `v0001`…`v0007` de `IBGE_agregados_por_municipio_basico`, se forem usados.
- [ ] Obter malha municipal IBGE (GeoJSON) para o coroplético — não há polígono no banco.
