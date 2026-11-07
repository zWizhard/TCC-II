# Fase 7 — Visão Geral de ponta a ponta com filtros territoriais e institucionais

## Objetivo

Tornar a Visão Geral (`/painel`) a primeira área funcional completa da plataforma — dados → SQL →
API → frontend → visualização → teste —, com poucos indicadores em destaque e filtros confirmados
nos dados do Censo 2024.

## Trabalho realizado

- **API** (`api/indicadores.py`, `consultas.py`, `rotas.py`, `schemas.py`): o endpoint
  `/api/v1/indicadores/{slug}` passou a aceitar `categoria` (6 valores), `organizacao` (5),
  `regiao` (5), `uf` (agora também no nível UF) e `municipio` (código IBGE de 7 dígitos, validado
  por expressão regular e vinculado como parâmetro). Novo endpoint
  `GET /api/v1/territorios/municipios?uf=` lista os municípios da UF presentes no Censo, com
  marcação sede/oferta. `/api/v1/metadados` publica regiões, UFs, categorias (com a rede),
  organizações e a modalidade de cada dimensão de oferta. O bloco `Filtros` da resposta declara
  todos os filtros aplicados.
- **Frontend** (`frontend/src/components/filters/`, `components/painel/`, `lib/api/`,
  `routes/painel.tsx`): filtros principais (Região → UF → Município em cascata, Rede, Modalidade),
  bloco recolhível "Mais filtros" (categoria administrativa, organização acadêmica, dimensões de
  oferta) e "Limpar filtros", com todo o estado na URL. Cinco KPIs em destaque (IES, cursos,
  matrículas, ingressantes, concluintes) no território selecionado; os outros quatro do catálogo
  ficam recolhidos. A distribuição territorial desce um nível: Brasil → região ou UF; região → UFs;
  UF → 20 maiores municípios (o total considera todos); município → sem nível abaixo.
  `KpisNacionais.tsx` foi substituído por `KpisTerritorio.tsx`.
- **Ferramenta** `scripts/dev/capturar_fixtures_frontend.py`: regrava as fixtures de teste do
  frontend a partir de respostas reais da API.

O contrato detalhado está em [API.md](../architecture/API.md) e em
[frontend/README.md](../../../frontend/README.md).

## Decisões técnicas/metodológicas

1. **Semântica do filtro territorial** — registrada na
   [ADR-0012](../decisions/ADR-0012-semantica-dos-filtros-territoriais.md).
2. **Categoria e organização filtradas direto em `cursos`**, sem JOIN com `ies`: os rótulos são
   idênticos nas duas tabelas e constantes por IES (0 divergências nas 2.561 IES).
3. **Modalidade não é parâmetro da API**: `tp_modalidade_ensino` é função de `tp_dimensao`
   (Presencial ↔ 1 dimensão; Curso a distância ↔ 3). O frontend a trata como atalho para um
   conjunto de dimensões, com a correspondência vinda de `/metadados`.
4. **Evolução temporal e filtro de ano não foram implementados**: a base tem apenas 2024
   (IND-Q-04, em quarentena). O ano aparece como informação fixa.
5. **Apenas indicadores diretos (Bloco A)** na tela; nenhum derivado foi adicionado.
6. **O frontend envia o município sempre com a UF**, de modo que um código de outra UF devolva
   vazio em vez de números sob a UF errada (achado da revisão).

Medições no DuckDB local em 2026-10-06:

| Partição | Valores | Soma |
|---|---|---|
| IES por categoria | Privada com fins 1.486; Privada sem fins 758; Pública Estadual 139; Pública Federal 122; Pública Municipal 28; Especial 28 | 2.561 |
| IES por organização | Faculdade 1.897; Centro Universitário 417; Universidade 206; Instituto Federal 39; CEFET 2 | 2.561 |
| IES por região | N 196; NE 604; SE 1.076; S 389; CO 296 | 2.561 |

Matrículas por categoria somam 10.227.266; matrículas territorializáveis por região somam
10.224.686. A lista de municípios tem 3.551 distintos, 698 com sede e 0 nomes divergentes entre as
tabelas.

Em recorte territorial, "cursos", "vagas" e "inscrições" só existem no presencial. O cartão nomeia
a dimensão incluída, pois cartões vizinhos cobrem dimensões diferentes e não são comparáveis
(SP: 7.864 cursos, só presencial, contra 2.441.033 matrículas, presencial + polo).

## Validação

- **Backend:** pytest 89/89 (antes 70); ruff e mypy sem erros. Novos testes cobrem a partição do
  total por categoria e organização, o fechamento região = UFs = municípios nas 5 regiões, a lista
  de municípios, 11 novas combinações recusadas (422) e a coerência dos literais com as duas tabelas.
- **Frontend:** 54/54 testes (antes 35), typecheck, build aprovado e lint com 0 erros (6 avisos
  antigos em `components/ui`).
- **Navegador** (Edge headless, 1366 px) contra a API real: Brasil (2.561 IES; 45.776 cursos;
  10.227.266 matrículas; 5.010.613 ingressos; 1.333.988 concluintes), SP + rede Pública + Pública
  Estadual, e Brasília.
- **Revisão independente:** nenhum achado bloqueante; constantes de controle conferidas por
  `GROUP BY` direto. Dois achados importantes corrigidos (decisão 6 e a declaração da dimensão no
  cartão) e um menor (teste de `valor_sem_territorio` com filtro institucional: 2.209 e 54.581).

## Problemas/limitações

- Layout em 360 px com dados carregados não foi conferido visualmente; apenas a moldura.
- Assimetria conhecida e não corrigida: `uf` + `municipio` incoerentes devolvem 200 vazio, enquanto
  `uf` + `regiao` incoerentes devolvem 422.
- A nota "rede Pública inclui as 28 IES Especial" repete-se em cada cartão quando rede = Pública.
- A distribuição municipal mostra só os 20 maiores, sem paginação.
- Sem mapa real nem Analista IA; indicadores derivados (Bloco B) ainda fora da API.
- Nada foi commitado.

## Próximo passo

Revisão e commit pelo autor; em seguida, mapa municipal com MapLibre (a API já serve o nível
município com coordenadas) ou os indicadores derivados do Bloco B.
