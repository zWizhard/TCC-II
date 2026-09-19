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
| `tp_rede` | **código** `'1'`/`'2'` | **rótulo** `Pública`/`Privada` |
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
| `municipio → ibge_populacao_estimada` | `codigo_municipio = cod_municipio` | 1:N (por ano) | a confirmar | — |
