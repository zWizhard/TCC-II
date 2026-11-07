# ADR-0016 — Malha territorial do IBGE (API v4) servida pela própria API

- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

O coroplético exige geometria de UFs e de municípios. A tabela `municipio` fornece apenas
coordenadas pontuais. A geometria precisa cobrir as 5.571 unidades de `municipio` e unir-se a elas
por chave estável, sem dependência de serviço externo em tempo de execução.

## Decisão

1. A malha vem da **API de malhas do IBGE, versão 4, qualidade mínima**, baixada uma vez por
   `scripts/etl/baixar_malha_ibge.py` para `data/reference/malha/{municipios,ufs}.geojson`.
2. Um `MANIFEST.json` registra URL, data do download e sha256 de cada arquivo; a versão da malha é
   identificada pelo sha256.
3. A malha é servida pela própria API (`GET /api/v1/mapa/malha/{uf|municipio}`) como arquivo
   estático, com cache de 1 dia e gzip. Ausente o arquivo, a API responde 503 (`MalhaIndisponivel`).
4. O JOIN com os dados é feito por `codarea` (texto, 7 dígitos) = `municipio.codigo_municipio_dv`,
   nunca por nome. Verificado: 1:1, 0 órfãos.

## Alternativas consideradas

- **API de malhas v3 (malha 2022, 5.570 feições):** descartada por não conter Boa Esperança do
  Norte/MT (5101837), presente em `municipio` e na população de 2024.
- **JOIN por nome do município:** descartado; a chave por código é exata e já verificada.
- **Malha em qualidade superior:** não adotada; a malha destina-se apenas à visualização.

## Consequências

- A malha é simplificada e serve somente à visualização, não a cálculo de área ou a operações
  espaciais de precisão.
- 62 das 5.571 coordenadas de `municipio` caem fora do próprio polígono (teste ponto-em-polígono),
  porque ponto e polígono vêm de fontes distintas. Por isso os pontos não são sobrepostos ao
  coroplético municipal.
- Os testes de malha são pulados quando `data/reference/malha/` está ausente (clone limpo).
- Permanece em aberto se `data/reference/malha/` será versionada no git.

> A confirmar: ano da edição da malha v4. A API não o declara nem aceita o parâmetro `periodo`.
