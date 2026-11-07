# Fase 8 — Análises de Instituições e de Cursos

## Objetivo

Entregar de ponta a ponta (SQL, API, interface e testes) análises aprofundadas de Instituições de
Ensino Superior e de Cursos, sem duplicar a Visão Geral e restritas ao que os dados do Censo 2024
sustentam metodologicamente.

## Trabalho realizado

- **API** (`api/analises.py`, novo): `GET /api/v1/indicadores/{slug}/composicao?por=`, que decompõe
  um indicador direto por eixo (rede, categoria, organização, dimensão, grau, área, rótulo CINE,
  titulação) e devolve valor e participação percentual; e `GET /api/v1/instituicoes`, tabela
  paginada e ordenada de IES com atributos, docentes, técnicos e oferta. `/metadados` passou a
  publicar `areas_cine` e `graus`.
- **Frontend**: rotas `/instituicoes` e `/cursos`, componentes em
  `frontend/src/components/analise/`, contrato zod e queries em `frontend/src/lib/api/`.
- **Testes**: `tests/test_analises.py` e `frontend/src/test/analises.test.tsx`, com fixtures que são
  respostas reais da API.

Detalhe dos endpoints em [API.md](../architecture/API.md); auditoria do JOIN em
[JOIN_STRATEGY.md](../../data/JOIN_STRATEGY.md); pendências em
[INDICADORES.md](../methodology/INDICADORES.md).

## Decisões técnicas/metodológicas

- JOIN `ies` × `cursos` com pré-agregação por `co_ies` e tabela de IES recortada pela sede, com
  totais territoriais de oferta nulos: [ADR-0013](../decisions/ADR-0013-join-ies-cursos-pre-agregado-e-recorte-pela-sede.md).
- IES sem linha nas dimensões de oferta selecionadas devolvem nulo (ausência), não zero; zeros
  estruturais são declarados em nota.
- As composições realizam fichas já admitidas: IND-R-03 (rede), R-04 (dimensão), R-05 (grau),
  R-06 (área e rótulo CINE) e R-12 (titulação docente). `por=dimensao` só declara IND-R-04 quando
  as dimensões do nível estão inteiras. Categoria administrativa e organização acadêmica são
  publicadas sem ficha própria (partição exata por construção), com pendência registrada.
- Recortes CINE são recusados (422) no nível municipal: bloqueio provisório por nível, não piso de
  supressão.
- A participação percentual é calculada no servidor, sobre todas as categorias antes do limite.
- Não implementados: evolução (só existe 2024), situação (`qt_sit_*` em quarentena, IND-Q-02),
  turno (existe só no presencial e não tem ficha), razão docente/matrícula (IND-Q-03) e
  concluinte/ingressante (IND-Q-01).

Achado: os 374 cursos sem marcador `qt_curso` (pendência de IND-D-02) são exatamente os de
`co_cine_area_geral = 0` ("Programas básicos", grau "Não aplicável"), com 61.053 matrículas e
0 concluintes. A regra oficial do INEP permanece a confirmar.

## Validação

Backend: 148 testes aprovados (eram 89); frontend: 62 (eram 54); ruff, mypy, tsc e eslint sem erro;
build com `NITRO_PRESET=node-server` concluído. As composições fecham com o indicador direto do
mesmo território (UF, região, município); a titulação fecha com IND-D-08 nas 27 UFs (soma nacional
374.501, sem divergências); a tabela de IES, percorrida página a página, soma os totais nacionais.
Revisão independente pelo subagent `reviewer`: nenhum bloqueante; três pontos importantes, dois
corrigidos (totais com território; ficha de `por=dimensao`) e um documentado como pendente.

## Problemas/limitações

- Piso de supressão para células pequenas sem decisão do autor: UF × rótulo CINE tem 741 células
  de 1 a 9 matrículas; município × grau, já servido, tem 2.242.
- `uf=DF` equivale a Brasília e não é atingido pelo bloqueio municipal dos recortes CINE.
- As telas não foram inspecionadas em navegador, apenas por testes de rota em jsdom.
- Nenhum commit foi feito; as Fases 7 e 8 permanecem no working tree.

## Próximo passo

Decisão do autor sobre o piso de supressão e sobre a formalização de turno como indicador; em
seguida, o mapa real (MapLibre).
