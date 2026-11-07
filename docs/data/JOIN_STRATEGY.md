# Estratégia de JOIN

Apurado em **2026-09-05** sobre os CSVs e **confirmado contra o PostgreSQL 17.9** no mesmo dia.

## ⚠️ Incompatibilidade de tipos entre as tabelas — ler antes de escrever JOIN

| Coluna | Em `ies` | Em `cursos` | Risco |
|---|---|---|---|
| `nu_ano_censo` | `character(4)` | `character varying(4)` | **é texto**: use `'2024'`, nunca `2024` |
| `co_ies` | `smallint` | `integer` | JOIN funciona por *cast* implícito, mas impede uso de índice |
| município | `co_municipio_ies` `character(7)` | `co_municipio` `character varying(18)` | ✅ sem padding — ver abaixo |
| `tp_rede` | `integer` | `character varying(7)` | valores incomparáveis (`1`/`2` vs `Pública`/`Privada`) — **use `ies.ds_rede`** |

**✅ `co_municipio_ies` não tem padding — confirmado no banco em 2026-09-05.** O tipo é
`character(7)` e os comprimentos distintos são `7` tanto no valor bruto quanto após `btrim()`:
o código IBGE ocupa exatamente a largura declarada. **O JOIN direto é seguro** e `btrim()` não é
requisito. O mesmo vale para `nu_ano_censo` (`character(4)`, 4 caracteres): `= '2024'` casa as
2.561 linhas sem normalização.

> A única coluna com padding real é `nu_cep_ies` (`character(12)` para um CEP de 8–9 caracteres).
> O projeto não a usa.

**Rede: não compare `tp_rede` com `tp_rede`.** A tabela de IES tem `ds_rede` (`varchar(7)`), com os
rótulos `Pública`/`Privada` — **os mesmos** de `cursos.tp_rede`. Mapeamento 1:1 confirmado
(`1`→`Pública` 317, `2`→`Privada` 2.244). Junte por `ies.ds_rede` ↔ `cursos.tp_rede`.

---

## `cursos` × `ies` — o JOIN principal

| Item | Valor |
|---|---|
| **Chave** | `co_ies` (+ `nu_ano_censo` quando houver mais de um ano) |
| **Cardinalidade** | **N:1** — cursos (720.349) → ies (2.561) |
| **Órfãos** | **0** nos dois sentidos: os 2.561 `co_ies` de cursos são exatamente os 2.561 de IES ✔ |
| **Pré-agregação** | **obrigatória** quando o resultado for por IES ou por município |

### Regra

`co_curso` já é globalmente único e **já determina `co_ies`** — provado: `COUNT(DISTINCT co_curso)`
e `COUNT(DISTINCT (ano, co_ies, co_curso))` dão ambos 46.150. Portanto **não** inclua `co_ies`
na chave de deduplicação de cursos; ele é redundante.

### ⚠️ Armadilha: métricas de IES sobre linhas de curso

`qt_doc_total`, `qt_tec_total` e todas as `qt_doc_ex_*` estão no grain **IES**. Um JOIN ingênuo
as repete em até **1.197 linhas** por curso EAD. Somá-las depois do JOIN infla o total em ordens
de grandeza.

```sql
-- ✘ ERRADO: infla docentes proporcionalmente ao nº de polos
SELECT i.co_municipio_ies, SUM(i.qt_doc_total)
FROM cursos c JOIN ies i USING (co_ies)
GROUP BY 1;

-- ✔ CORRETO: métrica de IES agregada no grain de IES
SELECT co_municipio_ies, SUM(qt_doc_total)
FROM ies
GROUP BY 1;
```

Métrica de IES agrega-se **na tabela de IES**. Só desça ao grain de curso o que for métrica de curso.

### ⚠️ Armadilha: colunas homônimas com semântica diferente

| Coluna | Em `ies` | Em `cursos` |
|---|---|---|
| município | `co_municipio_ies` = **sede da IES** | `co_municipio` = **local de oferta / polo** |
| `tp_rede` | **código inteiro** `1`/`2` | **rótulo** `Pública`/`Privada` |
| capital | `in_capital_ies` (`Sim`/`Não`) | `in_capital` (`Sim`/`Não`/`Cursos a distância`) |

`tp_rede` **não pode ser comparado entre as duas tabelas sem normalização**. Prefira
`tp_categoria_administrativa` (rótulo em ambas) ou normalize explicitamente na camada semântica.

---

## JOIN territorial (município)

**Chave:** `co_municipio` / `co_municipio_ies` — código IBGE de **7 dígitos**.
Verificado: 100% das linhas de IES e 708.571 de 720.349 linhas de cursos têm 7 dígitos.

### Pré-condição obrigatória

```sql
WHERE co_municipio ~ '^[0-9]{7}$'   -- descarta as 11.778 linhas 'Cursos a distância'
```

Sem esse filtro, o valor textual vira uma chave inexistente e um "município" fantasma aparece
em qualquer agregação ou mapa.

**Nunca** juntar por `no_municipio`: há homônimos entre UFs e variação de acentuação.
O código IBGE existe e é confiável — use-o.

> **Confirmado:** `co_municipio` é `character varying` e `co_municipio_ies` é `character`.
> Ambos são **texto**. Se a malha do IBGE trouxer o código como `integer`, o JOIN falha em silêncio —
> converta explicitamente (`btrim(...)::int` ou `codigo::text`) e verifique a contagem depois.

---

## Decisão metodológica pendente: qual é "o município de uma IES"?

As duas leituras são defensáveis e produzem números muito diferentes:

| Recorte | Municípios cobertos | Pergunta que responde |
|---|---|---|
| **Sede** (`ies.co_municipio_ies`) | 698 | onde a instituição está fisicamente instalada |
| **Oferta** (`cursos.co_municipio`) | 3.551 | onde o ensino superior é acessível (inclui polos EAD) |

2.853 municípios têm oferta sem sediar IES. **A escolha precisa ser explícita, documentada e
consistente em toda a plataforma** — e provavelmente exposta ao usuário como um seletor,
não escondida numa decisão de implementação.

Ver o caso de ambiguidade correlato ("universidade" = IES vs. Organização Acadêmica = Universidade,
206 de 2.561) em [`../tcc/architecture/AI_ANALYST.md`](../tcc/architecture/AI_ANALYST.md).

---

## Checklist antes de publicar qualquer número

1. `tp_dimensao` foi filtrada ou declarada?
2. `co_municipio` foi restrito a 7 dígitos?
3. Métrica de IES está sendo agregada no grain de IES?
4. Contagem de cursos usa `SUM(qt_curso)`, não `COUNT(*)` nem `COUNT(DISTINCT co_curso)`?
5. Linhas antes/depois do JOIN conferidas?
6. Total bate com a soma de controle nacional (`qt_mat` = 10.227.266 em 2024)?

---

## `municipio` é a tabela-ponte obrigatória

Verificado em 2026-09-05: **`municipio` tem 5.599 linhas e DUAS colunas de código**, e as tabelas
auxiliares não concordam entre si sobre o formato.

| Chave | Dígitos | Onde aparece |
|---|---|---|
| `codigo_municipio_dv` | **7** | `municipio`, e casa com o Censo (**0 órfãos**) |
| `codigo_municipio` | 6 | `municipio`, e casa com `ibge_populacao_estimada` |

Ligar o Censo direto à população **retorna zero linhas em silêncio** — 7 dígitos nunca igualam 6.
Prova: usar `codigo_municipio` contra o Censo dá **3.551 órfãos**, ou seja, 100% de falha.

```sql
-- ✔ CORRETO: municipio faz a ponte entre os dois formatos
SELECT m.codigo_municipio_dv, m.nome_municipio, m.latitude, m.longitude,
       c.matriculas, p.populacao,
       c.matriculas::numeric / NULLIF(p.populacao, 0) * 100000 AS mat_por_100k
FROM (
    SELECT co_municipio, SUM(qt_mat) AS matriculas
    FROM inep_educacao_superior_cursos
    WHERE nu_ano_censo = '2024'
      AND tp_dimensao  = 'Cursos presenciais ofertados no Brasil'
      AND co_municipio ~ '^[0-9]{7}$'
    GROUP BY co_municipio                      -- pré-agrega ANTES do JOIN
) c
JOIN municipio m               ON m.codigo_municipio_dv::text = c.co_municipio
JOIN ibge_populacao_estimada p ON p.cod_municipio::text       = m.codigo_municipio::text
                              AND p.ano = 2024;               -- casar com o ano do Censo

-- ✘ ERRADO: 7 dígitos vs 6 dígitos → zero linhas, sem erro algum
--   JOIN ibge_populacao_estimada p ON p.cod_municipio::text = c.co_municipio
```

**Use população de 2024** para casar com o ano do Censo. A tabela vai de 2000 a 2026, mas 2025 e
2026 são projeção, e **2023 não existe**.

## JOINs validados

| JOIN | Chave | Cardinalidade | Órfãos | Data |
|---|---|---|---|---|
| `cursos → ies` | `co_ies` | N:1 | **0** nos dois sentidos | 2026-09-05 |
| `cursos → municipio` | `co_municipio = codigo_municipio_dv` | N:1 | **0** | 2026-09-05 |
| `ies → municipio` | `co_municipio_ies = codigo_municipio_dv` | N:1 | **0** | 2026-09-05 |
| `municipio → ibge_populacao_estimada` | `codigo_municipio = cod_municipio` **e `ano = '2024'`** | **1:1 com o ano fixado** (1:N sem ele) | **0** nos dois sentidos — ver abaixo | 2026-10-07 |
| `municipio` ↔ malha IBGE (`data/reference/malha/municipios.geojson`) | `codigo_municipio_dv = properties.codarea` (texto, 7 díg.) | 1:1 | **0** nos dois sentidos — 5.571 e 5.571 | 2026-10-07 |
| agregado de `cursos` por `co_municipio` → `municipio` (mapa da API, presencial + polo) | `codigo = codigo_municipio_dv` | N:1 pós-agregação | **0** — 3.551 linhas antes e depois, `SUM(qt_mat)` 10.224.686 preservada, 0 sentinelas | 2026-09-26 |
| agregado de `ies` por `co_municipio_ies` → `municipio` (mapa da API) | `codigo = codigo_municipio_dv` | N:1 pós-agregação | **0** — 698 antes e depois, 2.561 IES / 374.501 docentes preservados | 2026-09-26 |
| `ies` ← agregado de `cursos` por `co_ies` (tabela de IES da API, `/api/v1/instituicoes`) | `co_ies` | **1:1 pós-agregação** | **0** nos dois sentidos — ver abaixo | 2026-10-06 |

### `cursos` pré-agregada → `municipio` → população e malha (Fase 10, 2026-10-07)

É o JOIN do coroplético (IND-R-01, `api/mapas.py`). Auditado por
`scripts/analise/auditar_mapas.py`; saída em `raw/diagnostics/2026-10-07_mapas.csv`.

| Item | Medido |
|---|---|
| Grain A | `cursos` pré-agregada por `co_municipio` (7 dígitos, filtro `[0-9]{7}`): 1 linha por código |
| Grain B | `municipio` sem as 28 sentinelas: 5.571 linhas, 5.571 códigos de 7 e 5.571 de 6 dígitos distintos |
| Grain C | `ibge_populacao_estimada` com `ano = '2024'`: 5.571 linhas, 5.571 `cod_municipio` distintos, 0 nulos ou ≤ 0 |
| Ponte | `codigo_municipio` (6 díg.) = prefixo de `codigo_municipio_dv` em 5.571 de 5.571 |
| Órfãos | 0 unidades sem população, 0 populações sem unidade |
| Antes → depois | 3.551 → 3.551 linhas com oferta; `SUM(qt_mat)` 10.224.686 → 10.224.686 |
| Denominador | população 2024 = **212.583.750** nas 5.571 unidades (200.295.471 nas 3.551 com oferta) |
| Malha | 5.571 feições, `codarea` texto de 7 dígitos, 0 órfãos nos dois sentidos; 27 UFs por `cd_uf` |

Três cuidados que o resultado não denuncia:

- **`ano` é texto no DuckDB** (`'2024'`). Sem o filtro de ano o JOIN é 1:N e mistura os 50 pares
  divergentes de 2000–2020.
- **O universo é `municipio`, não `cursos`.** O `LEFT JOIN` parte das 5.571 unidades: as 2.020 sem
  linha de oferta saem com numerador **nulo** (ausência), e as 135 com linha e zero matrícula saem
  com **zero**. A população das 2.020 continua no denominador de UF, região e Brasil.
- **A malha é a v4 da API do IBGE.** A v3 (malha de 2022, 5.570 feições) não tem Boa Esperança do
  Norte/MT (`5101837`), que existe em `municipio` e na população de 2024. O ano da edição v4 é
  **A confirmar**; a versão usada é identificada pelo hash em `data/reference/malha/MANIFEST.json`.

A coordenada de `municipio` cai **fora do próprio polígono em 62 das 5.571 unidades**
(ponto-em-polígono; 7 delas são sede de IES, entre elas Salvador e Maceió): ponto e polígono vêm
de fontes diferentes, e a malha é simplificada. Não altera número algum, mas os pontos não são
sobrepostos ao coroplético municipal, e a legenda diz que o ponto é a coordenada de referência do
município. (O teste por caixa envolvente acusava só 10 — aprova o ponto que cai no mar.)

### `ies` ← `cursos` pré-agregada por IES (Fase 8, 2026-10-06)

Único JOIN entre as duas tabelas do Censo em toda a API (`api/analises.py`, `listar_instituicoes`).
Auditado com a skill `join-audit` sobre o DuckDB local.

| Verificação | Resultado |
|---|---|
| Grain de `ies` | 2.561 linhas = 2.561 `co_ies` distintos (`SMALLINT`) |
| Grain de `cursos` | 720.349 linhas, 2.561 `co_ies` (`INTEGER`), 46.150 `co_curso`, 1 ano |
| Domínio das chaves (anti-join) | 0 `co_ies` de cursos sem IES · 0 IES sem cursos |
| Um curso, uma IES | 0 `co_curso` com mais de um `co_ies` |
| Linhas depois do JOIN | **2.561** (= antes), 2.561 `co_ies` distintos, 0 sem par |
| Somas preservadas | cursos 45.776 · matrículas 10.227.266 · ingressantes 5.010.613 · concluintes 1.333.988 · docentes 374.501 · técnicos 350.752 |
| JOIN ingênuo (sem pré-agregar) | 720.349 linhas e **410.207.378** "docentes" — 1.095× o valor real |
| Atributos da IES repetidos em `cursos` | 0 divergências de categoria, organização e rede (`ds_rede` ↔ `tp_rede`) em 720.349 linhas |

`SMALLINT` × `INTEGER` casam sem conversão no DuckDB. Armadilhas registradas:

- **Com `tp_dimensao` filtrada, o LEFT JOIN introduz nulos**: IES com linha em cada dimensão —
  presencial 2.444, EAD por polo 791, EAD "somente a nível Brasil" 793, exterior 27. A API devolve
  **nulo** (ausência de oferta na dimensão), não zero, e ordena os nulos por último.
- **Zero real existe**: 15 IES têm linhas de curso e `SUM(qt_mat) = 0`. Não confundir com o nulo acima.
- **O JOIN muda o recorte das métricas de curso.** A lista é filtrada pela **sede** da IES; cursos e
  matrículas são o total da instituição em qualquer local de oferta (inclusive polos fora do
  território filtrado e linhas sem município). Não é um número territorial de oferta, e a resposta
  o declara em `notas`.
- Docentes e matrículas ficam lado a lado na mesma linha, mas **nenhuma razão é calculada**
  (IND-Q-03 continua em quarentena).
