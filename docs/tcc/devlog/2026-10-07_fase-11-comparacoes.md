# Fase 11 — Comparações entre unidades territoriais

## Objetivo

Permitir a comparação entre unidades da Educação Superior (região, UF ou município) sem induzir
leitura de ranking e sem transformar a plataforma em ferramenta genérica de BI.

## Trabalho realizado

- **Auditoria:** `scripts/analise/auditar_comparacoes.py`, com saída em
  `docs/data/raw/diagnostics/2026-10-07_comparacoes.csv` (20 verificações, todas fechando).
- **API:** `api/comparacoes.py` e rota `GET /api/v1/comparacoes` (`nivel` = região, UF ou município;
  de 2 a 5 valores de `unidade`; `rede` opcional). Enums `NivelComparacao` e `TipoComparacao` em
  `api/indicadores.py`; schemas `UnidadeComparada`, `ValorComparado`, `IndicadorComparado` e
  `RespostaComparacao` em `api/schemas.py`.
- **Frontend:** rota `/comparar`, componentes em `frontend/src/components/comparar/`, contrato zod,
  cliente e `queryOptions` em `src/lib/api/`, link "Comparações" no `AppShell`. O estado fica na URL
  (`nivel`, `u`, `rede`); o padrão são as cinco regiões.
- **Documentação de referência** (não duplicada aqui): seção "Comparações" de
  [API.md](../architecture/API.md) e subseção "Comparação entre unidades territoriais" de
  [INDICADORES.md](../methodology/INDICADORES.md).

## Decisões técnicas/metodológicas

Formalizadas na [ADR-0018](../decisions/ADR-0018-comparacao-territorial-sem-ordenacao.md):

1. Compara-se apenas território com território, no mesmo nível. Rede e modalidade entram como
   proporção por unidade (IND-R-03, IND-R-04) e como filtro de rede. IES × IES e variação temporal
   ficaram fora (IND-Q-03, IND-Q-04).
2. Lista fechada de 10 indicadores em dois blocos: absolutos (IND-D-01, D-08, D-02, D-03, D-04,
   D-05) e relativos (IND-R-01, R-03, R-04 e percentual de doutores do IND-R-12). O Brasil aparece
   como coluna de referência, pelas mesmas consultas.
3. Nem a API nem a tela ordenam as unidades. Entre UFs, a ordem por matrículas e a ordem por
   matrículas por 100 mil habitantes têm correlação de Spearman de 0,06; 15 de 27 UFs mudam cinco
   ou mais posições (SP: 1ª em absoluto, 8ª na razão; DF: 1ª na razão, 12ª em absoluto).
4. Ausência não é zero: IES igual a 0 é zero real; demais contagens sem linha e razões com
   denominador zero são nulas.
5. Nenhum JOIN `ies` × `cursos` e nenhuma razão entre tabelas ou recortes (IND-Q-03, IND-Q-06).
6. Base pequena no município gera aviso, não supressão: menos de 100 matrículas, menos de
   100 docentes ou menos de 10 mil habitantes.

## Validação

- API: 256 testes aprovados (inclui `tests/test_comparacoes.py`). Frontend: 101 testes aprovados
  (`comparar.test.tsx`, fixture `comparar.json`); lint, typecheck e build limpos.
- Números de controle do Brasil nas definições da comparação (medidos em 2026-10-07): 10.224.686
  matrículas; 4.809,7 matrículas por 100 mil habitantes; 79,80% na rede privada; 50,73% em EAD;
  53,01% de docentes doutores. Por rede: EAD de 60,9% (privada) e 10,4% (pública); doutores de
  33,6% e 72,4%.
- Revisão pelo subagent `reviewer`: nenhum achado bloqueante. Aplicados ajustes de notas (dimensões,
  perda territorial, célula vazia com rede fixada, IND-Q-01), barras restritas aos indicadores
  relativos e a expressão "municípios e equivalentes".

## Problemas/limitações

- A comparação exclui 2.580 das 10.227.266 matrículas (sem território); o IND-R-04 exclui ainda
  o exterior e 41 matrículas de polo sem município.
- Dos 3.551 municípios com oferta, 2.853 não sediam IES; 1.271 têm de 1 a 99 matrículas
  (304 com 1 a 9) e 135 têm zero. Das 698 unidades de sede, 367 têm menos de 100 docentes.
- Mensagens de erro 422 sobre a quantidade de unidades permanecem em inglês (padrão do Pydantic).
- Nada foi commitado.

> A confirmar: manter apenas o aviso para proporções municipais de base pequena ou estender o
> bloqueio/piso da [ADR-0014](../decisions/ADR-0014-razoes-por-vaga-e-bloqueio-municipal.md) — há
> município com 100% de EAD sobre 4 matrículas.

> A confirmar: o limiar de 100 (matrículas e docentes) do aviso foi definido pelo agente, sem
> validação do autor.

> A confirmar: o sentido exato de "34.479 de 45.776 cursos" na nota de perda territorial (cursos
> retidos na comparação, restrita ao presencial, ou cursos excluídos).

## Próximo passo

Decidir, com o autor, o tratamento das proporções municipais de base pequena e o piso de supressão
ainda pendente em `INDICADORES.md`.
