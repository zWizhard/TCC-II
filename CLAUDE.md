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
- Analista IA: LLM local via **Ollama** (orçamento ZERO — nenhuma API paga é requisito).
  Dialeto SQL do SQLGlot = **duckdb**.
- Não trocar biblioteca já adequada por preferência. Sem Kubernetes/microservices/filas.

## Estado atual (2026-09-19)

**Camada analítica local pronta e validada** (ADR-0003). ETL em `scripts/etl/`, cópia em
`data/analytics/censo_2024.duckdb` (72 MB, não versionado), regerável em ~35 s:

```
.venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py [--recriar]
.venv/Scripts/python.exe scripts/etl/validar_duckdb.py
```

As 4 tabelas do escopo (`ies`, `cursos`, `municipio`, `ibge_populacao_estimada`) são cópia
**integral e literal** — nada é filtrado, agregado ou corrigido no ETL. 30/30 verificações,
somas de controle batendo com a origem ao vivo. Consultas de mapa: 864 ms → **10 ms**.
Detalhe em `docs/data/ETL_DUCKDB.md`. **Ainda sem API, frontend ou Analista IA.**

uv, ruff e git 2.55 presentes; **Node/npm e Ollama ausentes** (ver `docs/ENVIRONMENT.md`).
Git em `main` com 1 commit (estrutura inicial), **sem remoto**.

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
- **`tp_rede` é código `'1'/'2'` em IES e rótulo `Pública`/`Privada` em cursos.** Não comparar direto.
  E `tp_rede='1'` inclui as 28 IES "Especial" — não é sinônimo de pública.
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
  (`Pública` inclui as 28 IES "Especial", igual a `tp_rede='1'`.)
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
| Analista IA / Text-to-SQL | `docs/tcc/architecture/AI_ANALYST.md` |
| Índice do devlog | `docs/tcc/DEVLOG_INDEX.md` |
| Decisões (ADR) | `docs/tcc/decisions/` |

Skills disponíveis: `schema-audit`, `join-audit`, `analytics-feature`, `geospatial-feature`,
`text-to-sql`, `release-check`.

Subagents: `data-engineer`, `frontend-geospatial`, `ai-data-analyst`, `reviewer`, `tcc-documentarian`.
