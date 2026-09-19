# Granularidade das tabelas

Apurado em **2026-09-05** e **confirmado por conexão direta ao PostgreSQL** (sessão somente-leitura).
Grain, chaves, cardinalidade, tipos e nulidade são fatos verificados — nada aqui é inferido.

O grain define o que uma linha representa. Errar o grain não gera erro de execução —
gera número errado. Aqui, errar custa uma ordem de grandeza.

---

## `inep_educacao_superior_ies`

- **Grain:** uma linha = **uma IES no ano do censo**.
- **Chave:** `(nu_ano_censo, co_ies)`.
- **Prova:** `COUNT(*)` = 2.561 · `COUNT(DISTINCT co_ies)` = 2.561 · `COUNT(DISTINCT (ano, co_ies))` = 2.561. ✔
- **Anos:** somente 2024.
- **Agregação:** contagem de IES = `COUNT(*)` ou `COUNT(DISTINCT co_ies)` — equivalentes neste grain.
  `qt_doc_*` e `qt_tec_*` são somáveis diretamente.
- **Chaves que NÃO servem:** `no_ies` tem 2.547 distintos (14 nomes repetidos) e `sg_ies` está
  **vazia em 17,92% das linhas**. Identificar IES por nome ou sigla produz agrupamento errado.
- **Nulos:** só `sg_ies` (459) e `nu_cep_ies` (26). As outras 80 colunas estão 100% preenchidas.
- ⚠️ **`qt_doc_total` e `qt_doc_exe` são idênticas** nas 2.561 linhas — somar as duas duplica
  o total de docentes. Usar `qt_doc_total`.

---

## `inep_educacao_superior_cursos`

- **Grain:** uma linha = **curso × município de oferta × dimensão**.
  **Não** é uma linha por curso.
- **Prova:**

| Chave candidata | Distintos | vs. 720.349 linhas |
|---|---|---|
| `co_curso` | 46.150 | ✘ 15,6× menor |
| `(ano, co_curso)` | 46.150 | ✘ |
| `(ano, co_ies, co_curso)` | 46.150 | ✘ — `co_ies` é redundante: `co_curso` já o determina |
| `(ano, co_curso, co_municipio)` | 719.897 | ✘ por 452 linhas |
| **`(ano, co_curso, co_municipio, tp_dimensao)`** | **720.349** | ✅ **exata — é a chave natural da tabela** |

A chave de 4 partes **fecha o grain sem sobra**: 720.349 combinações distintas para 720.349 linhas,
nenhuma duplicada. As 452 sobras da chave de 3 partes eram o mesmo curso aparecendo em mais de uma
dimensão com o mesmo `co_municipio` (o literal `'Cursos a distância'`); `tp_dimensao` as separa.

`co_ies` é comprovadamente redundante: **`0` cursos** aparecem com mais de um `co_ies`
(verificado linha a linha nas 720.349). `co_curso` determina a IES sozinho.

- **Anos:** somente 2024.
- **Nulos:** as 223 colunas são **`NOT NULL` no schema** — não existe `NULL` nesta tabela,
  nem valor vazio em nenhuma delas.

### Por que 720.349 linhas para 46.150 cursos

Cursos **presenciais** têm exatamente **1 linha por curso** (34.824 cursos × 1 linha — distribuição
verificada: 100% dos cursos presenciais têm exatamente uma linha).

Cursos **EAD** são replicados por **município de polo**: um único curso chega a **1.197 linhas**.
Isso responde por 93,5% da tabela.

### O que NÃO pode ser feito neste grain

| Intenção | ✘ Errado | ✔ Correto |
|---|---|---|
| Nº de cursos no Brasil | `COUNT(*)` → 720.349 | `SUM(qt_curso)` → 45.776 |
| Nº de cursos por município | `COUNT(DISTINCT co_curso)` → conta o mesmo curso EAD em cada polo | `SUM(qt_curso)` |
| Nº de IES por município | contar linhas de cursos | usar a **tabela de IES** (sede) |
| Matrículas | — | `SUM(qt_mat)` está **correto** (ver abaixo) |

### Métricas: distribuídas, não replicadas ✔

Verificado por inspeção direta: para o curso `1576073` (695 linhas), `qt_mat` varia por município
(2, 5, 0, 0, 0, 1…) em vez de repetir o mesmo valor. Logo **`SUM(qt_mat)` não infla**.

Soma nacional 2024: `qt_mat` = 10.227.266 · `qt_ing` = 5.010.613 · `qt_conc` = 1.333.988.

`qt_curso` é a exceção: vale **0** em toda linha de EAD por polo, marcando o curso apenas na
linha presencial ou na de dimensão "somente a nível Brasil". É por isso que ele é o contador correto.

### `tp_dimensao` precisa entrar em quase todo filtro

| Dimensão | Linhas | Σ `qt_mat` | Σ `qt_curso` |
|---|---|---|---|
| EAD ofertados no Brasil | 673.756 | 5.186.852 | 0 |
| Presenciais no Brasil | 34.824 | 5.037.875 | 34.479 |
| EAD só a nível Brasil | 11.319 | 0 | 11.297 |
| EAD no exterior | 450 | 2.539 | 0 |

Somar as quatro dimensões mistura oferta física, polo de EAD e oferta no exterior.
Toda métrica publicada precisa declarar quais dimensões estão incluídas.

---

## Grain territorial — decisão metodológica em aberto

As duas tabelas respondem a perguntas **diferentes** sobre o mesmo município:

| Recorte | Municípios | Significado |
|---|---|---|
| **Sede de IES** (`ies.co_municipio_ies`) | **698** | onde existe instituição instalada |
| **Oferta de curso** (`cursos.co_municipio`) | **3.551** | onde há curso presencial **ou polo EAD** |

Nenhum município com sede de IES está ausente da tabela de cursos (0 órfãos).
**2.853 municípios aparecem em cursos sem sediar nenhuma IES** — são, essencialmente, polos de EAD.

Consequência: "quantas universidades tem o município X" tem respostas distintas conforme
o recorte, e a diferença é de 5×. Ver [`JOIN_STRATEGY.md`](JOIN_STRATEGY.md).

---

## Cuidados adicionais

- ⚠️ **A contaminação por `'Cursos a distância'` não é só de `co_municipio`.** As mesmas 11.778
  linhas trazem o literal em **oito colunas**: `co_municipio`, `no_municipio`, `co_uf`, `sg_uf`,
  `no_uf`, `co_regiao`, `no_regiao` e `in_capital`. Logo **agregação por UF ou região tem o mesmo
  defeito da municipal** — um `GROUP BY sg_uf` sem filtro devolve **28 "UFs"**. Filtrar a coluna
  territorial usada, em qualquer nível, antes de agregar ou juntar.
- ⚠️ **Nunca agrupar por nome de município.** Em cursos há 3.429 nomes para 3.551 códigos;
  em IES, 695 nomes para 698 códigos (`Valença`, `Cascavel`, `Redenção` repetem entre UFs).
- Distinguir **zero real** de **ausência**: 5.570 municípios existem no Brasil; 3.551 aparecem
  em cursos e 698 sediam IES. Os demais são ausência de linha, não zero registrado.
- Com **um único ano (2024)**, não há série temporal possível nestes extratos.
