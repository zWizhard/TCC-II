# ADR-0013 — JOIN IES × cursos pré-agregado e recorte da tabela de IES pela sede

- **Data:** 2026-10-06
- **Status:** Aceita

## Contexto

A tabela de instituições (`GET /api/v1/instituicoes`) reúne, por IES, atributos e métricas próprias
da instituição (docentes, técnicos) e métricas de oferta que só existem em `cursos` (cursos,
matrículas, ingressantes, concluintes). Os grains diferem: `ies` tem uma linha por instituição
(2.561 linhas, 2.561 `co_ies`); `cursos` tem grain curso × município × `tp_dimensao` (720.349
linhas para os mesmos 2.561 `co_ies`). Um JOIN direto replica as métricas de IES por linha de
curso: medido no DuckDB local em 2026-10-06, daria 410.207.378 "docentes" contra 374.501 reais.

Há ainda um problema de recorte ([ADR-0004](ADR-0004-recorte-territorial-duplo.md),
[ADR-0012](ADR-0012-semantica-dos-filtros-territoriais.md)): a IES tem uma sede, mas oferta em
vários locais. Filtrar instituições por território e somar a oferta de cada linha mistura os dois
recortes.

## Decisão

1. **Este é o único JOIN `ies` × `cursos` da API.** `cursos` é pré-agregada por `co_ies` antes de
   um `LEFT JOIN` com `ies`, o que torna a relação 1:1.
2. **Na tabela de IES, o filtro territorial vale para a sede.** As métricas de oferta de cada linha
   são o total da instituição em qualquer local de oferta.
3. **Com filtro territorial ativo, os totais das métricas de oferta são devolvidos nulos.** As
   linhas continuam exibindo seus valores; o que não se publica é a soma.

## Alternativas consideradas

- **JOIN direto com agregação posterior:** rejeitado; multiplica as métricas de IES pelo número de
  linhas de curso.
- **Somar os totais de oferta também sob filtro territorial:** rejeitado na revisão independente.
  A soma fabricaria "matrículas do território" divergentes de IND-D-03: as 100 maiores IES com sede
  no PR somam mais de 3 vezes as 711.466 matrículas ofertadas no PR.
- **Restringir a oferta de cada linha ao território filtrado:** não adotado nesta fase.
  > A confirmar: o handoff não registra se esta alternativa foi avaliada.

## Consequências

- Auditoria (skill `join-audit`, detalhe em [JOIN_STRATEGY.md](../../data/JOIN_STRATEGY.md)):
  0 órfãos nos dois sentidos, 0 cursos com mais de uma IES, 2.561 linhas após o JOIN e somas
  preservadas (cursos 45.776; matrículas 10.227.266; ingressantes 5.010.613; concluintes 1.333.988;
  docentes 374.501; técnicos 350.752).
- Os indicadores em quarentena IND-Q-03 e IND-Q-06 não são violados.
- IES sem linha nas dimensões de oferta selecionadas aparecem com nulo, não zero (linhas por
  dimensão: presencial 2.444, EAD polo 791, EAD nacional 793, exterior 27). 15 IES têm matrícula
  zero.
- A interface precisa declarar que a oferta exibida por linha é o total institucional, não a oferta
  no território filtrado; quem busca oferta por território usa os indicadores diretos.
- Qualquer novo cruzamento `ies` × `cursos` deve reutilizar a pré-agregação ou passar por nova
  auditoria de JOIN.
