# Fechamento técnico (Fase 15) — evidências para o artigo e a defesa

Estado em **2026-11-06**. Consolida o que está em `docs/tcc/devlog/`, nas ADRs e nas medições desta
fase. Nada aqui é decisão nova: cada afirmação aponta a fonte. O que não foi verificado está
marcado como **A confirmar**. O roteiro de demonstração está em [`DEFESA.md`](DEFESA.md).

## 1. Status em uma tabela

| Componente | Status | Evidência |
|---|---|---|
| Auditoria do schema e do grain (IES, cursos, município, população) | **Implementado** | `docs/data/`; devlogs de 2026-09-05 |
| Camada analítica local em DuckDB (ETL literal, 4 tabelas) | **Implementado** | [ADR-0003](decisions/ADR-0003-camada-analitica-local-duckdb.md), `docs/data/ETL_DUCKDB.md` |
| Definição formal dos indicadores (34 fichas) | **Implementado** | `methodology/INDICADORES.md`, [ADR-0009](decisions/ADR-0009-criterio-de-admissibilidade-de-indicadores.md) |
| API de catálogo fechado (indicadores, composições, razões, IES, mapas, comparações) | **Implementado** | `architecture/API.md`, [ADR-0010](decisions/ADR-0010-api-de-catalogo-fechado.md) |
| Frontend: Visão Geral, Instituições, Cursos, Matrículas, Mapa, Comparar | **Implementado** | `frontend/README.md`, devlogs das Fases 6 a 11 |
| Mapas (coroplético, sedes agrupadas, calor) | **Implementado** | [ADR-0015](decisions/ADR-0015-coropletico-por-ind-r-01-e-classes-por-quantis.md) a [ADR-0017](decisions/ADR-0017-mapa-sem-basemap-externo-e-sem-consulta-por-bbox.md) |
| Camada semântica do Analista IA | **Implementado** | [ADR-0019](decisions/ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md) |
| Pipeline Text-to-SQL (QueryPlan → validação → SQL → AST → execução) | **Implementado, sem provedor de LLM** | [ADR-0020](decisions/ADR-0020-queryplan-fechado-validado-contra-o-contexto.md) |
| Provedor de LLM de produção (AWS Bedrock) | **Não implementado** — autor ainda sem acesso; modelo A confirmar | [ADR-0021](decisions/ADR-0021-provedor-llm-via-aws-bedrock.md), [ADR-0022](decisions/ADR-0022-credenciais-aws-por-perfil-sso-fora-do-repositorio.md) |
| Tela do Analista IA no frontend | **Não implementado** | `frontend/src/routes/` não tem rota do Analista |
| Benchmark de modelos | **Parcial** — condição P em 3 modelos locais; medido com Ollama, depois removido | `benchmark/RESULTADOS.md` |
| Piso de supressão de células pequenas | **Não implementado** — substituído por bloqueio por nível; N a definir pelo autor | `INDICADORES.md`, pendências |
| Série temporal | **Não se aplica** — só existe 2024 no Censo | CLAUDE.md, IND-Q-04 |

## 2. Metodologia

**Processo.** Cada fase seguiu o fluxo dados → grain → semântica → consulta → validação →
implementação → teste → documentação (CLAUDE.md, "Workflow"). Regras que estruturam o trabalho:

- **Nada inventado.** Tabela, coluna, código ou resultado não verificado no banco vira "A confirmar"
  (CLAUDE.md, "Regra de ouro"). Os fatos críticos dos dados foram medidos antes de qualquer SQL
  produtivo (devlogs de 2026-09-05).
- **JOIN auditado antes e depois** — grain, chave, cardinalidade, linhas antes/depois e impacto
  nas métricas (`docs/data/JOIN_STRATEGY.md`).
- **Indicador só entra com ficha** de 11 campos e passa pelo critério de admissibilidade
  (ADR-0009); o que não passa fica em quarentena, com o motivo registrado.
- **Decisão estruturante vira ADR** (22 ADRs) e cada fase tem devlog (`DEVLOG_INDEX.md`).
- **Cálculo nunca é delegado ao LLM:** números saem de SQL ou Python; a explicação do Analista é
  determinística (ADR-0020).
- **Desenvolvimento assistido por agente de IA** (Claude Code), com hooks de proteção de segredos
  e bloqueio de comandos destrutivos e subagents de dados, frontend, IA, revisão e documentação
  (devlog de 2026-09-05, configuração do ambiente). Convém declarar isso no artigo.

**Protocolo do benchmark** pré-registrado e revisado antes da medição
(`benchmark/PROTOCOLO.md`); correções no pipeline depois de ver os resultados foram vetadas para
não invalidar a comparação (`benchmark/RESULTADOS.md`, §8).

## 3. Arquitetura

```
PostgreSQL IESB (fonte, somente leitura)
        │  ETL literal, roda uma vez (~35 s)
        ▼
DuckDB local (72 MB) ── API FastAPI (catálogo fechado + Analista IA) ── Frontend React/TS
                                         │
                                         └── LLM (AWS Bedrock — não implementado)
```

| Decisão | Por quê | ADR |
|---|---|---|
| Sessão somente-leitura no PostgreSQL | a conta só tem `SELECT` e não pode criar papel | 0002 |
| DuckDB local | `cursos` tem 609 MB, sem índice e sem permissão para criá-lo; 864 ms → 10 ms | 0003, 0008 |
| Recorte territorial duplo e obrigatório | sede da IES (698 municípios) ≠ local de oferta (3.551) | 0004 |
| API de catálogo fechado | sem consulta livre; regras metodológicas impostas no servidor | 0010 |
| Malha IBGE v4, sem basemap externo | a v3 não tem Boa Esperança do Norte/MT; sem dependência de tiles | 0016, 0017 |
| Comparação sem ordenação | ordem absoluta e relativa têm correlação de postos 0,06 entre UFs | 0018 |
| Camada semântica declarativa, recuperação léxica | determinística e auditável; sem embeddings | 0019 |
| QueryPlan fechado validado contra o contexto | é essa validação, e não o prompt, a defesa contra injeção | 0020 |
| AWS Bedrock como provedor | acesso dado pelo orientador; custo institucional | 0021, 0022 |

## 4. Dados

- **Fonte:** Censo da Educação Superior **2024** (único ano), tabelas de IES e de cursos no Big
  Data IESB, mais `municipio` e `ibge_populacao_estimada`.
- **Fatos que, se ignorados, produzem número errado sem erro de execução** (CLAUDE.md, "Fatos
  críticos"): `cursos` tem grain curso × município × dimensão (720.349 linhas para 46.150
  cursos); contar cursos = `SUM(qt_curso)` (45.776); a linha "Cursos a distância" contamina oito
  colunas territoriais; `tp_rede` tem tipos diferentes nas duas tabelas; população usa código de 6
  dígitos e exige `municipio` como ponte; 28 linhas sentinela em `municipio`; 50 pares duplicados
  de população fora de 2024.
- **ETL validado:** cópia integral e literal; somas de controle iguais à origem — 10.227.266
  matrículas, 5.010.613 ingressantes, 1.333.988 concluintes, 45.776 cursos.
- **Revalidação contra a origem ao vivo em 2026-11-06:** 29 de 30 verificações.
  A única divergência é nova e externa: `ibge_populacao_estimada` ganhou na origem o ano **2023**
  (5.570 linhas, com população idêntica à de 2022) depois do ETL. **2024 é idêntico nas duas
  pontas** (5.571 linhas, 212.583.750 habitantes), e a plataforma só usa 2024: nenhum número muda.
  Mostra, porém, que a premissa "a origem é estática" não é garantida
  (`docs/data/raw/diagnostics/2026-11-06_validacao_duckdb.csv`).

## 5. Indicadores

34 fichas em `methodology/INDICADORES.md`: **11 diretos** (IND-D-01 a D-11), **13 derivados**
(IND-R-01 a R-13) e **10 em quarentena** (IND-Q-01 a Q-10).

| Situação | Indicadores |
|---|---|
| Servidos pela API e pela UI | D-01 a D-09; R-01 (mapa); R-03 a R-07 e R-12 (composições); R-08 a R-11 (razões) |
| Só na camada semântica, sem endpoint | D-10, D-11 |
| Especificados, não servidos | R-02 (cobertura territorial), R-13 (concentração) |
| Em quarentena (inadmissíveis com o dado disponível) | Q-01 conclusão, Q-02 evasão, Q-03 aluno/docente, Q-04 evolução, Q-05 meso/microrregião, Q-06 comparação direta entre recortes, Q-07 PIB/densidade, Q-08 tipos de financiamento, Q-09 subtipos de reserva, Q-10 tipo de seleção |

Pendências registradas nas fichas: **piso de supressão** (hoje há bloqueio por nível: perfil,
financiamento e reserva não saem no município; CINE também não), fichas das composições por
categoria e organização, ficha do tipo de vaga do ingresso, composição por turno (candidata).

## 6. Desenvolvimento (cronologia)

| Fase | Data | Entrega | Testes ao fim |
|---|---|---|---|
| 1–2 | 2026-09-05 | auditoria do schema, acesso read-only, inventário | — |
| 3 | 2026-09-19 | ETL para DuckDB, 30 verificações | — |
| 4 | 2026-09-19 | 33 indicadores formalizados (34 com a Q-10, da Fase 9) | — |
| 5 | 2026-09-26 | API com os 9 diretos | 70 |
| 6 | 2026-10-06 | frontend integrado, `/painel` com dados reais | 35 (front) |
| 7 | 2026-10-06 | filtros territoriais e institucionais | 89 / 54 |
| 8 | 2026-10-06 | Instituições e Cursos, JOIN pré-agregado | 148 / 62 |
| 9 | 2026-10-07 | matrículas, ingressos, vagas, razões | 184 / 67 |
| 10 | 2026-10-07 | mapas | 233 / 94 |
| 11 | 2026-10-07 | comparações | 256 / 101 |
| 12 | 2026-10-07 | camada semântica | 596 |
| 13 | 2026-10-07 | Analista IA (backend) | 1.021 |
| 14 | 2026-10-09 | benchmark (parcial); decisão pelo Bedrock | — |
| — | 2026-10-19 | ambiente AWS (CLI, boto3, perfil SSO) | 1.064 |
| 15 | 2026-11-06 | validação final, remoção do Ollama, este documento | ver §7 |

Formato "backend / frontend". Fonte: `DEVLOG_INDEX.md`.

## 7. Validações (medidas em 2026-11-06)

| Verificação | Resultado |
|---|---|
| Testes do backend (pytest) | 1.051 aprovados, ~25 s |
| Testes do frontend (vitest) | 101 aprovados |
| Lint | ruff limpo; ESLint sem erros (6 avisos `react-refresh` nos componentes shadcn) |
| Tipos | mypy limpo em `api/` e `benchmark/`; tsc limpo. 122 erros de mypy só nos scripts de auditoria (`scripts/analise/`, `scripts/dev/`), fora do produto |
| Build do frontend | aprovado (`NITRO_PRESET=node-server`), 35 s |
| Hooks do agente | autoteste aprovado (49 casos em 4 hooks) |
| Auditorias de consulta | 6 scripts em `scripts/analise/` sem falha. Regravam os CSVs de evidência com nome fixo, e um deles saiu com outra ordem em empates (mesmo conteúdo); o original foi restaurado |
| Dados contra a origem | 29/30 (ver §4) |
| Reprodutibilidade do benchmark | `benchmark.relatorio` regerou `TABELAS.md` e os 6 CSVs a partir dos dados brutos: idênticos byte a byte; prompt, schema e conjunto com o mesmo sha256 dos manifestos |
| Revisão independente (subagent `reviewer`) | nenhuma regressão de segurança ou metodologia; achados em §10 e no relatório da fase |
| Smoke test da API em execução | todos os endpoints 200 com parâmetros válidos; parâmetros inválidos → 422 explicado |
| Varredura de segredos | nenhum segredo no repositório; `.env` e o material de credenciais do orientador ignorados pelo git |

**Desempenho (gargalos só se comprovados).** Todas as consultas levaram de 1,3 a 60 ms. A maior
resposta é a malha municipal: 4,0 MB brutos, **1,1 MB com gzip**, com `Cache-Control` de um dia; o
coroplético municipal tem 663 KB (107 KB com gzip). O MapLibre (1,07 MB) fica num chunk carregado
só na rota `/mapa`. **Nenhum gargalo comprovado; nada foi otimizado nesta fase.**

**Correção feita nesta fase.** O smoke test revelou uma regressão introduzida pela remoção do
Ollama: sem provedor, até perguntas resolvidas sem LLM recebiam 503. Corrigido (o provedor
indisponível só falha quando o modelo é de fato chamado) e coberto por teste de regressão.
A revisão independente levou a mais quatro ajustes pequenos: `LLM_PROVIDER` passou a aceitar só
`bedrock` (erro de digitação falha na partida), textos que ainda falavam em modelo "local", chaves
do `.env.example` que nenhum código lia, e o relatório do benchmark deixou de quebrar com rodadas
só do bloco de sistema.

## 8. Benchmark (Fase 14)

- **Tarefa:** pergunta → QueryPlan (o modelo não escreve SQL). 28 casos que chegam ao modelo, com
  plano e SQL de referência escritos à mão, e 12 casos que a camada deve barrar antes.
- **Resultado (condição P, 3 repetições, caso certo nas 3):** `gpt-oss:20b` 7/28 (IC 95%
  12,7–43,4%), `qwen3:8b` 3/28, `qwen2.5-coder:14b` 2/28. Diferenças **não significativas**
  (Cochran Q = 4,67, p = 0,097).
- **Achado de segurança:** em 252 execuções, **nenhum plano errado virou resposta**; as 44
  respostas entregues estavam todas corretas.
- **Bloco de sistema:** 12/12 resolvidas sem chamar o modelo; situação ideal em 10/12 (as duas
  divergências são de rótulo).
- **Diagnóstico:** parte das falhas vem do pipeline (teto de 1.024 tokens, duas convenções fora do
  prompt, `limit` e `visualization_hint` rejeitando planos corretos), ainda **não corrigida**.
- **Status:** parcial e histórico. Foi medido com modelos locais via Ollama, que o autor
  determinou remover do projeto em 2026-11-06. O conjunto de casos, os critérios e o relatório
  continuam no repositório; a medição de modelos volta quando houver o provedor Bedrock.

## 9. Resultados

O que a plataforma entrega hoje, todo com dado real do Censo 2024:

- painel por Brasil, região, UF e município, com filtros de rede, categoria, organização e
  dimensão de oferta, e o recorte territorial sempre declarado;
- composições (rede, categoria, organização, dimensão, grau, área CINE, titulação docente, perfil)
  e razões (financiamento, reserva de vagas, ingressantes e inscrições por vaga);
- tabela paginada de IES;
- mapa coroplético de matrículas por 100 mil habitantes (Brasil: 10.224.686 matrículas com
  território sobre 212.583.750 habitantes ≈ 4.810), mapa de sedes e mapa de calor;
- comparação de 2 a 5 unidades territoriais, sem ranking;
- Analista IA: respostas determinísticas para o que a camada resolve (recusa de "evolução" ou
  "tendência", pedidos de esclarecimento, termos não mapeados). Perguntas que exigem o modelo
  dependem do Bedrock.

## 10. Limitações

- **Analista IA sem modelo.** Nenhum provedor implementado; o único benchmark com modelo real
  usou modelos locais, já removidos, e nenhum deles foi utilizável na configuração medida.
- **Sem tela do Analista** no frontend.
- **Retrato transversal:** só 2024; nenhuma análise de evolução.
- **Sem coordenada por IES:** o ponto do mapa é o município de sede (2.561 IES em 698 pontos), e 62
  coordenadas caem fora do próprio polígono.
- **Piso de supressão indefinido:** há bloqueio por nível, mas células de 1 a 9 matrículas seguem
  alcançáveis por combinação de filtros em UF (`INDICADORES.md`).
- **Conjunto do benchmark pequeno (28) e de um único autor**, que também escreveu a camada
  semântica.
- **Edição da malha IBGE v4:** A confirmar.
- **Sem autenticação nem limite de taxa** na API; uma pergunta ao modelo por vez.
- **Origem não é estática** (ver §4).
- **A landing ilustrativa promete o que não existe:** comparar instituições (IES × IES ficou fora
  por decisão), conversar com os dados (sem tela) e comparar cidades por nome
  (`frontend/src/data/landing.ts`).
- **O benchmark não é repetível com o código atual:** a medição de modelos saiu com o Ollama; o
  código que a produziu é identificado só pelo hash nos manifestos e não está no git.
- **Nada das Fases 7 a 15 está commitado** (o último commit é a Fase 6).

## 11. Trabalhos futuros

1. Implementar a fábrica Bedrock cumprindo os 8 requisitos de `architecture/AI_ANALYST.md`
   (prazo total, sem nova tentativa, teto de bytes, perfil SSO explícito, 503 limpo, temperatura e
   tokens, saída por *tool use*, limite de volume) e medir o modelo escolhido com o mesmo conjunto.
2. Corrigir os defeitos do pipeline que o benchmark apontou, declarados como nova versão do
   protocolo.
3. Tela do Analista IA, consumindo só specs de visualização validadas.
4. Piso de supressão sobre o denominador, em qualquer nível.
5. Servir R-02 e R-13; ampliar o Analista para composições e JOIN.
6. Série temporal quando houver mais de um ano do Censo.

## 12. Onde está cada evidência

| Para o capítulo de… | Arquivos |
|---|---|
| Dados | `docs/data/DATA_DICTIONARY.md`, `DATA_GRAIN.md`, `JOIN_STRATEGY.md`, `ETL_DUCKDB.md`, `docs/data/raw/diagnostics/*.csv` |
| Indicadores | `docs/tcc/methodology/INDICADORES.md`, ADR-0009 |
| Arquitetura | `docs/tcc/architecture/API.md`, `AI_ANALYST.md`, ADRs 0002–0022 |
| Desenvolvimento | `docs/tcc/DEVLOG_INDEX.md` e `docs/tcc/devlog/` |
| Benchmark | `docs/tcc/benchmark/PROTOCOLO.md`, `RESULTADOS.md`, `TABELAS.md`, CSVs e `resultados/` |
| Validação | `tests/`, `frontend/src/test/`, `scripts/analise/`, `scripts/etl/validar_duckdb.py` |
