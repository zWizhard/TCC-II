# Fase 10 — Distribuição Territorial e mapas

Data: 2026-10-07

## Objetivo

Entregar a rota `/mapa` com três modos de visualização (coroplético por UF ou município, pontos
agrupados de IES e mapa de calor) sobre MapLibre GL JS, alimentada apenas pela API e pelo DuckDB
local, e fechar a relação indicador ↔ município ↔ geometria.

## Trabalho realizado

- **Dados:** `scripts/etl/baixar_malha_ibge.py` baixa a malha do IBGE (API v4, qualidade mínima) para
  `data/reference/malha/` com manifesto (URL, data, sha256). `scripts/analise/auditar_mapas.py`
  executa 27 verificações, registradas em
  [`2026-10-07_mapas.csv`](../../data/raw/diagnostics/2026-10-07_mapas.csv).
- **Backend:** `api/mapas.py` com `GET /api/v1/mapa/coropletico` (IND-R-01) e
  `GET /api/v1/mapa/malha/{uf|municipio}`; erro `MalhaIndisponivel` (503); compressão gzip na API.
- **Frontend:** rota `/mapa`, componentes em `components/map/`, `maplibre-gl` ^6.13.0, item
  "Distribuição Territorial" no menu e fixtures reais.

Contrato dos endpoints em [API.md](../architecture/API.md); ficha do IND-R-01 em
[INDICADORES.md](../methodology/INDICADORES.md); auditoria do JOIN em
[JOIN_STRATEGY.md](../../data/JOIN_STRATEGY.md).

## Decisões técnicas/metodológicas

- Coroplético representa o IND-R-01 (matrículas por 100 mil habitantes), nunca contagem bruta, com
  classes por quantis e unidade sem oferta tratada como nula
  ([ADR-0015](../decisions/ADR-0015-coropletico-por-ind-r-01-e-classes-por-quantis.md)).
- Malha do IBGE v4 unida por código de 7 dígitos
  ([ADR-0016](../decisions/ADR-0016-malha-territorial-ibge-v4.md)).
- Sem basemap de terceiros e sem consulta por bbox/zoom
  ([ADR-0017](../decisions/ADR-0017-mapa-sem-basemap-externo-e-sem-consulta-por-bbox.md)).
- **Pontos:** a base não possui coordenada por IES (apenas endereço textual e CEP). Um ponto
  equivale a um município de sede, na coordenada de `municipio`; os clusters somam IES, não pontos.
  Não se geocodificou endereço.
- **Mapa de calor:** peso linear (valor do município ÷ maior valor da resposta). Raiz ou logaritmo
  esconderiam a concentração real: 26,7% das matrículas estão nos 10 maiores pontos e 94% dos pontos
  têm peso inferior a 1% do máximo. A legenda declara que a intensidade não tem unidade nem é
  comparável entre filtros.
- **Filtros:** categoria administrativa e organização acadêmica passam a ser aceitas no IND-R-01,
  restringindo apenas o numerador. CINE e grau não foram expostos no mapa.
- **Interação:** o clique em UF ou município grava o filtro na URL; o mapa não grava o próprio
  movimento. Há alternativa tabular paginada em todos os modos.

## Validação

- Coordenadas de `municipio`: 5.571 unidades, sem nulas, zeradas, repetidas ou fora do Brasil; 28
  sentinelas excluídas.
- JOIN `cursos` (pré-agregada) → `municipio` → população 2024: 1:1, 0 órfãos nos dois sentidos,
  3.551 linhas preservadas, 10.224.686 matrículas; população 2024 de 212.583.750.
- IND-R-01: Brasil 4.809,7; UF de 3.305,4 (MA) a 8.325,4 (DF); município com mediana 1.173 e máximo
  30.106 (Urutaí-GO, 1.104 matrículas para 3.667 habitantes).
- Revisão independente sem achado bloqueante; três correções aplicadas: notas com números fixos
  passaram a ser calculadas do recorte; `geral` devolve nulo, não zero, quando não há registro;
  município incoerente com UF/região ou sentinela devolve 422.
- Backend: 233 testes (49 novos), ruff e mypy limpos. Frontend: lint, typecheck, 94 testes (27
  novos) e build. Renderização conferida em Edge headless (WebGL por software), sem erro de console.

## Problemas/limitações

- 62 das 5.571 coordenadas caem fora do próprio polígono (7 são sede de IES, entre elas Salvador e
  Maceió), pois ponto e polígono vêm de fontes distintas; por isso os pontos não são sobrepostos ao
  coroplético municipal. A primeira auditoria, por caixa envolvente, subestimava o problema (10).
- O IND-R-01 compara matrícula no local de oferta com habitante no local de residência; não é taxa
  de escolarização e é instável em município pequeno.
- O mapa de calor nacional é fraco fora de SP/RJ, consequência do peso linear.
- Não verificados: GPU real, toque em celular real, teclado dentro do canvas e `npm run dev`.
- Os testes de malha são pulados se `data/reference/malha/` estiver ausente.
- IND-R-02 e IND-R-13 seguem sem endpoint.

> A confirmar: ano da edição da malha v4 do IBGE (a API não o declara).

## Próximo passo

Confirmar a edição da malha com o IBGE; decidir se `data/reference/malha/` será versionada; avaliar
IND-R-02 e IND-R-13 como complemento quantitativo do mapa; iniciar o Analista IA.
