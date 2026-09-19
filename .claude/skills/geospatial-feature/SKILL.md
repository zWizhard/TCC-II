---
name: geospatial-feature
description: Implementar ou ajustar camada de mapa — heatmap, pontos, clusters, coroplético municipal, consulta por bbox/zoom e performance. Use em qualquer tarefa que toque o mapa MapLibre.
---

# geospatial-feature

Base: MapLibre GL JS + GeoJSON. Chave espacial: **código IBGE municipal** — nunca nome textual.

## 1. Decidir o modo

- **Heatmap** — densidade contínua; bom para "onde há concentração", ruim para valor exato.
- **Pontos / clusters** — entidades individuais (IES); clusterizar acima de ~algumas centenas de features.
- **Coroplético municipal** — valor por município. Exige normalização: contagem bruta por município
  desenha o mapa da população, não o fenômeno. Escolha e documente o denominador.

## 2. Dados

Confirme o grain do que vai ao mapa (município-ano? IES?). Uma feature por unidade espacial —
duplicata vira polígono pintado duas vezes ou ponto sobreposto.
Municípios sem dado: distinga **zero real** de **ausente** e represente-os de forma diferente.

Malha municipal: usar geometria de fonte oficial (IBGE), simplificada por nível de zoom.
Registre a versão/ano da malha usada — fronteiras e códigos mudam entre edições.

## 3. Performance (requisito, não detalhe)

Consultar por **bbox + zoom + filtros ativos**, não carregar o Brasil inteiro.
Agregar no servidor: Brasil → Região → UF → Município conforme o zoom.
Simplificar geometria por zoom; geometria de zoom baixo não precisa de precisão métrica.
Antes de enviar um payload grande, **meça** — nº de features, tamanho em KB, tempo até o primeiro
render. Se passar de alguns MB, mude a estratégia (agregação, tiles vetoriais, ou recorte por bbox).

Nunca despejar milhares/milhões de features no navegador sem medir.

## 4. Interação

Zoom, pan, hover, popup, clique, seleção. Ligação **bidirecional** com o dashboard: filtrar no
dashboard atualiza o mapa; selecionar no mapa filtra o dashboard. Evite loop de eventos entre os dois.
Debounce em movimento de mapa que dispara consulta.

## 5. Legibilidade e acessibilidade

Escala de cor adequada ao tipo de dado (sequencial vs divergente); classes explicadas na legenda;
não confiar só em cor (padrão/rótulo/tooltip). Controles do mapa alcançáveis por teclado.
Sempre haver uma alternativa tabular ao que o mapa mostra.

## Encerramento

Se o algoritmo de heatmap, a estratégia de agregação por zoom ou a normalização do coroplético for
uma decisão nova, chame `tcc-documentarian` — isso vira ADR.
