# Fase 6 — Integração e estruturação do frontend

## Objetivo

Trazer o frontend criado no Lovable para o repositório oficial e convertê-lo em base para dados
reais: estrutura de pastas, cliente tipado da API, filtros globais, componentes de KPI, gráfico e
tabela, e uma tela real (Visão Geral), preservando a identidade visual.

## Trabalho realizado

- Diretório `frontend/` (131 arquivos) copiado de `github.com/zWizhard/tcc-2`, commit `79a737d`,
  sem `.git` nem artefatos do Lovable; gerenciador npm. Nenhuma dependência adicionada ou removida.
- `src/lib/api/`: única porta para a API, com contrato zod espelhando `api/schemas.py` e três erros
  distintos (envelope da API, API sem resposta, resposta fora do contrato).
- `src/components/` reorganizado em `layout/`, `data/`, `filters/`, `painel/`, `map/`, `landing/` e
  `ui/` (shadcn, intocado).
- Rotas: `/` (landing ilustrativa, não consulta a API) e `/painel` (Visão Geral, somente dados reais):
  9 KPIs nacionais gerados a partir do catálogo `/api/v1/indicadores`, distribuição por Região/UF em
  gráfico de barras e tabela ordenável, rodapé com fonte, ano e data de extração.
- Servidor de desenvolvimento fixado em `localhost:5173`, origem do CORS padrão da API.
- Estrutura, comandos e regras: [frontend/README.md](../../../frontend/README.md).

## Decisões técnicas/metodológicas

Registradas na [ADR-0011](../decisions/ADR-0011-integracao-do-frontend.md): repositório TCC-II como
fonte oficial, stack do Lovable mantida, filtros na URL, consultas no navegador, landing separada
dos dados reais e frontend sem cálculo de indicador.

Textos da landing que contrariavam o retrato transversal de 2024 foram substituídos ("Evolução das
matrículas" → "Matrículas por região"; "Séries históricas" → "Retrato do Censo 2024"; o ano deixou de
ser apresentado como filtro). A [ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md) foi
aplicada na interface: o recorte aparece ao lado de cada número e provém do catálogo.

## Validação

- Linha de base do código recebido: typecheck e build aprovados; lint com 5.065 erros (CRLF e código
  minificado); 2/2 testes falhando.
- Estado final: lint com 0 erros (6 avisos, todos em `components/ui/`); typecheck aprovado; 35/35
  testes em 5 arquivos; build aprovado; pytest do backend 70/70, inalterado.
- Teste de mutação: forçar `recorte="sede"` no cliente derruba 2 testes.
- Conferência em navegador (Edge headless) contra a API real: Matrículas 10.227.266 (2.580 sem
  município), Cursos 45.776, IES 2.561 (317 na rede Pública), coincidentes com as somas de controle.
  Sem erro de console nem rolagem horizontal em 360 px e 1366 px; estado "API indisponível" conferido.
- Fixtures de teste são respostas reais capturadas da API.

## Problemas/limitações

- Node/npm seguem ausentes na máquina; utilizou-se Node 24.21.0 portátil em diretório temporário.
- O build mira Cloudflare Workers (padrão do template); execução local exige
  `NITRO_PRESET=node-server`. Alvo de implantação em aberto.
- Os 2 testes originais falhavam por limitação do roteador no jsdom; corrigido com
  `src/test/render-rota.tsx`.
- O subagente `frontend-geospatial` falhou duas vezes por erro 529; o agente principal concluiu e
  revisou o trabalho.
- `frontend/.env.example` foi barrado pelo hook `protect_secrets`; `VITE_API_BASE_URL` está
  documentada apenas no README.
- Permanecem ilustrativos na landing, por falta de endpoint equivalente: mapa, gráfico "Categoria
  administrativa", KPI "Municípios analisados", abas e filtros do mockup e prévia do Analista IA.
- Em desenvolvimento cada consulta é emitida duas vezes (React StrictMode); não ocorre em produção.
- Nada foi commitado.

> A confirmar: nomes de autor, orientador e instituição na seção "Sobre".

## Próximo passo

Instalação do Node (22.12+ ou 24) e revisão/commit de `frontend/` pelo autor; em seguida, mapa com
MapLibre no nível município e decisão do alvo de implantação.
