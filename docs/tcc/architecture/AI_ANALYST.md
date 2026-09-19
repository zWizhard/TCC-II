# Analista IA — arquitetura e segurança

Documento de referência. Carregar apenas em tarefas que envolvam o LLM.
Estado em 2026-09-05: **projetado, não implementado.**

## Restrições de partida

- Orçamento **ZERO**. Nenhum modelo próprio treinado; nenhuma API paga como requisito.
- LLM **local via Ollama**, configurável por `LLM_PROVIDER` e `OLLAMA_MODEL`.
  Trocar de modelo não pode exigir mudança na lógica da aplicação.
- Hardware disponível: RTX 2070 SUPER (8 GB VRAM), 32 GB RAM — ver [`../../ENVIRONMENT.md`](../../ENVIRONMENT.md).
  Faixa viável: modelos de 7–8B em Q4/Q5. Modelo definitivo: **a confirmar** por teste empírico.

## Pipeline

```
Pergunta do usuário
   │
   ▼
Camada semântica ──── resolve termos → entidades, dimensões, métricas
   │                  termo não mapeado = rejeição explícita, nunca improviso
   ▼
LLM (structured output) ──► QueryPlan (Pydantic)
   │
   ▼
Validação semântica ─── métricas/dimensões/filtros existem? agregação válida?
   │                    grain compatível? limit dentro do teto?
   ▼
Geração de SQL ──────── feita pelo BACKEND a partir do plano, não copiada do modelo
   │
   ▼
Validação AST (SQLGlot) ─ allowlist de schemas/tabelas (inclusive em CTE e subquery)
   │                      statement único, somente SELECT, LIMIT obrigatório
   ▼
Execução read-only ───── usuário somente-leitura + timeout + limite de linhas
   │
   ▼
Resultado (números do banco) ──► Análise em SQL/Python
   │
   ▼
Spec de visualização validada ──► Explicação gerada pelo LLM
```

**O LLM interpreta. A aplicação valida. O backend gera e valida o SQL.**
O modelo nunca emite SQL que vá direto ao banco e nunca calcula número relevante.

## QueryPlan

Campos: `intent`, `entity`, `metrics`, `dimensions`, `filters`, `group_by`, `having`,
`order_by`, `limit`, `visualization_hint`.

Structured output do LLM, parseado por Pydantic. Parse falho é erro — não motivo para
resgate por regex. Plano que não valida contra a camada semântica é **rejeitado**,
nunca "consertado" por adivinhação.

## Camada semântica

Construída **progressivamente a partir do schema real** (ver [`../../data/DATA_DICTIONARY.md`](../../data/DATA_DICTIONARY.md)).
Nunca antes de verificar os dados. Mapeia: entidades, dimensões, métricas, sinônimos,
relacionamentos, agregações válidas e filtros permitidos.

### Ambiguidade

Ambiguidade que **altera o resultado** é esclarecida com o usuário, não resolvida por chute.
Com o schema real de 2024 já auditado, as duas ambiguidades centrais têm magnitude conhecida:

**1. "Universidade"** — *"Quantos municípios possuem mais de 20 universidades?"*

- **IES** no sentido informal (qualquer instituição de ensino superior): **2.561**
- **Organização Acadêmica = Universidade** (categoria oficial): **206**

Um fator de **12×**. O sistema deve perguntar, não escolher.

**2. Recorte territorial** — o município de uma IES é a **sede** ou o **local de oferta**?

- Sede (`ies.co_municipio_ies`): **698** municípios
- Oferta, incluindo polos EAD (`cursos.co_municipio`): **3.551** municípios

Um fator de **5×**. Por [ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md) o recorte é
**dimensão obrigatória** do QueryPlan: um plano territorial que a omita é rejeitado, e a resposta
sempre declara qual recorte usou. Quando a pergunta for ambígua e o recorte mudar o resultado,
o Analista IA **pergunta**.

O gerador de SQL precisa conhecer estes dois eixos e nunca resolvê-los silenciosamente.

## Alvo de execução: DuckDB local, não o banco institucional

Por [ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md), o SQL gerado a partir do
LLM executa **exclusivamente contra o arquivo DuckDB local**, e nunca alcança o PostgreSQL do IESB.
O raio de alcance de uma falha de validação fica contido na máquina local, sobre dado derivado e
descartável.

Isso não dispensa nenhuma camada de validação — continua havendo risco de exfiltração fora da
allowlist e de consulta com custo abusivo. Muda apenas a configuração: o dialeto do SQLGlot passa a
ser **`duckdb`**, e a allowlist aponta para as tabelas locais.

## Segurança — defesa em profundidade

| Camada | Controle |
|---|---|
| 1 | Execução isolada no DuckDB local + conexão somente-leitura ao IESB no ETL |
| 2 | Allowlist de schemas e tabelas |
| 3 | QueryPlan validado antes de gerar SQL |
| 4 | Validação AST (SQLGlot) sobre a árvore, não sobre a string |
| 5 | Timeout + `LIMIT` obrigatórios |
| 6 | Parametrização — valor do usuário nunca concatenado |
| 7 | Log de pergunta, plano, SQL e tempo — sem credenciais |

Bloquear: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`,
`REVOKE`, `MERGE`, `CALL`, `EXECUTE`, múltiplos statements, e qualquer tabela fora da allowlist.

A permissão do banco é a **última** linha de defesa, não a primeira.

### Regras absolutas

- **Nunca** enviar credencial, connection string ou conteúdo de `.env` ao LLM.
- A saída do modelo é **entrada não confiável**: valida-se sempre, executa-se nunca.
- **Nunca** executar JavaScript gerado pelo LLM; nunca renderizar texto do modelo como HTML.

## Visualização

O modelo devolve **spec estruturada**, não código. Tipos permitidos: `kpi`, `table`, `bar`,
`line`, `composition`, `ranking`, `map`, `heatmap`. Spec fora do allowlist é rejeitada pelo frontend.

## Estatística

Cálculo numérico relevante **nunca** é delegado ao LLM: SQL/Python calcula, o modelo interpreta
o resultado já pronto. A explicação não pode transformar correlação em causalidade, e deve
mencionar as limitações do dado quando elas afetarem a leitura.

## Regras de domínio que a camada semântica DEVE impor

Derivadas da auditoria de 2026-09-05 (ver [`../../data/DATA_GRAIN.md`](../../data/DATA_GRAIN.md)).
Um QueryPlan que viole qualquer uma delas é inválido, mesmo que gere SQL executável:

1. Contagem de cursos usa `SUM(qt_curso)` — nunca `COUNT(*)` nem `COUNT(DISTINCT co_curso)`.
2. Agregação territorial exige `co_municipio ~ '^[0-9]{7}$'`.
3. `tp_dimensao` é declarada explicitamente em toda métrica de cursos.
4. Métrica de IES (`qt_doc_*`, `qt_tec_*`) só agrega no grain de IES.
5. Toda resposta declara o recorte territorial e a dimensão usados.

## Pendências

- [ ] Instalar Ollama e escolher o modelo por teste empírico
- [ ] Confirmar host/credenciais do PostgreSQL do IESB
- [ ] Confirmar existência de usuário somente-leitura no banco
- [ ] Confirmar se o banco tem mais anos além de 2024
- [ ] Construir a camada semântica sobre o schema real
