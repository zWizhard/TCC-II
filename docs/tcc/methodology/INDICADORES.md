# Indicadores da plataforma — definição formal

**Fase 4, 2026-09-19.** Definição metodológica dos indicadores. Não há aqui implementação de
API, frontend ou Analista IA: este documento é a especificação que essas camadas terão de honrar.

**Base factual:** exclusivamente o que foi verificado nas Fases 2 e 3
([`../../data/DATA_DICTIONARY.md`](../../data/DATA_DICTIONARY.md),
[`../../data/DATA_GRAIN.md`](../../data/DATA_GRAIN.md),
[`../../data/JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md)) e o que foi medido na auditoria
de suporte desta fase, sobre a cópia DuckDB local ([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)):

| Evidência | Verificações |
|---|---|
| [`2026-09-19_familias_metricas.csv`](../../data/raw/diagnostics/2026-09-19_familias_metricas.csv) | 79 — fechamento, domínio e contenção das famílias `qt_vg_*`, `qt_inscrito_*`, `qt_doc_ex_*`, `qt_tec_*`, `qt_*_financ*`, `qt_*_rv*`, `qt_sit_*` e do perfil de `qt_mat`/`qt_ing`/`qt_conc` |
| [`2026-09-19_semantica_metricas.csv`](../../data/raw/diagnostics/2026-09-19_semantica_metricas.csv) | 19 — replicação × distribuição entre polos, semântica de `qt_curso`, natureza das unidades de `municipio` |

Reprodutíveis com:

```
.venv/Scripts/python.exe scripts/analise/auditar_familias_metricas.py
.venv/Scripts/python.exe scripts/analise/auditar_semantica_metricas.py
```

O que não foi verificado está marcado **A confirmar** e listado no fim. Nada aqui é inferido de
nome de coluna.

---

## Como ler uma ficha

Cada indicador traz os onze campos exigidos: **nome · definição · finalidade · fórmula ·
campos de origem · unidade · granularidade · dimensões e filtros permitidos · pressupostos ·
limitações · validação possível.**

Três blocos, e a fronteira entre eles é o critério de admissibilidade da
[ADR-0009](../decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md):

- **A — Diretos:** contagem ou soma de uma coluna do Censo, sem denominador.
- **B — Derivados:** razão, proporção ou composição. Só entram aqui os que a auditoria sustenta.
- **C — Quarentena:** recusados nesta fase, com o motivo técnico. **Não implementar.**

---

## Regras transversais — valem para todos os indicadores

Violar qualquer uma delas produz número errado **sem gerar erro de execução**.

1. **Ano.** `nu_ano_censo = '2024'` — a coluna é texto nas duas tabelas. Só existe 2024:
   é um retrato transversal, e nenhum indicador admite leitura de evolução, tendência ou
   crescimento.
2. **Dimensão de oferta.** `tp_dimensao` é **dimensão obrigatória declarada**, sem padrão
   universal ([ADR-0009](../decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md)).
   As quatro dimensões medem coisas diferentes e não se somam sem declaração explícita:

   | `tp_dimensao` | Linhas | `qt_curso` | `qt_vg_total` | `qt_inscrito_total` | `qt_ing` | `qt_mat` | `qt_conc` |
   |---|---|---|---|---|---|---|---|
   | Cursos presenciais ofertados no Brasil | 34.824 | 34.479 | 5.075.146 | 8.658.561 | 1.663.040 | 5.037.875 | 729.246 |
   | Cursos a distância ofertados no Brasil (polo) | 673.756 | 0 | 6.925 | 3.590 | 3.346.116 | 5.186.852 | 604.269 |
   | Cursos a distância com dimensão de dados somente a nível Brasil | 11.319 | 11.297 | 18.583.348 | 7.060.934 | 0 | 0 | 0 |
   | Cursos a distância ofertados por instituições brasileiras no exterior | 450 | 0 | 0 | 0 | 1.457 | 2.539 | 473 |
   | **Total** | **720.349** | **45.776** | **23.665.419** | **15.723.085** | **5.010.613** | **10.227.266** | **1.333.988** |

   Leia a tabela na vertical antes de definir qualquer indicador: **vaga e matrícula de EAD não
   coexistem na mesma dimensão.**
3. **Recorte territorial.** Sede da IES (698 unidades) ou local de oferta incluindo polos EAD
   (3.551) — dimensão obrigatória, padrão inicial "sede"
   ([ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md)). Todo indicador territorial
   declara o recorte; comparar números de recortes diferentes é proibido sem sinalização.
4. **Filtro territorial.** `co_municipio ~ '^[0-9]{7}$'` antes de qualquer agregação ou JOIN
   por território, **em qualquer nível** — a contaminação por `'Cursos a distância'` atinge
   oito colunas, e um `GROUP BY sg_uf` sem filtro devolve 28 "UFs".
5. **Grain.** Métrica de IES (`qt_doc_*`, `qt_tec_*`) agrega-se **na tabela de IES**, nunca após
   JOIN com cursos. Métrica de curso agrega-se em `cursos`. Contagem de cursos usa
   `SUM(qt_curso)`, nunca `COUNT(*)` nem `COUNT(DISTINCT co_curso)`.
6. **Chave municipal.** Sempre código IBGE de 7 dígitos; `municipio.codigo_municipio_dv` é a
   ponte obrigatória para as auxiliares de 6 dígitos. Nunca juntar nem agrupar por nome.
7. **Rede.** Comparar `ies.ds_rede` ↔ `cursos.tp_rede`, nunca os `tp_rede` crus
   ([ADR-0007](../decisions/ADR-0007-comparacao-de-rede-via-ds-rede.md)). `Pública` inclui as
   28 IES de categoria *Especial*.
8. **Perda declarada.** O filtro territorial descarta 41 matrículas de 10.227.266 (0,0004%),
   residuais de 9 cursos EAD sem polo identificado. Total territorializável de matrículas:
   **10.224.686**. A diferença deve ser declarada, não escondida.

### Fato transversal descoberto nesta fase: turno é dimensão presencial

`qt_mat_diurno + qt_mat_noturno` = **5.037.875**, exatamente o total presencial. O resíduo de
5.189.391 é exatamente a soma de EAD, e o turno declarado em EAD é **zero** — o mesmo vale para
ingressantes (3.347.573) e concluintes (604.742). Qualquer composição por turno é, por construção,
um indicador **exclusivamente presencial**, e apresentá-la sobre o universo total produz um
"sem informação" de 50,7% que na verdade é ausência de aplicabilidade, não ausência de dado.

---

# Bloco A — Indicadores diretos

## IND-D-01 — Instituições de ensino superior instaladas

- **Definição:** número de IES com registro no Censo 2024, contadas no município onde têm sede.
- **Finalidade:** medir presença institucional instalada — a infraestrutura acadêmica fisicamente
  existente num território.
- **Fórmula:** `COUNT(*)` sobre `inep_educacao_superior_ies` (equivalente a
  `COUNT(DISTINCT co_ies)` neste grain).
- **Campos de origem:** `inep_educacao_superior_ies.co_ies`, `co_municipio_ies`, `nu_ano_censo`.
- **Unidade:** instituições (contagem inteira).
- **Granularidade:** IES → município de sede → UF → região → Brasil. Também por
  `tp_organizacao_academica`, `tp_categoria_administrativa`, `ds_rede`.
- **Dimensões e filtros permitidos:** organização acadêmica, categoria administrativa, rede,
  `in_comunitaria`, `in_confessional`, `in_capital_ies`, recorte territorial **sede** (único
  aplicável). Não admite `tp_dimensao` — a tabela de IES não a possui.
- **Pressupostos:** uma linha = uma IES (chave `(nu_ano_censo, co_ies)`, 2.561 = `COUNT(*)`
  provado); sede é atributo único da IES.
- **Limitações:** **não é contagem de campi nem de polos.** Uma IES com 40 unidades conta 1, no
  município da sede. Não use este indicador para responder "onde há ensino superior" — use
  IND-D-11. `no_ies` tem 14 homônimos e `sg_ies` está vazia em 17,92% das linhas: identificar
  IES por nome ou sigla agrupa errado.
- **Validação possível:** total nacional = **2.561**; soma por `ds_rede` = 317 Pública +
  2.244 Privada; soma por `tp_categoria_administrativa` = 1.486 + 758 + 139 + 122 + 28 + 28;
  `COUNT(DISTINCT co_municipio_ies)` = 698.

## IND-D-02 — Cursos contabilizados na oferta

> ⚠️ **Nome deliberado.** Não é "número de cursos". Ver a limitação central abaixo.

- **Definição:** soma do marcador `qt_curso`, que a base atribui a exatamente uma linha por curso
  contabilizado, na dimensão de oferta correspondente.
- **Finalidade:** dimensionar a oferta de cursos de graduação sem contar o mesmo curso EAD uma
  vez por polo.
- **Fórmula:** `SUM(qt_curso)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_curso`, `tp_dimensao`, `co_curso`,
  `co_municipio`, `nu_ano_censo`.
- **Unidade:** cursos (contagem inteira).
- **Granularidade:** curso → IES → município de oferta → UF → região → Brasil; também por
  área CINE, grau acadêmico, rede, modalidade.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), `tp_grau_academico`,
  `tp_nivel_academico`, hierarquia CINE, `tp_rede`, `tp_categoria_administrativa`,
  `in_gratuito`, recorte territorial **oferta**.
- **Pressupostos:** `qt_curso` assume **apenas 0 ou 1** (verificado: 674.573 zeros e 45.776 uns) e
  `SUM(qt_curso)` agrupado por `co_curso` nunca excede 1 (verificado, máximo = 1). O marcador
  aparece só nas dimensões presencial (34.479) e "somente a nível Brasil" (11.297); é zero em
  todas as linhas de polo EAD e de exterior.
- **Limitações:**
  - **`SUM(qt_curso)` = 45.776 e `COUNT(DISTINCT co_curso)` = 46.150 são conceitos diferentes e
    não podem ser usados como sinônimos.** Os **374 cursos** da diferença não são linhas vazias:
    somam **61.053 matrículas, 44.421 ingressantes, 89.269 vagas e 184.350 inscrições — e zero
    concluintes**; apenas 14 deles são totalmente inertes.
  - **O que distingue esses 374 não existe como coluna nesta base.** Não há `tp_situacao` nem
    equivalente. A semântica oficial de `qt_curso` é **A confirmar** contra o dicionário de
    variáveis do INEP; até lá o indicador é publicável, mas o rótulo não pode prometer
    "todos os cursos".
  - Se a interface precisar do outro conceito, ele é um indicador distinto — "cursos com
    registro no Censo" — e não substitui este.
- **Validação possível:** total nacional = **45.776**; por dimensão = 34.479 + 11.297;
  `COUNT(DISTINCT co_curso)` = 46.150 e a diferença = 374; nenhuma linha de polo EAD contribui.

## IND-D-03 — Matrículas

- **Definição:** número de vínculos de matrícula em cursos de graduação informados ao Censo 2024.
- **Finalidade:** medir o porte da população estudantil atendida — é a métrica de referência da
  plataforma.
- **Fórmula:** `SUM(qt_mat)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_mat`, `tp_dimensao`, `co_municipio`.
- **Unidade:** matrículas (vínculos, não pessoas distintas).
- **Granularidade:** curso → IES → município de oferta → UF → região → Brasil; por CINE, grau,
  rede, modalidade, e por todos os perfis do IND-R-07.
- **Dimensões e filtros permitidos:** todas as dimensões categóricas de `cursos`; recorte
  territorial **oferta**.
- **Pressupostos:** a métrica é **distribuída** entre os polos de um curso EAD, não replicada —
  reverificado nesta fase: dos 8.395 cursos EAD multi-linha com matrícula, 8.324 variam entre
  polos; os 71 constantes têm no máximo 12 linhas e valor máximo 11, somando 270 de 5.186.852
  (0,005%). `SUM` é, portanto, válido.
- **Limitações:** conta **vínculos**, não estudantes — uma pessoa em dois cursos conta duas
  vezes, e a base não permite deduplicar por pessoa (não existe tabela de aluno). O filtro
  territorial descarta 41 matrículas.
- **Validação possível:** soma de controle nacional = **10.227.266**; territorializável =
  **10.224.686**; por dimensão = 5.186.852 + 5.037.875 + 0 + 2.539; fechamento com as seis
  decomposições de perfil (todas exatas, 0 divergências em 720.349 linhas).

## IND-D-04 — Ingressantes

- **Definição:** número de ingressos em cursos de graduação no ano de referência.
- **Finalidade:** medir o fluxo de entrada no sistema, e servir de denominador aos indicadores
  de acesso (financiamento, reserva de vagas, procedência escolar).
- **Fórmula:** `SUM(qt_ing)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_ing`, `tp_dimensao`, `co_municipio`.
- **Unidade:** ingressos (vínculos).
- **Granularidade:** idêntica ao IND-D-03.
- **Dimensões e filtros permitidos:** idem; adicionalmente por forma de ingresso
  (`qt_ing_vestibular`, `qt_ing_enem`, …) — **mas ver a ressalva de fechamento abaixo**.
- **Pressupostos:** distribuída entre polos (verificado: 7.730 de 7.786 cursos EAD multi-linha
  variam; os 56 constantes somam 221).
- **Limitações:** ingresso ≠ pessoa distinta. A decomposição por **forma de ingresso** não foi
  auditada nesta fase e não pode ser publicada como composição até que passe pelo teste de
  fechamento — **A confirmar**.
- **Validação possível:** total nacional = **5.010.613**; territorializável = 5.009.116;
  por dimensão = 3.346.116 + 1.663.040 + 0 + 1.457; fechamento exato em sexo, cor/raça, faixa
  etária, nacionalidade e procedência escolar.

## IND-D-05 — Concluintes

- **Definição:** número de conclusões de curso de graduação registradas no ano de referência.
- **Finalidade:** dimensionar a saída anual do sistema por área, grau e território.
- **Fórmula:** `SUM(qt_conc)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_conc`, `tp_dimensao`, `co_municipio`.
- **Unidade:** concluintes (conclusões, não pessoas distintas).
- **Granularidade:** idêntica ao IND-D-03.
- **Dimensões e filtros permitidos:** idem.
- **Pressupostos:** distribuída entre polos (6.086 de 6.109 cursos variam; os 23 constantes
  somam 76).
- **Limitações:** ⚠️ **este número não pode ser dividido por ingressantes nem por matrículas
  para produzir taxa de conclusão** — ver [IND-Q-01](#ind-q-01--taxa-de-conclusão). São
  populações de coortes distintas observadas no mesmo ano. Os 374 cursos não contabilizados em
  IND-D-02 têm **zero** concluintes.
- **Validação possível:** total nacional = **1.333.988**; por dimensão = 729.246 + 604.269 + 473;
  fechamento exato nas cinco decomposições de perfil.

## IND-D-06 — Vagas ofertadas

> ⚠️ **Não territorializável em EAD.** Ver limitações.

- **Definição:** número de vagas oferecidas em processos seletivos para cursos de graduação.
- **Finalidade:** dimensionar a capacidade de oferta declarada, e servir de denominador aos
  indicadores IND-R-10 e IND-R-11.
- **Fórmula:** `SUM(qt_vg_total)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_vg_total`, `tp_dimensao`.
- **Unidade:** vagas.
- **Granularidade:** curso → IES → **município apenas no presencial** → UF → região → Brasil.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), CINE, grau, rede, categoria
  administrativa. Decomposições **auditadas e válidas**: por turno/modalidade
  (`qt_vg_total_diurno + qt_vg_total_noturno + qt_vg_total_ead`) e por tipo de vaga
  (`qt_vg_nova + qt_vg_proc_seletivo + qt_vg_remanesc + qt_vg_prog_especial`) — ambas fecham
  exatamente, e são **ortogonais entre si** (não podem ser somadas juntas).
- **Pressupostos:** as duas decomposições são partições exatas de `qt_vg_total`
  (0 linhas divergentes em 720.349, nas duas).
- **Limitações:**
  - **78,5% das vagas (18.583.348 de 23.665.419) estão na dimensão "somente a nível Brasil",
    que não tem município, UF nem região.**
  - Nas 673.747 linhas de polo EAD **com** território, `qt_vg_total` é **zero em todas**;
    as 6.925 vagas dessa dimensão estão inteiramente nas 9 linhas sem município.
  - Consequência: **vaga só existe territorializada no presencial** (5.075.146). Um mapa de
    vagas é, necessariamente, um mapa de vagas presenciais, e deve dizê-lo.
  - `qt_vg_nova` (17.407.524) **não** é a soma dos outros três tipos — é um dos quatro termos
    da partição, não um total. Não usar como denominador de "tipos de vaga".
- **Validação possível:** total nacional = **23.665.419**; territorializável = **5.075.146**,
  exatamente igual ao total presencial; as duas decomposições somam 23.665.419 sem divergência.

## IND-D-07 — Inscrições em processo seletivo

> ⚠️ **Não territorializável em EAD.** Mesma restrição do IND-D-06.

- **Definição:** número de inscrições registradas em processos seletivos.
- **Finalidade:** medir a demanda manifesta por vagas de graduação.
- **Fórmula:** `SUM(qt_inscrito_total)`, com `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.qt_inscrito_total`, `tp_dimensao`.
- **Unidade:** **inscrições** — explicitamente não pessoas.
- **Granularidade:** curso → IES → **município apenas no presencial** → UF → região → Brasil.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), CINE, grau, rede. Decomposições
  auditadas e válidas: turno/modalidade e tipo de vaga (`qt_insc_*`) — ambas fecham exatamente
  e são ortogonais.
- **Pressupostos:** partições exatas (0 divergências nas duas).
- **Limitações:**
  - **Uma pessoa pode inscrever-se em vários cursos e várias IES.** O indicador mede
    inscrições, e nenhum texto da plataforma pode chamá-las de "candidatos".
  - 7.060.934 de 15.723.085 (44,9%) estão na dimensão sem território; nas linhas de polo EAD com
    município o valor é zero. Territorializável = **8.658.561**, exatamente o total presencial.
  - `qt_insc_vg_nova` não é a soma dos outros tipos — mesma armadilha do `qt_vg_nova`.
- **Validação possível:** total nacional = **15.723.085**; territorializável = 8.658.561;
  as duas decomposições fecham sem divergência.

## IND-D-08 — Docentes em exercício

- **Definição:** número de docentes em exercício informados pelas IES no Censo 2024.
- **Finalidade:** dimensionar o corpo docente instalado por território, rede e organização
  acadêmica.
- **Fórmula:** `SUM(qt_doc_total)` **sobre a tabela de IES**.
- **Campos de origem:** `inep_educacao_superior_ies.qt_doc_total`, `co_municipio_ies`, `co_ies`.
- **Unidade:** docentes (pessoas, no grain da IES).
- **Granularidade:** IES → município de **sede** → UF → região → Brasil.
- **Dimensões e filtros permitidos:** organização acadêmica, categoria administrativa, rede,
  capital; recorte territorial **sede** (único aplicável). Decomposições auditadas e **todas
  exatas**: sexo, titulação, regime de trabalho, faixa etária, cor/raça, nacionalidade.
- **Pressupostos:** `qt_doc_total` e `qt_doc_exe` são a **mesma medida sob dois nomes**
  (0 divergências nas 2.561 linhas) — somar as duas duplica o total.
- **Limitações:**
  - ⚠️ **Nunca somar após JOIN com `cursos`**: o valor se repete em até 1.197 linhas por curso
    EAD e o total infla em ordens de grandeza.
  - Atribuído à **sede**, não onde o docente leciona. Uma IES com campi em 10 municípios
    concentra todos os docentes em um só ponto do mapa. Isso é limite da base, não do indicador.
  - Não existe tabela de docente: não há grain de pessoa, nem vínculo docente-curso.
  - Três IES declaram `qt_doc_total = 0`.
- **Validação possível:** total nacional = **374.501**; as seis decomposições fecham com
  0 divergências; `qt_doc_ex_int = qt_doc_ex_int_de + qt_doc_ex_int_sem_de` = 212.899;
  `qt_doc_ex_com_deficiencia` = 2.401, contido no total.

## IND-D-09 — Técnicos administrativos

- **Definição:** número de funcionários técnico-administrativos informados pelas IES.
- **Finalidade:** dimensionar a estrutura de apoio institucional.
- **Fórmula:** `SUM(qt_tec_total)` **sobre a tabela de IES**.
- **Campos de origem:** `inep_educacao_superior_ies.qt_tec_total`, `co_municipio_ies`.
- **Unidade:** funcionários (pessoas, no grain da IES).
- **Granularidade:** IES → município de **sede** → UF → região → Brasil.
- **Dimensões e filtros permitidos:** idem IND-D-08. Decomposição auditada e exata:
  escolaridade × sexo (14 colunas `qt_tec_*`).
- **Pressupostos:** única coluna do conjunto que o schema declara nullable, e tem **zero** nulos
  de fato; mínimo observado = 1.
- **Limitações:** mesmas do IND-D-08 quanto a grain e sede. A decomposição cruza escolaridade
  **com** sexo e não permite isolar uma das duas sem recombinar as 14 colunas.
- **Validação possível:** total nacional = **350.752**; as 14 colunas somam exatamente o total,
  0 divergências em 2.561 linhas.

## IND-D-10 — Unidades territoriais com sede de IES

- **Definição:** número de municípios e equivalentes que sediam ao menos uma IES.
- **Finalidade:** medir o alcance da instalação física do sistema de ensino superior.
- **Fórmula:** `COUNT(DISTINCT co_municipio_ies)` sobre `inep_educacao_superior_ies`.
- **Campos de origem:** `inep_educacao_superior_ies.co_municipio_ies`.
- **Unidade:** unidades territoriais de nível municipal.
- **Granularidade:** UF → região → Brasil (o indicador é uma contagem de territórios; não existe
  no grain do próprio município).
- **Dimensões e filtros permitidos:** rede, categoria administrativa, organização acadêmica.
  Recorte territorial **sede**, por definição.
- **Pressupostos:** `co_municipio_ies` tem 7 caracteres exatos, sem padding, e 0 órfãos contra
  `municipio.codigo_municipio_dv`; o Censo **não referencia nenhuma das 28 sentinelas**
  (verificado nesta fase: 0 linhas de IES e 0 de cursos).
- **Limitações:** contagem de territórios, não de instituições — não comparar com IND-D-01.
  Ausência de linha significa ausência de sede, não zero registrado.
- **Validação possível:** total nacional = **698**.

## IND-D-11 — Unidades territoriais com oferta de curso

- **Definição:** número de municípios e equivalentes onde há ao menos um curso presencial ou um
  polo de EAD.
- **Finalidade:** medir o alcance do **acesso** ao ensino superior, que é cinco vezes maior que
  o da instalação física — o contraste com IND-D-10 é, em si, um achado do trabalho
  ([ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md)).
- **Fórmula:** `COUNT(DISTINCT co_municipio)` sobre `inep_educacao_superior_cursos`,
  com `co_municipio ~ '^[0-9]{7}$'` e `tp_dimensao` declarada.
- **Campos de origem:** `inep_educacao_superior_cursos.co_municipio`, `tp_dimensao`.
- **Unidade:** unidades territoriais de nível municipal.
- **Granularidade:** UF → região → Brasil.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória — presencial e polo EAD dão
  respostas muito diferentes), CINE, grau, rede. Recorte territorial **oferta**, por definição.
- **Pressupostos:** o filtro de 7 dígitos é obrigatório; sem ele aparece uma 28ª "UF" fantasma.
- **Limitações:** **equipara campus físico a polo de EAD.** Um município com um único polo conta
  igual a um com uma universidade federal. Não usar como proxy de infraestrutura acadêmica —
  para isso existe o IND-D-10, e os dois nunca devem ser comparados sem sinalização.
- **Validação possível:** total nacional = **3.551**; 2.853 dessas unidades não sediam nenhuma
  IES; nenhuma unidade com sede está ausente (0 órfãos).

---

# Bloco B — Indicadores derivados

## IND-R-01 — Matrículas por 100 mil habitantes

- **Definição:** razão entre matrículas e população residente estimada da unidade territorial,
  normalizada por 100.000 habitantes.
- **Finalidade:** tornar territórios de portes diferentes comparáveis no mapa — sem ela, o
  coroplético só mostra onde há gente.
- **Fórmula:** `SUM(qt_mat) / NULLIF(populacao, 0) * 100000`, pré-agregando `qt_mat` **antes** do
  JOIN.
- **Campos de origem:** `cursos.qt_mat`, `cursos.co_municipio`;
  `municipio.codigo_municipio_dv`, `municipio.codigo_municipio`;
  `ibge_populacao_estimada.cod_municipio`, `.populacao`, `.ano`.
- **Unidade:** matrículas por 100 mil habitantes.
- **Granularidade:** município → UF → região → Brasil. **O denominador precisa ser reagregado
  em cada nível** — não é a média das razões municipais.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE, grau.
- **Pressupostos:** `municipio` é a **tabela-ponte obrigatória** — o Censo usa 7 dígitos e a
  população 6; o JOIN direto devolve zero linhas em silêncio. `ibge_populacao_estimada` deve
  ser filtrada por `ano = 2024`: a tabela tem 50 pares `(ano, município)` duplicados com valores
  divergentes (até 100×) nos anos 2000–2020, e 2024 está limpo.
- **Limitações:**
  - **A matrícula é contada no local de oferta, e o habitante no local de residência.** Um
    município-polo de EAD que atende a região inteira infla a razão; a métrica **não** mede
    escolarização da população local.
  - Não é taxa de escolarização: o denominador é a população total, não a população em idade
    de cursar ensino superior — essa faixa etária não existe nesta base.
  - Unidades territoriais sem linha em `cursos` são **ausência**, não zero.
- **Validação possível:** somar o numerador reagregado por UF e conferir contra 10.224.686;
  verificar que o JOIN não multiplica linhas (`COUNT(*)` antes e depois); conferir que nenhuma
  unidade aparece duas vezes; checar que o total de população usado bate com o ano 2024.

## IND-R-02 — Cobertura territorial da oferta

- **Definição:** proporção das unidades territoriais de nível municipal do país que têm oferta de
  ensino superior, sob o recorte declarado.
- **Finalidade:** expressar em uma frase o alcance territorial do sistema, e sustentar a
  comparação entre instalação (sede) e acesso (oferta).
- **Fórmula:** `unidades_com_oferta / 5571 * 100`, com o recorte declarado no numerador.
- **Campos de origem:** numerador — `cursos.co_municipio` ou `ies.co_municipio_ies`;
  denominador — `municipio.codigo_municipio_dv`.
- **Unidade:** percentual de unidades territoriais.
- **Granularidade:** Brasil, UF, região (o denominador é recontado em cada nível).
- **Dimensões e filtros permitidos:** recorte territorial (obrigatório), `tp_dimensao`
  (obrigatória quando o numerador vier de `cursos`).
- **Pressupostos — o denominador foi auditado nesta fase:**

  | Grupo | Linhas | Critério |
  |---|---|---|
  | Unidades territoriais reais | **5.571** | código não termina em `00000` e não começa por `99` |
  | `Município Ignorado - <UF>` | 26 | termina em `00000` |
  | Exterior (`9900000`, `9999999`) | 2 | começa por `99` |
  | **Total de `municipio`** | **5.599** | |

  O filtro publicado em `DATA_DICTIONARY.md` —
  `right(codigo, 5) <> '00000' AND codigo <> '9999999'` — foi reconferido nesta fase e devolve
  **5.571**, correto: `9900000` termina em `00000` e já cai na primeira condição. A redundância
  entre as duas condições não afeta o resultado, porque são exclusões de conjunto e não
  subtrações.
- **Limitações:**
  - ⚠️ **As 5.571 unidades não são 5.571 "municípios".** Excluindo `2605459` restam **5.570**:
    Fernando de Noronha é **distrito estadual de Pernambuco**, não município — e por isso PE
    aparece com 185 unidades. O Distrito Federal entra com uma única unidade (Brasília).
    A denominação correta em toda a interface é **"municípios e equivalentes"** ou
    "unidades territoriais de nível municipal". Escrever "de 5.571 municípios" é incorreto.
  - A correspondência entre esse conjunto e a lista oficial vigente do IBGE na data do Censo é
    **A confirmar** contra a Divisão Territorial Brasileira.
  - Cobertura não é qualidade nem intensidade de oferta: um polo com 3 matrículas cobre o
    território tanto quanto uma universidade.
- **Validação possível:** 698/5.571 = **12,53%** (sede) e 3.551/5.571 = **63,74%** (oferta);
  a soma das unidades por UF deve dar 5.571 em 27 UFs; o Censo não referencia sentinela alguma
  (0 linhas em ambas as tabelas).

## IND-R-03 — Participação da rede privada

- **Definição:** proporção de uma métrica (matrículas, por padrão) atribuída a IES da rede
  privada.
- **Finalidade:** caracterizar a estrutura público-privada do sistema, que é o traço mais
  marcante do ensino superior brasileiro.
- **Fórmula:** `SUM(qt_mat) FILTER (WHERE tp_rede = 'Privada') / SUM(qt_mat) * 100`.
- **Campos de origem:** `cursos.tp_rede`, `cursos.qt_mat`; para métricas de IES,
  `ies.ds_rede` e `ies.tp_categoria_administrativa`.
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município; também por CINE, grau e `tp_dimensao`.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), CINE, grau.
- **Pressupostos:** `cursos.tp_rede` traz rótulos (`Privada` 700.198 · `Pública` 20.151) e
  `ies.tp_rede` traz códigos — comparar entre tabelas apenas via `ies.ds_rede`
  ([ADR-0007](../decisions/ADR-0007-comparacao-de-rede-via-ds-rede.md)). A partição é binária e
  exaustiva: não há terceira categoria.
- **Limitações:** ⚠️ **`Pública` inclui as 28 IES de categoria *Especial***, exatamente como
  `tp_rede = '1'`. Para "pública" em sentido estrito, usar `tp_categoria_administrativa`, que é
  comparável entre as duas tabelas. O indicador descreve a rede da **IES ofertante**, não o
  financiamento do estudante — para isso existe o IND-R-08.
- **Validação possível:** as duas parcelas somam 100%; contagem de linhas por rótulo =
  700.198 + 20.151 = 720.349; em IES, 2.244 + 317 = 2.561.

## IND-R-04 — Participação da educação a distância

- **Definição:** proporção de uma métrica atribuída a cursos a distância, medida por
  `tp_dimensao`.
- **Finalidade:** dimensionar o fenômeno que responde por 93,5% das linhas da tabela de cursos e
  por mais da metade das matrículas.
- **Fórmula:** `SUM(qt_mat)` nas dimensões de EAD ÷ `SUM(qt_mat)` total × 100.
- **Campos de origem:** `cursos.tp_dimensao`, `cursos.qt_mat`.
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município; por CINE, grau, rede.
- **Dimensões e filtros permitidos:** recorte territorial (obrigatório), rede, CINE, grau.
  `tp_dimensao` aqui **é o próprio eixo do indicador** e não pode ser filtrada previamente.
- **Pressupostos:** **usar `tp_dimensao`, não `tp_modalidade_ensino`.** As duas são redundantes
  (as três dimensões de EAD dão sempre `'Curso a distância'`, sem exceção em 720.349 linhas),
  mas só `tp_dimensao` separa oferta física, polo, agregado nacional e exterior.
- **Limitações:** o resultado muda conforme quais dimensões de EAD entram na conta — incluir a
  dimensão "somente a nível Brasil" altera radicalmente o numerador de vagas (18,6 milhões) e não
  altera o de matrículas (zero). **Cada publicação declara as dimensões incluídas.**
  Não aplicável a vagas e inscrições em recorte territorial (ver IND-D-06).
- **Validação possível:** matrículas EAD = 5.186.852 + 0 + 2.539 = 5.189.391, ou **50,74%** de
  10.227.266; excluindo o exterior, 5.186.852 (50,72%).

## IND-R-05 — Composição por grau acadêmico

- **Definição:** distribuição percentual de uma métrica entre bacharelado, licenciatura,
  tecnológico e "não aplicável".
- **Finalidade:** caracterizar o perfil formativo da oferta de um território, rede ou área.
- **Fórmula:** `SUM(qt_mat) GROUP BY tp_grau_academico` ÷ total do recorte × 100.
- **Campos de origem:** `cursos.tp_grau_academico`, `cursos.qt_mat` (ou `qt_curso`, `qt_ing`,
  `qt_conc`).
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município, IES, área CINE.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE.
- **Pressupostos:** a coluna é categórica exaustiva — 338.574 Tecnológico + 243.210 Bacharelado
  + 136.519 Licenciatura + 2.046 Não aplicável = 720.349 linhas.
- **Limitações:** **`Não aplicável` (2.046 linhas) é uma categoria real e não pode ser
  descartada em silêncio** — descartá-la muda o denominador. A distribuição por *linhas* não é a
  distribuição por *matrículas*: sempre ponderar pela métrica, nunca contar linhas.
- **Validação possível:** as categorias somam 100% e a soma das parcelas reproduz a soma de
  controle da métrica escolhida.

## IND-R-06 — Composição por área do conhecimento (CINE)

- **Definição:** distribuição percentual de uma métrica entre as áreas da classificação CINE.
- **Finalidade:** mostrar a vocação formativa de um território e permitir comparação entre
  regiões e redes.
- **Fórmula:** `SUM(qt_mat) GROUP BY co_cine_area_geral` ÷ total do recorte × 100.
- **Campos de origem:** `cursos.co_cine_area_geral` / `no_cine_area_geral` (11 categorias, 1:1);
  hierarquia `area_especifica` (39) e `area_detalhada` (89); `co_cine_rotulo` (353).
- **Unidade:** percentual.
- **Granularidade:** três níveis hierárquicos CINE × Brasil, região, UF, município, IES, rede.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, grau.
- **Pressupostos:** os pares código/nome são 1:1 em todos os níveis (11/11, 353/353); agrupar por
  código e rotular pelo nome é seguro.
- **Limitações:** a hierarquia CINE é a classificação do INEP e não corresponde a divisões
  administrativas de universidades. Níveis mais finos (89 áreas detalhadas, 353 rótulos)
  fragmentam a métrica e produzem células muito pequenas em recortes municipais — a
  visualização deve ter um mínimo declarado, não suprimir em silêncio.
- **Validação possível:** as 11 áreas somam 100% e reproduzem a soma de controle;
  `COUNT(DISTINCT co_cine_area_geral)` = 11.

## IND-R-07 — Perfil das matrículas, ingressos e conclusões

- **Definição:** distribuição percentual de `qt_mat`, `qt_ing` ou `qt_conc` por sexo, cor/raça,
  faixa etária, nacionalidade ou procedência escolar.
- **Finalidade:** descrever quem é atendido pelo sistema — insumo central da discussão de
  equidade do trabalho.
- **Fórmula:** subcoluna ÷ coluna-total × 100, dentro do mesmo recorte.
- **Campos de origem:** por base (`mat`, `ing`, `conc`): `*_fem`/`*_masc`;
  `*_branca`/`*_preta`/`*_parda`/`*_amarela`/`*_indigena`/`*_cornd`; as oito faixas de
  `*_0_17` a `*_60_mais`; `*_nacbras`/`*_nacestrang`;
  `*_procescpublica`/`*_procescprivada`/`*_procnaoinformada`.
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município, IES, curso, área CINE, rede.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE, grau.
- **Pressupostos — auditados nesta fase:** as **cinco** decomposições são **partições exatas**
  nas três bases: 0 linhas divergentes em 720.349, diferença zero no agregado. Nenhuma
  sobreposição, nenhum resíduo.
- **Limitações:**
  - ⚠️ **`*_cornd` e `*_procnaoinformada` são "não declarado", não "nenhum"** — são categorias
    de informação ausente e precisam aparecer no gráfico, nunca ser somadas a outra categoria
    nem removidas do denominador. Em 2024 elas não são desprezíveis.
  - **Turno não pertence a este indicador.** `*_diurno + *_noturno` **não** fecha: o resíduo é
    exatamente a soma EAD (5.189.391 em matrículas), e o turno declarado em EAD é zero.
    Composição por turno só existe no universo presencial — ver a regra transversal acima.
  - Sexo é registrado como binário na base; a plataforma descreve o dado, não a realidade.
  - Percentual sobre células pequenas (um curso num município) é instável e pode identificar
    indivíduos — a interface precisa de um piso declarado.
- **Validação possível:** cada decomposição soma exatamente a coluna-total
  (10.227.266 · 5.010.613 · 1.333.988), com 0 linhas divergentes.

## IND-R-08 — Participação de financiamento estudantil

> ⚠️ **Só como agregado.** A decomposição por tipo está na quarentena (IND-Q-08).

- **Definição:** proporção de matrículas (ou ingressos, ou conclusões) com algum tipo de
  financiamento ou auxílio declarado.
- **Finalidade:** dimensionar a dependência do sistema — sobretudo o privado — de instrumentos
  de financiamento estudantil.
- **Fórmula:** `SUM(qt_mat_financ) / SUM(qt_mat) * 100` (análogo para `ing` e `conc`).
- **Campos de origem:** `cursos.qt_mat_financ`, `qt_ing_financ`, `qt_conc_financ` e as
  respectivas colunas-total.
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município, IES, curso, rede, CINE.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE, grau.
- **Pressupostos — auditados nesta fase:** `qt_*_financ ≤ qt_*` em **todas** as 720.349 linhas,
  nas três bases, com **0 violações**. A coluna-total é, portanto, um numerador seguro.
  Distribuída entre polos como as demais (4.937 de 4.950 cursos variam).
- **Limitações:**
  - ⚠️ **As subcolunas se sobrepõem e não podem ser somadas.** `financ_reemb + financ_nreemb`
    **excede** `financ` em 78.502 matrículas (6.094 linhas divergentes, todas para cima); a mesma
    sobreposição aparece em ingressos (+54.206) e conclusões (+10.721). A leitura consistente é
    que a mesma matrícula pode ter mais de um instrumento e é contada **uma vez** no total e
    **mais de uma** nos tipos.
  - Consequência direta: **FIES, ProUni e "outros" não formam uma composição.** Publicar essa
    divisão produz percentuais que ultrapassam o total.
  - O indicador não distingue bolsa integral de parcial, nem mede valor financeiro.
- **Validação possível:** `qt_mat_financ` = **3.071.136** de 10.227.266 (30,03%);
  `qt_ing_financ` = 1.673.188 de 5.010.613; `qt_conc_financ` = 347.889 de 1.333.988;
  0 violações de contenção nas três.

## IND-R-09 — Participação de reserva de vagas

> ⚠️ **Só como agregado.** A decomposição por subtipo está na quarentena (IND-Q-09).

- **Definição:** proporção de matrículas (ou ingressos, ou conclusões) associadas a alguma
  modalidade de reserva de vagas.
- **Finalidade:** dimensionar o alcance das políticas de reserva no acesso ao ensino superior.
- **Fórmula:** `SUM(qt_mat_reserva_vaga) / SUM(qt_mat) * 100` (análogo para `ing` e `conc`).
- **Campos de origem:** `cursos.qt_mat_reserva_vaga`, `qt_ing_reserva_vaga`,
  `qt_conc_reserva_vaga` e as colunas-total.
- **Unidade:** percentual.
- **Granularidade:** Brasil, região, UF, município, IES, curso, rede, CINE.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE, grau.
- **Pressupostos — auditados nesta fase:** `qt_*_reserva_vaga ≤ qt_*` em todas as 720.349 linhas,
  nas três bases, **0 violações**.
- **Limitações:**
  - ⚠️ **Os 12 subtipos `rv*` não fecham com o total, e falham nos dois sentidos ao mesmo
    tempo:** somam 1.116.988 contra 648.225 em matrículas (+468.763), com **8.490 linhas acima**
    e **391 abaixo**. Sobreposição é esperada (um mesmo ingressante pode ser cotista de escola
    pública *e* PPI), mas o resíduo em 391 linhas não tem explicação nesta base.
  - Somar os subtipos, ou apresentá-los como fatias de um todo, produz percentual acima de 100%.
  - A reserva é fortemente concentrada na rede pública; comparar territórios sem controlar a
    rede confunde política de acesso com composição da oferta.
- **Validação possível:** `qt_mat_reserva_vaga` = **648.225** de 10.227.266 (6,34%);
  `qt_ing_reserva_vaga` = 171.335 de 5.010.613; `qt_conc_reserva_vaga` = 72.157 de 1.333.988;
  0 violações de contenção.

## IND-R-10 — Razão ingressantes / vagas ofertadas

> ⚠️ **Indicador exclusivamente presencial.** Ver pressupostos.

- **Definição:** razão entre ingressos e vagas ofertadas, no mesmo recorte e na mesma dimensão
  de oferta.
- **Finalidade:** indicar quanto da capacidade declarada foi efetivamente preenchida.
- **Fórmula:** `SUM(qt_ing) / NULLIF(SUM(qt_vg_total), 0)`.
- **Campos de origem:** `cursos.qt_ing`, `cursos.qt_vg_total`, `cursos.tp_dimensao`.
- **Unidade:** razão adimensional (ingressos por vaga).
- **Granularidade:** curso → IES → município → UF → região → Brasil, **apenas no presencial**.
- **Dimensões e filtros permitidos:** `tp_dimensao = 'Cursos presenciais ofertados no Brasil'`
  — **fixa**, não selecionável; recorte territorial **oferta**; rede, CINE, grau.
- **Pressupostos — a restrição vem da auditoria:** em EAD, **ingressos e vagas vivem em
  dimensões diferentes**. Os 3.346.116 ingressos estão na dimensão de polo, onde
  `qt_vg_total` é **zero em todas as 673.747 linhas com território**; as 18.583.348 vagas estão
  na dimensão "somente a nível Brasil", onde `qt_ing` é **zero**. Calcular a razão para EAD
  exigiria cruzar duas dimensões — o que o grain proíbe.
- **Limitações:**
  - ⚠️ **Não é "taxa de ocupação de vagas".** O nome foi recusado nesta fase: a base não
    garante que os ingressos do ano provenham das vagas do mesmo ano, nem que vaga não
    preenchida signifique ociosidade. O nome só muda com sustentação metodológica externa.
  - Pode exceder 1 legitimamente (ingressos por programa especial, vagas remanescentes).
  - Denominador zero é frequente no grain de curso — `NULLIF` obrigatório, e células sem vaga
    não são "razão zero", são não aplicáveis.
- **Validação possível:** no presencial, 1.663.040 ÷ 5.075.146 = **0,328**; conferir que
  nenhuma linha de EAD entra na conta; conferir que o denominador territorializado é exatamente
  5.075.146.

## IND-R-11 — Inscrições por vaga ofertada

> ⚠️ **Territorializável apenas no presencial.**

- **Definição:** razão entre inscrições em processos seletivos e vagas ofertadas, no mesmo
  recorte e dimensão.
- **Finalidade:** medir a pressão de demanda sobre a oferta — por curso, área, IES ou território.
- **Fórmula:** `SUM(qt_inscrito_total) / NULLIF(SUM(qt_vg_total), 0)`.
- **Campos de origem:** `cursos.qt_inscrito_total`, `cursos.qt_vg_total`, `cursos.tp_dimensao`.
- **Unidade:** inscrições por vaga.
- **Granularidade:** curso → IES → município → UF → região → Brasil no presencial; em EAD,
  **apenas a nível Brasil**, sem território.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória); recorte territorial **oferta**
  — aplicável somente quando a dimensão for presencial; rede, CINE, grau.
- **Pressupostos:** numerador e denominador coexistem na dimensão presencial (8.658.561 e
  5.075.146) e na dimensão "somente a nível Brasil" (7.060.934 e 18.583.348). Esta segunda é
  calculável, mas **não tem município, UF nem região** — nunca pode aparecer num mapa.
- **Limitações:**
  - ⚠️ **Inscrições não são pessoas distintas.** Uma pessoa pode inscrever-se em vários cursos e
    várias instituições, e a base não permite deduplicar. Chamar o indicador de
    "candidatos por vaga" é incorreto e está vedado em todo texto da plataforma, inclusive nas
    respostas do Analista IA.
  - Processos seletivos têm regras heterogêneas entre IES; a razão não é comparável entre
    instituições como se fosse seletividade.
  - Não misturar as duas dimensões numa única razão.
- **Validação possível:** presencial = 8.658.561 ÷ 5.075.146 = **1,706**; dimensão nacional de
  EAD = 7.060.934 ÷ 18.583.348 = 0,380; as duas nunca somadas.

## IND-R-12 — Titulação do corpo docente

- **Definição:** distribuição percentual dos docentes em exercício por maior titulação —
  sem graduação, graduação, especialização, mestrado, doutorado.
- **Finalidade:** caracterizar a qualificação do corpo docente instalado num território ou rede.
- **Fórmula:** `SUM(qt_doc_ex_dout) / SUM(qt_doc_total) * 100` (análogo para as demais),
  **agregado no grain da IES**.
- **Campos de origem:** `ies.qt_doc_ex_sem_grad`, `qt_doc_ex_grad`, `qt_doc_ex_esp`,
  `qt_doc_ex_mest`, `qt_doc_ex_dout`, `qt_doc_total`.
- **Unidade:** percentual.
- **Granularidade:** IES → município de **sede** → UF → região → Brasil; por rede, categoria
  administrativa, organização acadêmica.
- **Dimensões e filtros permitidos:** as dimensões da tabela de IES; recorte territorial
  **sede** (único aplicável). Outras decomposições igualmente auditadas e exatas: sexo, regime
  de trabalho, faixa etária, cor/raça, nacionalidade.
- **Pressupostos — auditados nesta fase:** as cinco categorias de titulação **particionam
  exatamente** `qt_doc_total` (374.501, 0 linhas divergentes em 2.561). O mesmo vale para as
  outras cinco decomposições, e `qt_doc_ex_int = qt_doc_ex_int_de + qt_doc_ex_int_sem_de`
  (212.899).
- **Limitações:**
  - ⚠️ **Nunca calcular após JOIN com `cursos`** — o denominador infla com o número de polos.
  - Atribuído à sede da IES, não ao local de atuação (ver IND-D-08).
  - **Titulação não é qualidade de ensino.** O indicador descreve uma característica do corpo
    docente; qualquer leitura avaliativa é extrapolação, e a plataforma não a faz.
  - Três IES declaram `qt_doc_total = 0`: denominador zero, célula não aplicável.
  - Regime de trabalho e titulação são eixos independentes — não cruzáveis nesta base, que só
    traz marginais.
- **Validação possível:** as cinco categorias somam 374.501 com 0 divergências;
  `qt_doc_total` = `qt_doc_exe` (mesma medida, não somar as duas).

## IND-R-13 — Concentração territorial da oferta

- **Definição:** grau de concentração de uma métrica entre as unidades territoriais de um
  recorte, medido pela participação das *n* maiores e/ou pelo índice de Herfindahl-Hirschman.
- **Finalidade:** quantificar a desigualdade da distribuição do ensino superior — o contraponto
  quantitativo ao mapa.
- **Fórmula:** participação acumulada das *n* maiores unidades, `Σ(mat_i) / Σ(mat) * 100`;
  HHI = `Σ((mat_i / Σmat) * 100)²`, sobre as unidades com oferta.
- **Campos de origem:** a métrica escolhida (`qt_mat` por padrão) agregada por
  `co_municipio` ou `co_municipio_ies`.
- **Unidade:** percentual acumulado; HHI em pontos (0–10.000).
- **Granularidade:** calculado sobre um conjunto de unidades — Brasil, região ou UF.
- **Dimensões e filtros permitidos:** `tp_dimensao` (obrigatória), recorte territorial
  (obrigatório), rede, CINE.
- **Pressupostos:** o universo de unidades precisa ser declarado — concentração medida **entre as
  unidades com oferta** (3.551) é um número; **entre todas as 5.571** é outro, muito maior.
  Os dois são defensáveis; misturá-los não.
- **Limitações:**
  - **Descritivo, não explicativo.** Concentração alta não indica causa, política nem
    ineficiência, e o Analista IA não pode sugerir isso.
  - Sensível ao recorte: sede concentra muito mais que oferta, por construção — a diferença é
    o próprio fenômeno da EAD, não um achado sobre desigualdade.
  - HHI foi concebido para mercados; aqui é usado como medida de dispersão, e o texto deve
    dizê-lo.
- **Validação possível:** as participações somam 100%; HHI entre 0 e 10.000; recalcular a
  participação da maior unidade por soma direta e conferir contra o ranking.

---

# Bloco C — Quarentena metodológica

**Nenhum destes é implementável nesta fase.** Estão aqui com o motivo técnico para que a
recusa seja auditável — e para que não reapareçam por engano num QueryPlan do Analista IA.

## IND-Q-01 — Taxa de conclusão

`qt_conc ÷ qt_ing` e `qt_conc ÷ qt_mat`. **Decisão do autor em 2026-09-19: não publicar em
nenhuma forma nesta fase.** Concluintes e ingressantes de 2024 pertencem a **coortes
diferentes** observadas no mesmo ano; com um único ano não há como acompanhar uma turma.
Qualquer razão entre eles seria lida como taxa de conclusão e estaria errada. Os nomes
"taxa de conclusão", "taxa de sucesso" e "eficiência" estão vedados em toda a plataforma,
inclusive nas respostas do Analista IA.

## IND-Q-02 — Taxa de evasão

`qt_sit_trancada`, `qt_sit_desvinculado`, `qt_sit_transferido`, `qt_sit_falecido`. Duas
barreiras independentes: (1) evasão é conceito de coorte, e só há 2024; (2) a auditoria
mostrou que **as situações não são subconjunto das matrículas** — a soma das quatro excede
`qt_mat` em **267.780 linhas**, com excesso máximo de 1.883, somando 5.492.084 contra
10.227.266. Não há, nesta base, denominador válido para essas colunas. A semântica de
`qt_sit_*` é **A confirmar** contra o dicionário do INEP.

## IND-Q-03 — Razão aluno / docente

Numerador no grain de curso, denominador no grain de IES, e 93,5% das linhas de curso são polos
de EAD. **Decisão do autor: não resolver atribuindo matrículas à sede** — isso fabricaria uma
razão territorial que o dado não sustenta. Poderá ser reavaliado no futuro **no grain da IES**,
onde numerador e denominador coexistem legitimamente, e apenas ali.

## IND-Q-04 — Evolução, tendência, crescimento

Só existe 2024, confirmado pelo autor. Nenhum indicador de variação temporal é possível, e os
termos "evolução", "tendência", "crescimento" e "queda" estão vedados no texto da UI e nas
respostas do Analista IA.

## IND-Q-05 — Indicadores por mesorregião ou microrregião

`co_mesorregiao_ies` e `co_microrregiao_ies` são códigos **locais à UF**: 15 códigos para
131 mesorregiões. A identidade correta é o par `(co_uf_ies, código)` — e na microrregião nem o
par resolve (383 pares para 382 nomes). Agrupar pelo código funde estados; agrupar pelo nome
funde microrregiões homônimas. Só sai da quarentena com uma chave composta validada.

## IND-Q-06 — Comparação direta entre recortes territoriais

Comparar um número de sede com um de oferta (698 × 3.551) não é um indicador: é um contraste
entre perguntas diferentes. A [ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md)
exige rotulagem obrigatória, e comparações entre recortes devem ser bloqueadas ou
explicitamente sinalizadas — nunca oferecidas como razão calculada.

## IND-Q-07 — Indicadores cruzados com PIB ou densidade populacional

`pib_municipios` e `ibge_densidade_populacional_area_municipios_2010` são contexto
socioeconômico, não indicador educacional, e a densidade é de **2010** — quatorze anos antes do
Censo. Correlação com PIB seria lida como causalidade. Fora de escopo nesta fase.

## IND-Q-08 — Composição do financiamento por tipo (FIES, ProUni, outros)

**Recusado pela auditoria desta fase.** As subcolunas se sobrepõem: `financ_reemb +
financ_nreemb` excede `qt_mat_financ` em 78.502 (6.094 linhas), e as hipóteses de decomposição
interna também falham — `fies + rpfies + outros` excede `financ_reemb` em 3.859, e
`prouni_i + prouni_p + nrpfies + outros` excede `financ_nreemb` em 68.460. Não é partição:
uma matrícula pode ter mais de um instrumento. Apresentar como fatias de um todo produz
percentual acima de 100%. O agregado (IND-R-08) permanece válido.

## IND-Q-09 — Composição da reserva de vagas por subtipo

**Recusado pela auditoria desta fase.** Os 12 subtipos `rv*` somam 1.116.988 contra 648.225 de
`qt_mat_reserva_vaga` (+468.763), e divergem **nos dois sentidos**: 8.490 linhas acima e 391
abaixo. A sobreposição é explicável (cotista de escola pública *e* PPI), o resíduo não.
O agregado (IND-R-09) permanece válido.

---

## Pendências — "A confirmar"

Nenhuma delas bloqueia os indicadores liberados; todas bloqueiam uma extensão específica.

- [ ] **Semântica oficial de `qt_curso`** (IND-D-02): o que distingue os 374 cursos com marcador
  zero, que têm 61.053 matrículas e nenhum concluinte. Exige o dicionário de variáveis do INEP —
  a informação não existe nesta base.
- [ ] **Semântica oficial de `qt_sit_*`** (IND-Q-02): por que as situações excedem `qt_mat` em
  267.780 linhas. Mesmo material.
- [ ] **Correspondência das 5.571 unidades com a Divisão Territorial Brasileira** vigente na data
  do Censo (IND-R-02). Verificado nesta base: 5.571 = 5.570 + Fernando de Noronha, PE com 185
  unidades, DF com 1.
- [ ] **Fechamento da decomposição por forma de ingresso** (`qt_ing_vestibular`, `qt_ing_enem`,
  `qt_ing_egr`, …) — não auditada nesta fase; sem ela, IND-D-04 não admite essa composição.
- [ ] **Fechamento das famílias `qt_parfor`, `qt_apoio_social`, `qt_ativ_extracurricular`,
  `qt_mob_academica`** — não auditadas; nenhum indicador as usa hoje.
- [ ] **Composição por turno** — **candidato futuro ainda não cadastrado**, deliberadamente sem id
  atribuído. A auditoria provou que `*_diurno + *_noturno` é partição exata dentro do presencial,
  o que o tornaria admissível pela ADR-0009; falta decidir se entra como indicador formal numa
  próxima rodada. Até lá, turno é apenas a restrição transversal descrita acima, não um indicador.
- [ ] **Piso de supressão** para células pequenas em IND-R-07 e IND-R-06 (risco de
  identificação em recortes municipais finos). Decisão de UX e ética, ainda não tomada.

## Consistência com a documentação existente

| Documento | Relação |
|---|---|
| [`DATA_DICTIONARY.md`](../../data/DATA_DICTIONARY.md) | Fonte das colunas, tipos e categorias. Sem divergência: o filtro de sentinelas e o total de 5.571 foram reconferidos e estão certos. Esta fase acrescenta o que aquelas 5.571 unidades **são** — 5.570 municípios mais Fernando de Noronha —, corrigindo a denominação, não o número. |
| [`DATA_GRAIN.md`](../../data/DATA_GRAIN.md) | Fonte das regras 2 e 5. Esta fase acrescenta que `qt_vg_total` e `qt_inscrito_total` não existem territorializados em EAD. |
| [`JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md) | Fonte da regra 6 e do JOIN do IND-R-01. Sem divergência. |
| [ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md) | Toda a auditoria desta fase rodou sobre a cópia local; o PostgreSQL não foi consultado. |
| [ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md) | Regra 3. Todo indicador territorial declara o recorte. |
| [ADR-0007](../decisions/ADR-0007-comparacao-de-rede-via-ds-rede.md) | Regra 7 e IND-R-03. Sem divergência. |
| [ADR-0009](../decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md) | Define a fronteira entre os blocos B e C deste documento. |
