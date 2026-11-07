# CLAUDE.md — Observatório Inteligente da Educação Superior (TCC-II)

Memória operacional. Curto de propósito. Detalhe fica em `docs/` e só é lido quando a tarefa exigir.

## Projeto

TCC-II de Data Science. Plataforma web para exploração dos dados da **Educação Superior brasileira**
(Censo da Educação Superior — tabelas de **IES** e **Cursos**), hospedadas no **Big Data IESB**.

Escopo: **exclusivamente Educação Superior**. Nunca usar terminologia da Educação Básica.
Nível espacial central: **município** (chave preferencial: código IBGE).

Nome conceitual temporário; pode mudar.

## Arquitetura

```
PostgreSQL IESB (fonte oficial, read-only)
        │  ETL versionado, roda 1x (dado é estático)
        ▼
DuckDB local  ←── dashboard, mapa e Analista IA consultam SÓ isto
        ▲
API (FastAPI + Pydantic) ← Frontend (React + TypeScript)
```

- Camada analítica local em **DuckDB** ([ADR-0003](docs/tcc/decisions/ADR-0003-camada-analitica-local-duckdb.md)):
  `cursos` tem 609 MB sem índice e não podemos criar. SQL do LLM **nunca** toca o banco institucional.
- Mapas: MapLibre GL JS. Coordenadas vêm da tabela `municipio`; coroplético exige malha IBGE (GeoJSON).
- Analista IA: LLM via **AWS Bedrock**, disponibilizada pelo orientador (decisão do autor,
  2026-10-09; região `us-east-1`, credenciais só pelo perfil SSO `tcc-bedrock` da AWS CLI, nunca no
  `.env` — [ADR-0022](docs/tcc/decisions/ADR-0022-credenciais-aws-por-perfil-sso-fora-do-repositorio.md);
  modelo **A confirmar**; provedor ainda não implementado). **Sem inferência paga nem mudança na
  infraestrutura AWS (EC2 inclusa) sem autorização explícita do autor.**
  **Ollama removido do projeto** por decisão do autor (2026-11-06) — não reintroduzir. Sem fábrica Bedrock, perguntas que chegariam ao modelo recebem 503 explicado.
  Dialeto SQL do SQLGlot = **duckdb**.
- Não trocar biblioteca já adequada por preferência. Sem Kubernetes/microservices/filas.

## Estado atual (2026-11-06)

**Camada analítica local pronta e validada** (ADR-0003). ETL em `scripts/etl/`, cópia em
`data/analytics/censo_2024.duckdb` (72 MB, não versionado), regerável em ~35 s:

```
.venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py [--recriar]
.venv/Scripts/python.exe scripts/etl/validar_duckdb.py
```

As 4 tabelas do escopo (`ies`, `cursos`, `municipio`, `ibge_populacao_estimada`) são cópia
**integral e literal** — nada é filtrado, agregado ou corrigido no ETL. 30/30 verificações,
somas de controle batendo com a origem ao vivo. Consultas de mapa: 864 ms → **10 ms**.
Detalhe em `docs/data/ETL_DUCKDB.md`.

**API FastAPI (Fase 5, 2026-09-26)** em `api/`: serve os 9 indicadores diretos (IND-D-01 a D-09)
por brasil/região/UF/município, só do DuckDB (read-only + travas), sem consulta livre. Filtros
(Fase 7): rede, categoria administrativa, organização acadêmica, região, UF e município — o
filtro territorial vale do seu nível para baixo. A API não lê `.env`. Testes: `.venv/Scripts/python.exe -m pytest`. Rodar:
`.venv/Scripts/python.exe -m uvicorn api.main:app`. Detalhe em `docs/tcc/architecture/API.md`.

**Frontend (Fase 6, 2026-10-06)** em `frontend/`: veio do Lovable (`zWizhard/tcc-2`), mas **este
repositório é a fonte oficial** ([ADR-0011](docs/tcc/decisions/ADR-0011-integracao-do-frontend.md)).
TanStack Start/Router + React 19 + Tailwind 4 + shadcn + React Query + Zod — não trocar. Rotas:
`/` (landing **ilustrativa**, não consulta a API) e `/painel` (Visão Geral, **só dados reais**).
Toda chamada passa por `src/lib/api/` (contrato zod espelhando `api/schemas.py`; `recorte` vem do
catálogo). Dentro de `frontend/`: `npm run dev` (fixo em `localhost:5173`, a origem do CORS da API),
`npm run lint | typecheck | test | build`. Fixtures são respostas reais da API
(regravar com `scripts/dev/capturar_fixtures_frontend.py`). **Visão Geral (Fase 7, 2026-10-06):**
5 KPIs em destaque no território selecionado, distribuição um nível abaixo, filtros principais
(território, rede, modalidade) + "Mais filtros".
`npm run build` mira Cloudflare (padrão do template): local exige `NITRO_PRESET=node-server`.
Detalhe em `frontend/README.md`. **Ainda sem tela do Analista IA** (backend desde a Fase 13; mapa real desde a Fase 10).

**Instituições e Cursos (Fase 8, 2026-10-06):** `api/analises.py` serve
`/api/v1/indicadores/{slug}/composicao?por=` (rede, categoria, organização, dimensão, grau, área e
rótulo CINE, titulação docente — IND-R-03/04/05/06/12) e `/api/v1/instituicoes` (tabela paginada
de IES). Rotas `/instituicoes` e `/cursos` no frontend (`components/analise/`). É o **único JOIN
`ies` × `cursos` da API**: `cursos` pré-agregada por `co_ies`, 1:1, auditado em
`docs/data/JOIN_STRATEGY.md`. Na tabela de IES o território é a **sede** e as métricas de curso
são o total da instituição. CINE não é servido no nível municipal (piso de supressão pendente).
Rota nova no frontend exige regerar `routeTree.gen.ts` (`npm run dev` ou `build`; o vitest não gera).

**Matrículas e Fluxo (Fase 9, 2026-10-07):** `api/fluxo.py` serve `/api/v1/razoes/{slug}` —
IND-R-08 financiamento, R-09 reserva de vagas, R-10 ingressantes/vaga (**só presencial**) e R-11
inscrições/vaga (uma dimensão por vez) — com numerador, denominador e comparação por território ou
eixo; `/composicao` ganhou o perfil (IND-R-07) e o tipo de vaga do ingresso. Rota `/matriculas`
(`RazaoCard`). Perfil, R-08 e R-09 bloqueados no nível municipal (**bloqueio por nível, não piso**).
Auditoria: `scripts/analise/auditar_fluxo.py`.

**Distribuição Territorial e mapas (Fase 10, 2026-10-07):** rota `/mapa` (MapLibre GL JS 6, sem
tiles externos — o fundo é a própria malha) com três modos: **coroplético** de IND-R-01
(matrículas por 100 mil hab., UF ou município, classes por quantis **calculadas na API**),
**municípios de sede** (clusters somando IES) e **mapa de calor** (peso linear). `api/mapas.py`
serve `/api/v1/mapa/coropletico` e `/api/v1/mapa/malha/{uf|municipio}`; pontos e calor usam
`/indicadores/{slug}?nivel=municipio`. Malha do IBGE (API **v4**, 5.571 feições, 1:1 por
`codarea`) em `data/reference/malha/`, baixada por `scripts/etl/baixar_malha_ibge.py` — a v3
(2022) não tem Boa Esperança do Norte/MT; **ano da edição v4: A confirmar**. **Não existe
coordenada por IES**: o ponto é o município de sede (2.561 IES em 698 pontos), e 62 coordenadas
caem fora do próprio polígono. População: `ano = '2024'` é **texto**; universo = 5.571 unidades,
sem oferta = **nulo** (2.020), não zero (135). 233 testes no backend, 94 no frontend. Auditoria:
`scripts/analise/auditar_mapas.py`. A API precisa ser reiniciada para servir rota nova (sem `--reload`).

**Comparações (Fase 11, 2026-10-07):** `api/comparacoes.py` serve `/api/v1/comparacoes`
(`nivel` = região/UF/município, 2 a 5 `unidade`, `rede` opcional): lista **fechada** de 10
indicadores, absolutos (porte) e relativos (IND-R-01/03/04/12) separados, Brasil como referência.
Dimensões fixas presencial + polo. **Não ordena nem classifica** (entre UFs, a ordem absoluta e a
relativa têm correlação de postos 0,06). Rota `/comparar` (`components/comparar/`), estado na URL
(`nivel`, `u=SP,DF`, `rede`). Sem IES × IES e sem variação temporal, por decisão.

**Camada semântica (Fase 12, 2026-10-07):** pacote `api/semantica/`
([ADR-0019](docs/tcc/decisions/ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md)) —
modelos Pydantic derivados de `api/indicadores.py` (23 dimensões, 22 métricas, 8 ambiguidades,
15 termos vedados; as 318 colunas com estado de cobertura). Entrada:
`recuperar_contexto(pergunta)` → `ContextoSemantico` (`para_prompt()` **sem** SQL/coluna/tabela;
`para_dict()` para o backend). Recuperação determinística por léxico, sem LLM; termo não mapeado
= rejeição. Termos coloquiais (aluno, professor, candidato, calouro, formado, cota) são **aliases
de intenção**: apontam para a métrica canônica e a resposta usa o termo canônico. 21 sinônimos
`proposto` aguardam o autor. Suíte: 596 testes (340 em `tests/test_semantica.py`, com bateria de
regressão de 129 perguntas). Auditoria: `scripts/analise/auditar_schema_semantico.py`.

**Analista IA (Fase 13, 2026-10-07):** pacote `api/analista/`
([ADR-0020](docs/tcc/decisions/ADR-0020-queryplan-fechado-validado-contra-o-contexto.md)) e
`POST /api/v1/analista/perguntas` (`{pergunta}` → `situacao`, sempre HTTP 200; modelo fora = 503).
O LLM só escolhe ids de um **QueryPlan fechado**, validado contra a camada **e contra o contexto
determinístico da pergunta** — é essa validação, não o prompt, a defesa contra injeção. SQL só de
fragmentos da camada, parametrizado; validador AST por **allowlist** (1 SELECT, 1 tabela, sem
CTE/subquery/JOIN) roda sempre antes de executar. Explicação e análise **determinísticas**; `line`
sempre rejeitado. v1: 11 métricas diretas + 2 razões por vaga, sem JOIN; o resto sai
`nao_suportada`. **Nenhum provedor de LLM implementado** (`ProvedorIndisponivel`: 503 só quando o
modelo é chamado; o resolvido pela camada segue com 200); **frontend ainda não consome o endpoint**; sem
autenticação nem rate limit. Detalhe em `docs/tcc/architecture/AI_ANALYST.md`.

**Benchmark de modelos (Fase 14, 2026-10-09 — parcial):** pacote `benchmark/` (não altera `api/`),
protocolo e resultados em `docs/tcc/benchmark/` (`PROTOCOLO.md`, `RESULTADOS.md`, `TABELAS.md`).
Mede **pergunta → QueryPlan** pelo pipeline de produção: 28 casos que chegam ao LLM (plano e SQL de
referência escritos à mão) + 12 que a camada barra antes. Condição P (produção), 3 repetições:
`gpt-oss:20b` 7/28, `qwen3:8b` 3/28, `qwen2.5-coder:14b` 2/28 — **nenhum modelo local é utilizável
na configuração atual**, e as diferenças não são significativas. Nenhum plano errado virou
resposta. Medido com Ollama, hoje **removido**: os resultados são registro histórico, e a medição
de modelos saiu do executor até existir a fábrica Bedrock. Defeitos do pipeline apontados e ainda
**não corrigidos** (independem de provedor): teto de 1.024 tokens, duas convenções do validador
ausentes do prompt, `limit` e `visualization_hint` rejeitando planos corretos. Rodar:
`python -m benchmark.executar --validar-conjunto | --rotulo <nome>` (só bloco de sistema);
agregar: `python -m benchmark.relatorio`.
**Decisão do autor (2026-10-09):** produção usará AWS Bedrock
([ADR-0021](docs/tcc/decisions/ADR-0021-provedor-llm-via-aws-bedrock.md)); provedor não implementado.

**Validação final (Fase 15, 2026-11-06):** release-check completo + revisão independente; 1.051
testes no backend, 101 no frontend, build ok. Consolidação para o artigo em
`docs/tcc/FECHAMENTO_TECNICO.md` (implementado / parcial / não implementado, limitações) e roteiro
de demonstração em `docs/tcc/DEFESA.md`. Revalidação contra a origem: 29/30 — `ibge_populacao_estimada`
ganhou 2023 na origem depois do ETL; **2024 idêntico**, nenhum número muda. Requisitos da futura
fábrica Bedrock listados em `AI_ANALYST.md`. Rodar as auditorias regrava CSVs de evidência de
nome fixo: conferir o diff antes de manter.

uv, ruff, git 2.55 e **Node 24.21 / npm 11.19** (desde 2026-10-06, em `%LOCALAPPDATA%\Programs\nodejs`)
presentes; **AWS CLI 2.38.1** e
`boto3` desde 2026-10-19 (ver `docs/ENVIRONMENT.md`, seção "Acesso AWS").
Git em `main`, remoto `origin` = `https://github.com/zWizhard/TCC-II.git` (desde 2026-10-06).

**Conexão direta ao banco funciona desde 2026-09-05.** `.env` preenchido pelo autor (não versionado,
e o agente não pode lê-lo — hook `protect_secrets`), `psycopg[binary]` em `pyproject.toml`,
`.venv` criado pelo uv com **Python 3.14.6**. Rodar SQL somente-leitura com:

```
.venv/Scripts/python.exe scripts/db/run_sql.py <arquivo.sql|--query "..."> [--out <dir> --prefix <p>]
```

O script aplica as travas da ADR-0002 em toda conexão e aborta se a sessão não ficar read-only.
Ele precisa de `dangerouslyDisableSandbox` porque a sandbox nega ao processo filho a leitura do `.env`.
Projeto em `C:\Users\Eduardo\Documents\TCC-II`, **fora do OneDrive** (movido em 2026-09-05).

Banco: **PostgreSQL 17.9**, database `iesb`, schema `public`. Host/usuário só no `.env` (não versionado).
Censo **2024** auditado e **conferido contra o banco** — schema em `docs/data/`, brutos em `docs/data/raw/`.
Conta `data_iesb` tem só `SELECT`, sem `CREATEROLE`: a trava read-only é aplicada **na sessão**
pelo pool ([ADR-0002](docs/tcc/decisions/ADR-0002-sessao-somente-leitura.md)).

## Fatos críticos dos dados (verificados 2026-09-05)

Errar qualquer um destes produz número errado sem gerar erro de execução:

- **`cursos` NÃO tem uma linha por curso.** Grain = curso × município × `tp_dimensao`.
  720.349 linhas para 46.150 cursos; 93,5% são EAD replicadas por polo.
- **Contar cursos = `SUM(qt_curso)`** (45.776). Nunca `COUNT(*)` nem `COUNT(DISTINCT co_curso)`.
- **`SUM(qt_mat)` está correto** — métricas são distribuídas entre polos, não replicadas.
  Soma de controle nacional 2024: **10.227.266**.
- **A contaminação por `'Cursos a distância'` atinge OITO colunas de `cursos`**, não só o município:
  `co_municipio`, `no_municipio`, `co_uf`, `sg_uf`, `no_uf`, `co_regiao`, `no_regiao`, `in_capital`
  — as mesmas 11.778 linhas em cada. **Agregação por UF ou região tem o mesmo defeito da municipal:**
  `GROUP BY sg_uf` sem filtro devolve 28 "UFs". Filtrar `~ '^[0-9]+$'` na coluna usada, em qualquer nível.
- **Métrica de IES (`qt_doc_*`, `qt_tec_*`) agrega-se na tabela de IES**, nunca após JOIN com cursos.
- **`tp_rede` é código INTEGER `1`/`2` em IES e rótulo `Pública`/`Privada` em cursos.** Não comparar
  direto: no DuckDB, `cursos.tp_rede = ies.tp_rede` estoura com ConversionException (medido
  2026-10-07). E `tp_rede = 1` inclui as 28 IES "Especial" — não é sinônimo de pública.
- **`in_comunitaria`/`in_confessional` são SMALLINT `0`/`1`** nas duas tabelas no DuckDB, não texto
  `'0'`/`'1'` (medido 2026-10-07).
- **Os 374 cursos sem marcador `qt_curso` são os "Programas básicos"** (`co_cine_area_geral = 0`,
  rótulos "ABI …", grau "Não aplicável"; 61.053 matrículas, 0 concluintes — medido 2026-10-06).
  Entram em matrículas e ficam fora da contagem de cursos. **Não existe coluna de situação nem de
  turno em `cursos`**; turno só como `qt_*_diurno/noturno`, e só no presencial.
- **`co_cine_rotulo` vem com aspas literais** (`'"0113P01"'`): remover só para exibir.
- **Só existe o ano 2024** (confirmado pelo autor). É um **retrato transversal**: nada de
  "evolução", "tendência" ou "crescimento" — nem no texto da UI, nem na resposta do Analista IA.
- **Recorte territorial é dimensão obrigatória** ([ADR-0004](docs/tcc/decisions/ADR-0004-recorte-territorial-duplo.md)):
  sede da IES (698 municípios) **ou** local de oferta incl. polos EAD (3.551). Padrão = sede.
  Todo indicador territorial declara o recorte; QueryPlan que o omita é inválido.
- **`nu_ano_censo` é TEXTO** nas duas tabelas: filtrar com `'2024'`, nunca `2024`.
- **`co_municipio_ies` é `character(7)` SEM padding** (verificado 2026-09-05): 7 caracteres exatos,
  `btrim()` é desnecessário. A única coluna com padding real é `nu_cep_ies` (`character(12)`),
  que o projeto não usa.
- **Não existe `NULL` nas tabelas do Censo:** `cursos` é `NOT NULL` nas 223 colunas; `ies` só admite
  em `qt_tec_total`, onde há 0. "Vazio" é string vazia — testar com `btrim(col) = ''`, não `IS NULL`.
- **`ies.ds_rede` é a ponte de rede:** traz `Pública`/`Privada`, os mesmos rótulos de `cursos.tp_rede`.
  Comparar rede entre as tabelas por `ies.ds_rede` ↔ `cursos.tp_rede`, nunca pelos `tp_rede` crus.
  (`Pública` inclui as 28 IES "Especial", igual a `tp_rede = 1`.)
- **`co_mesorregiao_ies`/`co_microrregiao_ies` são códigos locais à UF**, não nacionais (15 códigos
  para 131 mesorregiões). Identidade = `(co_uf_ies, código)`; agrupar só pelo código funde estados.
- **`cursos` não tem NENHUM índice** (720k×223, 609 MB) e não podemos criar: todo filtro é seq scan.
  Medido: 864 ms (presencial) e 1.492 ms (EAD) por agregação. Daí o DuckDB local.
- **Chave municipal = `municipio.codigo_municipio_dv` (7 díg.)**, 0 órfãos. `codigo_municipio` é
  de 6 dígitos e falha em 100% dos casos. **`ibge_populacao_estimada` usa 6 dígitos** —
  `municipio` é a **tabela-ponte** obrigatória, senão o JOIN dá zero linhas em silêncio.
- **`municipio` tem 5.599 linhas, mas só 5.571 são municípios.** As outras 28 são sentinelas:
  26 `'Município Ignorado - <UF>'` (código termina em `00000`) + `9900000` e `9999999` (exterior,
  com coordenadas em Paris e no oceano). Excluir antes de plotar ou usar como denominador.
  O Censo não referencia nenhuma delas.
- **`ibge_populacao_estimada` tem 50 pares `(ano, município)` duplicados com valores divergentes**
  (até 100× de diferença), nos anos 2000–2020. **2024 está limpo**, mas o JOIN precisa filtrar o ano.

Detalhe e provas: `docs/data/`.

## Regra de ouro dos dados

**NUNCA inventar** tabela, coluna, código, categoria, métrica, chave, relacionamento,
granularidade ou resultado. O que não foi verificado no banco escreve-se como **"A confirmar"**.

Antes de SQL produtivo: descobrir o schema real (skill `schema-audit`).

Antes de um JOIN importante: grain A, grain B, chave, cardinalidade, necessidade de pré-agregação.
Depois: linhas antes/depois, duplicações, nulos, impacto nas métricas (skill `join-audit`).
Um JOIN não está correto só porque executou.

Métrica derivada relevante precisa de: definição, fórmula, unidade, grain, fonte, pressupostos, limitações.
Cálculo numérico é feito em SQL/Python — **nunca** delegado ao LLM. Correlação ≠ causalidade.

Tarefa que envolva indicador ou metodologia de métrica: as referências oficiais são
`docs/tcc/methodology/INDICADORES.md` (fichas dos indicadores diretos, derivados e em quarentena)
e a [ADR-0009](docs/tcc/decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md)
(critério de admissibilidade). Não propor indicador fora delas sem passar pelo critério.

## Segurança

- Conexão do Analista IA é **READ ONLY**. Defesa em profundidade: usuário somente-leitura,
  allowlist de schemas/tabelas, QueryPlan validado, parser AST (SQLGlot), timeout, LIMIT.
- Bloquear DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE/CREATE/GRANT/REVOKE.
- **Nunca** enviar credenciais ao LLM. Nunca versionar `.env`, senhas, tokens, keys.
- Nunca executar JavaScript gerado pelo LLM — o frontend só interpreta specs de visualização validadas.

## Regras de IA (resumo)

Fluxo obrigatório: `Pergunta → Camada semântica → QueryPlan (Pydantic) → Validação →
SQL → Validação AST → Execução read-only → Resultado → Análise → Visualização`.

O LLM interpreta; a aplicação valida; o backend gera e valida o SQL.
Ambiguidade que altere o resultado (ex.: "universidade" = IES informal vs. Organização Acadêmica = Universidade)
deve ser esclarecida com o usuário, não adivinhada.

Detalhes: `docs/tcc/architecture/AI_ANALYST.md` (ler só em tarefas de IA).

## Workflow

- Simples: Inspect → Implement → Validate → Document se relevante → Respond.
- Dados: Schema → Grain → Semântica → Query → Validate → Implement → Test → Document.
- IA: Question → Semântica → QueryPlan → Validate → SQL → Validate SQL → Execute →
  Validate result → Visualization → Explanation → Document.

Git: `git status` antes de mudanças importantes. **Não commitar nem dar push automaticamente.**
Nunca `git reset --hard`, `git clean -fd` ou `push --force` sem autorização explícita.

## Economia de contexto

1. Ler este arquivo; 2. localizar os arquivos diretamente relacionados (Glob/Grep antes de abrir);
3. ler só esses; 4. expandir só se necessário.

Não fazer scan do repositório inteiro a cada pedido. Não abrir lockfiles, `node_modules`, builds,
datasets, GeoJSON grande, logs ou binários sem necessidade. Preferir `git diff --stat` antes do conteúdo.
Não repetir CLAUDE.md, docs ou logs nas respostas — resumir. Subagent só quando isolar a tarefa
reduzir o contexto do agente principal; tarefa simples faz-se direto.

## Quando perguntar ao usuário

Se a dúvida puder mudar arquitetura, metodologia, interpretação dos dados, SQL, schema, UX,
indicadores, segurança ou resultado acadêmico — **e não puder ser descoberta com segurança no repositório** —
parar e perguntar. Também perguntar quando for preciso que o usuário envie arquivo/schema/print,
exporte algo, faça login, conceda acesso, configure credencial ou escolha entre alternativas
metodologicamente diferentes. Agrupar dúvidas em uma única mensagem objetiva. Não preencher lacuna com suposição.

Se a informação estiver no repositório, investigar primeiro.

## Documentarian

Ao final de **toda** tarefa que produza mudança persistente relevante (código, arquitetura, config,
análise, schema descoberto, indicador, decisão metodológica, mapa, IA, endpoint, teste, correção
importante), chamar o subagent `tcc-documentarian` **antes** da resposta final, passando um
**TASK HANDOFF compacto** (formato em `.claude/agents/tcc-documentarian.md`).

Não chamar para perguntas, explicações ou exploração sem conclusão. Nunca fazê-lo reler o repositório.

## Referências (carregar só quando a tarefa exigir)

| Assunto | Arquivo |
|---|---|
| Ambiente/máquina, ferramentas ausentes | `docs/ENVIRONMENT.md` |
| Dicionário de dados verificado | `docs/data/DATA_DICTIONARY.md` |
| ETL e camada analítica DuckDB | `docs/data/ETL_DUCKDB.md` |
| Grain das tabelas | `docs/data/DATA_GRAIN.md` |
| Estratégia de JOIN | `docs/data/JOIN_STRATEGY.md` |
| **Indicadores — definição formal** | `docs/tcc/methodology/INDICADORES.md` |
| Scripts de auditoria sobre o DuckDB local | `scripts/analise/` |
| API (endpoints, regras, segurança) | `docs/tcc/architecture/API.md` |
| Frontend (estrutura, comandos, regras) | `frontend/README.md` |
| Analista IA / Text-to-SQL | `docs/tcc/architecture/AI_ANALYST.md` |
| Benchmark de modelos LLM | `docs/tcc/benchmark/PROTOCOLO.md`, `RESULTADOS.md` |
| Índice do devlog | `docs/tcc/DEVLOG_INDEX.md` |
| Decisões (ADR) | `docs/tcc/decisions/` |

Skills disponíveis: `schema-audit`, `join-audit`, `analytics-feature`, `geospatial-feature`,
`text-to-sql`, `release-check`.

Subagents: `data-engineer`, `frontend-geospatial`, `ai-data-analyst`, `reviewer`, `tcc-documentarian`.
