# Fase 4 — Definição formal dos indicadores da plataforma

## Objetivo
Especificar metodologicamente os indicadores que a plataforma poderá publicar, com ficha completa
por indicador, antes de qualquer implementação de API, frontend ou Analista IA.

## Trabalho realizado
Foi executada uma auditoria de suporte de 98 verificações sobre a cópia DuckDB local (sem consultar
o PostgreSQL institucional), cobrindo famílias de colunas até então não verificadas: `qt_vg_*`,
`qt_inscrito_*`, `qt_doc_ex_*`, `qt_tec_*`, `qt_*_financ*`, `qt_*_rv*`, `qt_sit_*`, o perfil de
`qt_mat`/`qt_ing`/`qt_conc`, a semântica de `qt_curso` e a natureza das unidades de `municipio`.
As evidências foram versionadas conforme a [ADR-0005](../decisions/ADR-0005-versionamento-das-evidencias-de-auditoria.md)
em `docs/data/raw/diagnostics/2026-09-19_familias_metricas.csv` (79 verificações) e
`_semantica_metricas.csv` (19), produzidas por `scripts/analise/auditar_familias_metricas.py` e
`auditar_semantica_metricas.py`.

O resultado está em [`docs/tcc/methodology/INDICADORES.md`](../methodology/INDICADORES.md): 11
indicadores diretos (IND-D-01..11), 13 derivados (IND-R-01..13) e 9 em quarentena (IND-Q-01..09),
cada um com ficha de 11 campos (nome, definição, finalidade, fórmula, campos de origem, unidade,
granularidade, dimensões permitidas, pressupostos, limitações e validação possível), além de regras
transversais e pendências. `docs/README.md` foi atualizado. Nada foi commitado.

## Decisões técnicas/metodológicas
Registrada a [ADR-0009](../decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md)
(Aceita), com três condições de admissibilidade válidas para dashboard, mapa, exportações e
Analista IA: `tp_dimensao` explícita, sem padrão universal (regra gêmea da
[ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md)); composição percentual apenas sobre
decomposição com partição provada e evidência versionada; e vedação a qualquer taxa que pressuponha
coorte, dado o ano único — em cálculo e em nomenclatura.

Decisões do autor: taxa de conclusão não publicável sob nenhuma forma; denominador da cobertura
municipal é a dimensão territorial canônica `municipio`, não a tabela de população; razão
aluno/docente mantida em quarentena, vedado resolvê-la atribuindo matrículas à sede; IES individual
permitida para métricas descritivas, sem autorizar ranking ou score de qualidade; renomeações de
"taxa de ocupação de vagas" para "Razão ingressantes/vagas ofertadas" e de "concorrência por vaga"
para "Inscrições por vaga ofertada".

Achados que alteraram indicadores: `qt_curso` é marcador binário (0 ou 1), e os 374 cursos da
diferença entre 46.150 e 45.776 têm 61.053 matrículas, 44.421 ingressantes, 89.269 vagas e zero
concluintes, sem coluna que os distinga — indicador renomeado para "Cursos contabilizados na
oferta". Vaga e inscrição não são territorializáveis em EAD: nas 673.747 linhas de polo com
município, `qt_vg_total` e `qt_inscrito_total` são zero, e 78,5% das vagas (18.583.348 de
23.665.419) estão na dimensão "somente a nível Brasil"; IND-R-10 ficou restrito ao presencial.
Financiamento e reserva de vagas não se decompõem (excesso de 78.502 em 6.094 linhas; subtipos
`rv*` somando 1.116.988 contra 648.225, divergindo nos dois sentidos), sobrevivendo apenas como
agregados. `qt_sit_*` não é subconjunto das matrículas (excede `qt_mat` em 267.780 linhas).

## Validação
Fechamento exato confirmado, com zero divergências, nas 6 decomposições de `qt_doc_ex_*`, nas 14 de
`qt_tec_*`, nas 5 de perfil nas três bases, e nas 2 de `qt_vg_*` e `qt_inscrito_*`. Turno é dimensão
exclusivamente presencial (diurno + noturno = 5.037.875, o total presencial; resíduo igual à soma
EAD). Reconfirmado que `qt_mat`, `qt_ing`, `qt_conc`, `qt_mat_financ`, `qt_mat_reserva_vaga` e
`qt_sit_*` são distribuídas entre polos. O filtro de sentinelas de `municipio` foi reconferido e
devolve 5.571 unidades.

## Problemas/limitações
As 5.571 unidades de `municipio` não são 5.571 municípios: excluída Fernando de Noronha (2605459,
distrito estadual de PE), restam 5.570; adotada a denominação "municípios e equivalentes". O número
não mudou, apenas a denominação.

> A confirmar — **7 pendências**, registradas em
> [`INDICADORES.md`](../methodology/INDICADORES.md):
>
> 1. semântica oficial de `qt_curso`, os 374 cursos não contabilizados (IND-D-02);
> 2. semântica oficial de `qt_sit_*`, que excede `qt_mat` em 267.780 linhas (IND-Q-02);
> 3. correspondência das 5.571 unidades com a Divisão Territorial Brasileira vigente (IND-R-02);
> 4. fechamento da decomposição por forma de ingresso (IND-D-04);
> 5. fechamento das famílias `qt_parfor`, `qt_apoio_social`, `qt_ativ_extracurricular` e
>    `qt_mob_academica` — nenhum indicador as usa hoje;
> 6. composição por turno — **candidato futuro ainda não cadastrado**, sem id atribuído: a
>    auditoria provou que é partição exata dentro do presencial, mas a decisão de transformá-lo
>    em indicador formal fica para uma próxima rodada;
> 7. piso de supressão para células pequenas (IND-R-06 e IND-R-07).
>
> As duas primeiras dependem do dicionário de variáveis do INEP e não se resolvem nesta base.

## Próximo passo
Iniciar a Fase 5 a partir das fichas, sem reabrir decisão metodológica. O projeto segue sem API,
frontend e Analista IA.
