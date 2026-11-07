# Frontend — Observatório Inteligente da Educação Superior

Interface web do TCC-II. Consome **somente** a API FastAPI do projeto (`../api`), que por sua vez
lê a cópia local do Censo da Educação Superior 2024. O visual nasceu no Lovable
(`zWizhard/tcc-2`, commit `79a737d`); **este diretório é a fonte técnica oficial** — mudanças
feitas no Lovable precisam ser trazidas para cá manualmente. O prompt original está em
[`docs/PROMPT_LOVABLE.md`](docs/PROMPT_LOVABLE.md).

## Stack

React 19 · TypeScript (strict) · TanStack Start/Router (rotas por arquivo, SSR) · TanStack Query ·
Tailwind CSS 4 · shadcn/ui · Recharts · Zod · Vitest + Testing Library.
A configuração do Vite vem de `@lovable.dev/vite-tanstack-config` (ver `vite.config.ts`).

## Pré-requisitos

- Node.js 22.12+ ou 24 (com npm).
- A API rodando (na raiz do repositório):
  `.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000`

## Comandos

```sh
npm install
npm run dev         # http://localhost:5173 (porta fixa: é a origem liberada no CORS da API)
npm run lint
npm run typecheck
npm test
npm run build
```

### Variável de ambiente

| Variável            | Padrão                  | Uso                                                        |
| ------------------- | ----------------------- | ---------------------------------------------------------- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | URL base da API. Definir em `.env.local` se for diferente. |

Se o frontend for servido em outra origem, inclua-a em `API_CORS_ORIGINS` ao subir a API.

### Build e execução fora do Lovable

`npm run build` usa o alvo padrão do template (Cloudflare Workers) e **`vite preview` não funciona
com ele**. Para rodar o build localmente, gere-o com o preset Node do Nitro (PowerShell):

```powershell
$env:NITRO_PRESET = "node-server"; npm run build
$env:PORT = "5173"; node .output/server/index.mjs
```

## Estrutura

```
src/
  lib/api/            cliente HTTP, contrato (zod) e queryOptions — única porta para a API
  lib/format.ts       números e datas em pt-BR, rótulos de recorte/nível/rede
  components/layout/  Brand, Navbar e Footer (landing), AppShell (área de dados), Container, Section, Panel
  components/data/    KpiCard, DataState (carregando/erro/vazio), ChartCard, RankingBarChart, DataTable, SourceNote
  components/filters/ filtros globais (território, rede, modalidade + "Mais filtros") e seu estado na URL
  components/painel/  blocos da Visão Geral (KPIs do território, distribuição territorial)
  components/analise/ blocos de Instituições, Cursos e Matrículas: ComposicaoCard, RazaoCard, TabelaInstituicoes, useAreaDeDados
  components/map/     mapa MapLibre de `/mapa`: MapaTerritorial (canvas), DistribuicaoNoMapa (consultas, legenda,
                      tabela), estilo.ts (camadas), geo.ts (resposta → GeoJSON, cores, caixas), search.ts;
                      MapVisual é o ilustrativo da landing
  components/landing/ seções da landing (uma por arquivo)
  components/ui/      shadcn/ui gerado — não editar à mão
  data/landing.ts     textos estáticos da landing
  components/comparar/ `/comparar`: Comparacao (seleção das unidades e tabela lado a lado) e search.ts
  routes/             `/` (landing), `/painel` (Visão Geral), `/instituicoes`, `/cursos`, `/matriculas`, `/mapa` e `/comparar`;
                      `routeTree.gen.ts` é gerado por `npm run dev` ou `npm run build` (o vitest não o gera)
  test/               utilitário de render de rota e fixtures (respostas reais da API)
```

## Regras que o código segue

- **Nenhum formato de resposta é suposto.** `lib/api/schemas.ts` espelha `api/schemas.py`; toda
  resposta é validada e, fora do contrato, vira erro explícito em vez de número errado.
- **Recorte territorial sempre declarado** (ADR-0004): o `recorte` vem do catálogo da API, nunca
  é escolhido pela tela, e aparece ao lado de cada número.
- **Dimensões de oferta:** em nível territorial a API só aceita as de `dimensoes_territoriais`;
  `resolverDimensoes` faz o corte antes da chamada e a tela mostra o que ficou de fora.
- **Território:** vale o nível mais específico (município > UF > região); a região nunca é
  enviada junto com a UF, e o município vai sempre com a sua UF (`resolverEscopo`/`filtroDoEscopo`). Os cartões mostram o território selecionado; a
  distribuição desce um nível (Brasil → região ou UF; região → UFs; UF → 20 maiores municípios;
  município → sem nível abaixo).
- **Instituições e Cursos (Fase 8):** `/instituicoes` mostra a composição por categoria
  administrativa e organização acadêmica (IES, docentes ou técnicos), a titulação docente
  (IND-R-12) e a tabela de IES, paginada e ordenada **pela API**; `/cursos` decompõe um indicador
  de cursos por grau (IND-R-05), dimensão de oferta (IND-R-04), área geral e rótulo CINE
  (IND-R-06), com filtros de área e grau. A participação (%) vem calculada pela API. Na tabela de
  IES o território é o da **sede**, e as colunas de curso são o total da instituição em qualquer
  local de oferta. Recortes CINE não são consultados para um único município (piso de supressão
  pendente). Turno, situação e comparação entre anos não existem na tela, e a tela diz por quê.
- **Matrículas e Fluxo (Fase 9):** `/matriculas` mostra os cinco indicadores diretos de fluxo, o
  perfil (IND-R-07: sexo, faixa etária, cor ou raça, procedência escolar, nacionalidade) da base
  escolhida — matrículas, ingressantes ou concluintes —, o tipo de vaga do ingresso, e as razões
  IND-R-08 a R-11 em `RazaoCard`, comparadas por rede, categoria, organização, dimensão, grau,
  área ou território. **A divisão vem da API** (`/api/v1/razoes`), com numerador e denominador
  sempre visíveis; denominador zero aparece como "não se aplica". `resolverDimensoesRazao` reduz
  as dimensões às que a razão admite: IND-R-10 só no presencial; IND-R-11 em dois cartões
  (presencial e EAD "somente a nível Brasil"), nunca somados. Perfil e participações não são
  consultados para um único município. Não há razão entre concluintes, ingressantes e matrículas,
  nem os nomes "taxa de conclusão", "evasão", "taxa de ocupação" ou "candidatos por vaga".
- **Distribuição Territorial (Fase 10):** `/mapa` tem três modos, com o estado na URL (`modo`,
  `unidade`, `metrica`): coroplético de IND-R-01 por UF ou município, municípios de sede de IES
  (pontos/agrupamentos) e mapa de calor de um indicador direto. **Sem basemap, tiles ou servidor
  de fontes:** o fundo é a malha do IBGE servida pela API, o estilo é montado em `estilo.ts` e os
  rótulos são desenhados com a fonte do navegador. O `maplibre-gl` (v6, só ESM) é importado dentro
  de um efeito — nunca no SSR — e o worker dele é um asset do build (`?url` + `setWorkerUrl`).
  **Classe, razão e limites da legenda vêm da API**; o frontend só troca classe por cor e pinta
  por `feature-state` (`promoteId: "codarea"`), sem reenviar geometria a cada filtro. A malha
  municipal (3,9 MB) só é pedida no coroplético por município. O recorte do coroplético é `oferta`
  fixo em `client.ts` — única exceção à regra do catálogo, porque IND-R-01 não tem endpoint de
  catálogo e a API recusa outro recorte. Sem registro de oferta é cinza hachurado (ausência), nunca
  zero. **Um ponto é um município de sede**, na coordenada de referência do município (a base não
  tem coordenada por IES); o agrupamento soma IES, não municípios; pontos nunca se sobrepõem ao
  coroplético municipal. Com um município selecionado o mapa consulta a UF dele e só o destaca.
  Clicar numa unidade grava `uf`/`municipio` nos filtros globais; mover o mapa não escreve na URL,
  e o enquadramento reage só ao território da URL. A tabela sob o mapa é a alternativa em texto.
  Nos testes o `maplibre-gl` é trocado por `src/test/maplibre-falso.ts` (o jsdom não tem WebGL), e
  a malha municipal das fixtures é o recorte real do DF.
- **Modalidade é atalho para dimensões de oferta:** a correspondência vem de `/metadados`; o
  estado na URL continua sendo `dimensao`.
- **Opções de filtro vêm da API** (`/metadados` e `/territorios/municipios`), nunca de lista
  escrita no frontend.
- **Retrato transversal de 2024:** nada de "evolução", "tendência" ou série temporal. O ano não é
  filtro.
- **Sem cálculo de indicador no frontend:** só se exibem valores devolvidos pela API.
- **Todo bloco com dados** trata carregando, erro (API fora do ar ≠ erro da API ≠ resposta fora do
  contrato) e vazio.
- **Mock só sai quando existe endpoint real equivalente.** A landing é ilustrativa (não consulta a
  API e está rotulada como demonstrativa); `/painel` usa apenas dados reais.
- **Fixtures de teste são respostas reais** capturadas da API (`src/test/fixtures/`). Se o contrato
  mudar, recapture — não edite à mão:
  `.venv/Scripts/python.exe scripts/dev/capturar_fixtures_frontend.py` (na raiz) e depois
  `npx prettier --write src/test/fixtures` (aqui).
- **Comparações (Fase 11):** `/comparar` põe de 2 a 5 regiões, UFs ou municípios lado a lado, com
  o Brasil como coluna de referência e o estado na URL (`nivel`, `u=SP,DF,RR`, `rede`). Não usa os
  filtros globais: a seleção é só nível, unidades e rede. **As colunas ficam na ordem escolhida —
  a tela não ordena nem classifica.** Valores absolutos (porte) e relativos (razões e proporções)
  ficam em blocos separados; cada linha mostra código da ficha, unidade, recorte e, nos relativos,
  numerador ÷ denominador, tudo vindo de `/api/v1/comparacoes`. Só os valores relativos têm barra (percentual em
  escala fixa de 0 a 100; a referência fica fora): nos absolutos ela desenharia o porte. Sem registro aparece como traço,
  nunca zero; linha que não se aplica aos filtros mostra o motivo da API. Trocar de nível zera a
  seleção. O padrão são as cinco regiões.
