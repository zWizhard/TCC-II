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
  components/filters/ filtros globais (Rede, Dimensão de oferta) e seu estado na URL
  components/painel/  blocos da Visão Geral (KPIs nacionais, distribuição territorial)
  components/map/     MapVisual ilustrativo — o mapa MapLibre entrará aqui
  components/landing/ seções da landing (uma por arquivo)
  components/ui/      shadcn/ui gerado — não editar à mão
  data/landing.ts     textos estáticos da landing
  routes/             `/` (landing) e `/painel` (Visão Geral); `routeTree.gen.ts` é gerado
  test/               utilitário de render de rota e fixtures (respostas reais da API)
```

## Regras que o código segue

- **Nenhum formato de resposta é suposto.** `lib/api/schemas.ts` espelha `api/schemas.py`; toda
  resposta é validada e, fora do contrato, vira erro explícito em vez de número errado.
- **Recorte territorial sempre declarado** (ADR-0004): o `recorte` vem do catálogo da API, nunca
  é escolhido pela tela, e aparece ao lado de cada número.
- **Dimensões de oferta:** em nível territorial a API só aceita as de `dimensoes_territoriais`;
  `resolverDimensoes` faz o corte antes da chamada e a tela mostra o que ficou de fora.
- **Retrato transversal de 2024:** nada de "evolução", "tendência" ou série temporal. O ano não é
  filtro.
- **Sem cálculo de indicador no frontend:** só se exibem valores devolvidos pela API.
- **Todo bloco com dados** trata carregando, erro (API fora do ar ≠ erro da API ≠ resposta fora do
  contrato) e vazio.
- **Mock só sai quando existe endpoint real equivalente.** A landing é ilustrativa (não consulta a
  API e está rotulada como demonstrativa); `/painel` usa apenas dados reais.
- **Fixtures de teste são respostas reais** capturadas da API (`src/test/fixtures/`). Se o contrato
  mudar, recapture — não edite à mão.
