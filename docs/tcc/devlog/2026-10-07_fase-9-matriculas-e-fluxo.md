# Fase 9 — Matrículas, ingressos e vagas

## Objetivo

Servir de ponta a ponta (SQL, API, interface e testes) as análises de estudantes que o Censo 2024
sustenta: perfil (IND-R-07), financiamento (IND-R-08), reserva de vagas (IND-R-09), ingressantes
por vaga (IND-R-10) e inscrições por vaga (IND-R-11). Nenhuma taxa de conclusão, evasão ou leitura
temporal foi implementada.

## Trabalho realizado

- **Auditoria:** `scripts/analise/auditar_fluxo.py`, com 45 testes sobre o DuckDB local e saída em
  `docs/data/raw/diagnostics/2026-10-07_fluxo.csv`. Inventário de `cursos`: `qt_mat` (52 colunas),
  `qt_ing` (63), `qt_conc` (52), `qt_vg_*` (8), inscrições (8) e `qt_sit_*` (4).
- **API:** eixos de composição por sexo, cor/raça, faixa etária, nacionalidade, procedência escolar
  e tipo de ingresso (`api/indicadores.py`, `api/analises.py`); catálogo de razões e
  `api/fluxo.py`; endpoints `GET /api/v1/razoes` e `/api/v1/razoes/{slug}`.
- **Frontend:** rota `/matriculas`, componente `RazaoCard`, contrato zod, cliente e consultas,
  item de navegação "Matrículas e Fluxo" e fixture com respostas reais da API.

As fichas dos indicadores estão em [INDICADORES.md](../methodology/INDICADORES.md) e o contrato dos
endpoints em [API.md](../architecture/API.md).

## Decisões técnicas/metodológicas

As regras de cálculo das razões e o bloqueio municipal estão formalizados na
[ADR-0014](../decisions/ADR-0014-razoes-por-vaga-e-bloqueio-municipal.md). Em síntese: IND-R-10
aceita somente a dimensão presencial; IND-R-11 aceita exatamente uma dimensão por resposta;
numerador e denominador são somados nas mesmas linhas e divididos em Python; denominador zero
resulta em valor nulo; perfil, IND-R-08 e IND-R-09 não são servidos no nível municipal.

Demais decisões:

- IND-R-08 e IND-R-09 exigem o parâmetro `base` (matrículas, ingressantes ou concluintes) e servem
  apenas o agregado, pois os tipos se sobrepõem (IND-Q-08/09).
- A composição dos ingressos por **tipo de vaga** é partição exata (5.010.613 ingressos, 0
  divergências em 720.349 linhas) e passou a ser servida (`por=tipo_ingresso`).
- A composição por **tipo de seleção** não fecha (40.050 linhas acima do total, 130.209 abaixo) e
  entrou em quarentena como IND-Q-10. `qt_ing_proc_seletivo` é zero em todas as linhas.
- Mantidas as quarentenas IND-Q-01 (a interface exibe os cinco totais lado a lado, com aviso, sem
  razão entre eles), IND-Q-02 (`qt_sit_*` soma 5.492.084 e excede `qt_mat` em 267.780 linhas) e
  IND-Q-04. Turno permanece sem ficha.
- Título da página alterado para "Matrículas, ingressos e vagas", porque "fluxo" designa, no INEP,
  trajetória de coorte.

## Validação

Medições de 2026-10-07:

| Indicador | Resultado |
|---|---|
| Perfil | 15 partições exatas (5 decomposições × 3 bases), 0 linhas divergentes |
| Financiamento | 30,03% das matrículas (3.071.136/10.227.266); ingressantes 33,39%; concluintes 26,08%; privada 37,50%, pública 0,50% |
| Reserva de vagas | matrículas 6,34%; ingressantes 3,42%; concluintes 5,41% |
| Ingressantes por vaga (presencial) | 1.663.040/5.075.146 = 0,3277; pública 0,59, privada 0,28 |
| Inscrições por vaga | presencial 1,7061 (pública 5,28, privada 1,02); EAD nacional 7.060.934/18.583.348 = 0,3800 |

Backend: 184 testes aprovados (eram 148), ruff e mypy limpos. Frontend: 67 testes (eram 62),
`tsc` e `eslint` sem erros, `npm run build` concluído. Revisão independente sem item bloqueante;
controles reproduzidos e correções de redação, rótulos e notas aplicadas, com 3 testes novos.

## Problemas/limitações

- **Piso de supressão indefinido.** UF × categoria já devolve células de 1 vínculo; a combinação
  UF × categoria × organização × área × grau tem 378 células de 1–9 matrículas, alcançáveis por
  filtro e agora com atributos sensíveis (cor/raça, reserva, financiamento).
- Sem filtro territorial, o valor geral inclui 41 matrículas de polo sem município que as linhas
  por território excluem (declarado em nota na resposta).
- Vagas remanescentes compõem 33,6% do denominador de IND-R-10 (razão de 0,14 contra 0,42 nas
  vagas novas); 544 de 31.687 linhas têm ingressos acima das vagas.
- Não houve verificação visual no navegador, apenas testes de rota com respostas reais.

> A confirmar: bloqueio municipal de IND-R-08/R-09, mais restritivo que a granularidade das fichas.
> A confirmar: definição INEP dos tipos de vaga do ingresso e ficha correspondente no Bloco B.
> A confirmar: nome da área na navegação ("Matrículas e Fluxo"); a revisão recomenda evitar "fluxo".

## Próximo passo

Definição, pelo autor, do piso de supressão (N) e do nome da área; em seguida, IND-R-01/R-02 e o
mapa real.
