# Analista IA — arquitetura e segurança

Documento de referência. Carregar apenas em tarefas que envolvam o LLM.
Estado em 2026-11-06: **camada semântica (Fase 12) e pipeline do backend (Fase 13) implementados**
— QueryPlan, validação, geração de SQL, validador AST, análise, spec de visualização e endpoint
`POST /api/v1/analista/perguntas`. **Nenhum provedor de LLM implementado:** o Ollama, usado só no
benchmark da Fase 14, foi **removido do projeto** por decisão do autor (2026-11-06), e o provedor
de produção (AWS Bedrock) ainda não existe. Até lá, toda pergunta que chegaria ao modelo recebe 503
explicado; as resolvidas antes do modelo (recusa, esclarecimento, não mapeada) seguem respondidas.
**Sem frontend.**

> **Decisão do autor (2026-10-09): o modelo de produção virá da AWS Bedrock**, disponibilizada
> pelo orientador. Substitui a premissa de LLM exclusivamente local. O provedor Bedrock **ainda
> não está implementado**; ver [Provedor: AWS Bedrock](#provedor-aws-bedrock).

## Restrições de partida

- Nenhum modelo próprio treinado. **Sem custo para o autor**: AWS Bedrock custeada pela
  instituição (decisão do autor, 2026-10-09). O Ollama serviu só ao benchmark da Fase 14 e foi
  removido em 2026-11-06.
- Provedor e modelo configuráveis (`LLM_PROVIDER`, padrão `bedrock`, ainda sem fábrica).
  Trocar de modelo ou de provedor não pode exigir mudança na lógica da aplicação.
- Hardware local: RTX 2070 SUPER (8 GB VRAM), 32 GB RAM — ver [`../../ENVIRONMENT.md`](../../ENVIRONMENT.md).
  Só modelos de até ~8B cabem inteiros na GPU (medido na Fase 14).

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
Validação AST (SQLGlot) ─ allowlist: um SELECT sobre UMA tabela, sem CTE/subquery/JOIN
   │                      statement único, somente SELECT, LIMIT obrigatório
   ▼
Execução read-only ───── usuário somente-leitura + timeout + limite de linhas
   │
   ▼
Resultado (números do banco) ──► Análise em SQL/Python
   │
   ▼
Spec de visualização validada ──► Explicação determinística (backend)
```

**O LLM interpreta. A aplicação valida. O backend gera e valida o SQL.**
O modelo nunca emite SQL que vá direto ao banco e nunca calcula número relevante.

## QueryPlan

Campos: `intent`, `entity`, `metrics`, `dimensions`, `filters`, `group_by`, `having`,
`order_by`, `limit`, `visualization_hint`.

Structured output do LLM, parseado por Pydantic. Parse falho é erro — não motivo para
resgate por regex. Plano que não valida contra a camada semântica é **rejeitado**,
nunca "consertado" por adivinhação.

## Implementação (Fase 13) — `api/analista/`

| Módulo | Papel |
|---|---|
| `plano.py` | `QueryPlan` (Pydantic, congelado, `extra="forbid"`): só ids e enums, sem texto livre |
| `validacao.py` | plano × camada semântica **e** plano × contexto da pergunta; rejeita, nunca conserta |
| `sql.py` | SQL só de fragmentos da camada; todo valor é parâmetro nomeado |
| `validador_sql.py` | AST (SQLGlot/duckdb): exatamente 1 SELECT sobre 1 tabela (sem JOIN, CTE, subconsulta nem alias de tabela), denylist de comandos, allowlist de nós e funções, tabela e colunas da entidade do plano, `LIMIT` ≤ teto |
| `llm.py` | `ProvedorLLM` (Protocol), prompt de sistema, `_FABRICAS` (vazio) e `ProvedorIndisponivel` (503 só quando o modelo é chamado) |
| `analise.py` | soma, média, máx/mín e participação em Python; explicação determinística; `verificar_texto` |
| `visualizacao.py` | `SpecVisualizacao`; o backend decide pela forma do resultado, o hint só desempata |
| `pipeline.py` / `rotas.py` | orquestração, log (`api.analista`) e endpoint |

- **`dimensions` × `group_by`:** `dimensions` declara, sem padrão, `recorte`, `nivel_territorial` e
  `dimensao_de_oferta`; `group_by` só aceita dimensão categórica. Território agrupa-se apenas pelo
  nível.
- **O LLM só é chamado com contexto `pronta`.** Recusa, ambiguidade, termo não mapeado e pedido
  fora da v1 são respondidos pela camada. Pergunta sobre cursos que não diz a dimensão de oferta
  vira esclarecimento (não há padrão).
- **Coerência com o contexto** (defesa contra prompt injection): o plano usa **todas** as métricas
  servidas da pergunta e só elas; recorte, nível, dimensão de oferta e filtros são os da pergunta;
  `group_by` é exatamente o conjunto de dimensões citadas como quebra.
- **Números têm papel** (`ContextoSemantico.numeros_citados`): *limiar* (após "mais de", "menos
  de", "acima/abaixo de", "pelo menos") só entra em `having.valor`, com operador no sentido da
  pergunta e no máximo um por métrica; *limite* ("top N", "os N", "N maiores") só entra em `limit`;
  *código de município* (7 dígitos) só em filtro. Milhar e decimal no formato brasileiro são um
  número só ("100.000", "1,5"). Sem limite na pergunta, `limit` é o padrão (100).
- **Ordem vem da pergunta** (`ContextoSemantico.ordem`): "com mais", "maiores", "top" = decrescente;
  "menores" = crescente; sem pedido, o plano não ordena. Ordem e limite saem na interpretação.
- **Esclarecimento antes do LLM** quando a pergunta deixa em aberto: número sem papel, mais de um
  limiar, "os N" sem ordem, maiores e menores juntos, dois níveis territoriais, limiar ou ordem
  com mais de uma medida. Métrica fora da v1 pedida explicitamente não é trocada pela métrica-base.
- **Travas do entorno:** pergunta com caractere de controle ou de formatação Unicode é inválida;
  o prompt não leva `<`, `>` do usuário nem id de regra; o JSON do plano não pode repetir chave;
  o modelo atende uma pergunta por vez (a segunda recebe 503 `modelo_ocupado`); o cliente do
  provedor **deve** ignorar proxy do ambiente, limitar tamanho da resposta, tokens
  (`LLM_MAX_TOKENS`) e prazo total — travas que existiam no cliente Ollama removido e são
  **requisito** da fábrica Bedrock; erro do motor
  vira `consulta_falhou` (500) e tempo esgotado, 504; `sqlglot` tem teto de versão (`<31`) e o
  validador falha na importação se uma classe da denylist deixar de existir.
- **Escopo v1:** métricas diretas e as razões `ingressantes_por_vaga` e `inscricoes_por_vaga`; uma
  tabela por consulta; quebra por nível territorial e por dimensão categórica enumerada. **Fora:**
  composições, decomposições (sexo, cor/raça, titulação…), rótulo CINE,
  `matriculas_por_100_mil_habitantes` (JOIN) e `financiamento`/`reserva_vagas` (exigem base
  declarada). Município só por código IBGE, e sem o nome nas linhas.
- **Respostas:** `situacao` ∈ respondida, requer_esclarecimento, recusada, nao_mapeada,
  nao_suportada, pergunta_invalida, plano_invalido (todas HTTP 200). Modelo fora do ar = 503;
  resposta que não é um QueryPlan = 502, sem resgate nem nova tentativa.
- **Explicação é determinística**; não há texto gerado pelo LLM na resposta. O SQL validado e
  seus parâmetros aparecem na resposta (transparência acadêmica).
- **Configuração:** `LLM_PROVIDER` (sem fábrica → 503 explicado), `LLM_TIMEOUT_SECONDS`,
  `LLM_MAX_TOKENS`, `ANALISTA_MAX_LINHAS` (≤ 1000).

## Provedor: AWS Bedrock

Decisão do autor em 2026-10-09. O que ela **não** muda: o pipeline, o QueryPlan, a validação
contra a camada e contra o contexto, o gerador e o validador de SQL, a execução só no DuckDB
local. `ProvedorLLM` é a única interface que o pipeline conhece; o Bedrock entra como mais uma
fábrica em `_FABRICAS` (`api/analista/llm.py`).

O que ela muda, e está **A confirmar** com o autor antes de implementar:

| Ponto | Situação |
|---|---|
| Modelo (id no Bedrock) | A confirmar (o exemplo do orientador usa Llama 4 Scout) |
| Região | `us-east-1` (2026-10-19) |
| Credenciais | IAM Identity Center (SSO), perfil `tcc-bedrock` da AWS CLI, credenciais temporárias de ~8 h, sem chave fixa ([ADR-0022](../decisions/ADR-0022-credenciais-aws-por-perfil-sso-fora-do-repositorio.md)). A API continua sem segredo: lerá só o **nome do perfil** e a cadeia padrão do `boto3` resolve o resto |
| Limites de uso e de custo da conta | A confirmar |
| Saída estruturada | No Bedrock depende do modelo (uso de ferramenta com esquema, ou JSON no texto). A confirmar por teste |
| Dependência nova | `boto3` 1.43 no projeto (2026-10-19) |
| Descoberta de modelos | `scripts/aws/descobrir_modelos_bedrock.py`, só leitura com trava no SDK; roda depois do login do autor |

**Requisitos da fábrica Bedrock** (o cliente Ollama removido cumpria os equivalentes; revisão da
Fase 15, 2026-11-06). Nada disso existe ainda; é a lista de aceitação da implementação:

1. **Prazo total** da chamada (`LLM_TIMEOUT_SECONDS`): o `read_timeout` do botocore conta por
   leitura, não pela chamada inteira.
2. **Sem nova tentativa:** `retries={"max_attempts": 1}` — o botocore repete por padrão, o que
   multiplica custo e tempo.
3. **Teto de bytes da resposta** antes de `interpretar_plano` (que não limita o tamanho).
4. **`Session(profile_name=...)` explícito**, para que variáveis `AWS_*` do ambiente não passem à
   frente do perfil SSO; tratar `HTTPS_PROXY` (papel do antigo `trust_env=False`).
5. **Mensagem de 503 limpa:** exceções do botocore e do SSO trazem perfil, ARN e conta; nada disso
   vai ao cliente. Token SSO expirado (~8 h; o provedor fica em `app.state`) → 503 explicado.
6. **Temperatura 0 e `maxTokens` = `LLM_MAX_TOKENS`** enviados de fato.
7. **Saída estruturada por *tool use* chega como dict:** serializá-la anula a checagem de chave
   repetida de `plano.py`. A confirmar por teste com o modelo escolhido.
8. **Limite de volume:** a API não tem autenticação nem rate limit, e o semáforo só limita a
   concorrência, não a quantidade de chamadas pagas.

Consequências que já se conhecem:

- **A pergunta do usuário e o contexto semântico saem da máquina.** O que vai ao modelo continua
  sendo só o prompt de sistema, o contexto (`para_prompt()`: ids e nomes de negócio) e o esquema
  do plano — nenhuma linha da base, nenhum SQL, nenhum nome físico de tabela ou coluna, nenhuma
  credencial. A base é pública (Censo), mas a pergunta digitada passa a trafegar para um terceiro.
- **As regras de segurança não mudam:** credencial nunca vai ao LLM nem é versionada; a saída do
  modelo é entrada não confiável; o SQL segue sendo gerado e validado pelo backend.
- **Deixa de valer "funciona sem rede".** Não há provedor alternativo: o Ollama foi removido por
  decisão do autor (2026-11-06). Sem acesso ao Bedrock, o Analista só responde o que a camada
  semântica resolve sem modelo.
- CLAUDE.md, ADR-0003 e este documento falavam em "LLM local" e "orçamento ZERO": a redação foi
  ajustada onde é fato; a decisão está registrada em ADR própria.

## Benchmark de modelos (Fase 14)

Protocolo em [`../benchmark/PROTOCOLO.md`](../benchmark/PROTOCOLO.md), resultados em
[`../benchmark/RESULTADOS.md`](../benchmark/RESULTADOS.md), código em `benchmark/`. O benchmark usa
o pipeline de produção sem alterá-lo e mede a tarefa **pergunta → QueryPlan** (o modelo não escreve
SQL). O que ele revelou sobre **este pipeline**, independentemente do modelo:

1. **`LLM_MAX_TOKENS = 1024` é pequeno para modelos que raciocinam.** `qwen3` e `gpt-oss` gastam
   o teto no campo `thinking` e param por `length` sem emitir o JSON (resposta 502). O teto foi
   dimensionado na Fase 13 pelo tamanho do plano, sem modelo real.
2. **O cliente não envia `think`.** Cada modelo usa o próprio padrão; para o `qwen3`,
   `think: false` desliga o raciocínio. É um parâmetro de topo da requisição, não de `options`.
3. **O prompt de sistema omite duas convenções que o validador exige:**
   - filtro por uma única unidade territorial (um município, uma UF, uma região) muda o nível
     territorial, e então `intent` tem de ser `distribuicao`, não `valor` — a regra 8 do prompt
     diz "valor (número único)";
   - pergunta de cursos sem dimensão de oferta escolhida mas com quebra por ela ("por modalidade")
     exige declarar as quatro dimensões — a regra 5 diz "os valores citados".
4. **`limit` é o erro mais barato de evitar.** A regra 9 manda omitir `limit` quando a pergunta
   não pede N; o `qwen2.5-coder` o preenche quase sempre, e o plano é rejeitado só por isso
   (`limite_diverge_do_contexto`). O campo poderia sair do esquema enviado ao modelo quando o
   contexto não traz um limite.
5. **`visualization_hint` rejeita planos corretos.** A dica é opcional, mas uma dica incompatível
   invalida o plano inteiro (`visualizacao_incompativel`).
6. **A validação estrita funciona como desenhada:** nenhum plano errado virou resposta. O custo é
   a taxa de rejeição alta com modelos pequenos.
7. **Rótulos da camada, não do sistema:** "Como evoluíram as matrículas?" sai `nao_mapeada`, não
   `recusada` (a flexão verbal de "evolução" não está no léxico); duas medidas de tabelas
   diferentes na mesma pergunta saem `requer_esclarecimento`, não `nao_suportada`. Nos dois casos
   o sistema se abstém corretamente; só o rótulo difere do ideal.
8. **"Top N" sai sempre com `truncado = true`**, como já estava pendente de decisão.

Nenhum desses pontos foi corrigido na Fase 14: mexer no prompt ou no esquema depois de ver os
pilotos invalidaria a comparação. São insumo para a próxima fase.

## Camada semântica

Implementada em `api/semantica/` (Fase 12, 2026-10-07), a partir do inventário das 318 colunas do
DuckDB local. Decisão e alternativas em
[ADR-0019](../decisions/ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md); contagens,
magnitudes e limitações no [devlog da Fase 12](../devlog/2026-10-07_fase-12-camada-semantica.md).

- **Fonte da verdade:** modelos Pydantic imutáveis, exportáveis como JSON. Literais, expressões,
  recortes e limitações são derivados de `api/indicadores.py`. A importação falha com referência
  pendente.
- **Conteúdo:** 4 entidades, 4 relacionamentos, 23 dimensões, 22 métricas, 16 regras de domínio,
  15 termos vedados e 8 ambiguidades. Cada coluna tem exatamente um estado de cobertura (131
  expostas, 187 fora).
- **Entrada:** `recuperar_contexto(pergunta)` → `ContextoSemantico`. A recuperação é determinística
  por léxico, sem LLM, e devolve só os itens casados e suas dependências. Situações possíveis:
  vazia, pergunta longa, recusada, termo não mapeado, requer esclarecimento, lugar não resolvido,
  sem métrica, pronta.
- **Prompt sem schema:** `para_prompt()` não traz SQL, coluna, tabela, predicado nem relacionamento
  — o LLM escolhe apenas identificadores. O detalhe técnico fica em `para_dict()`, para o backend.
  Pergunta limitada a 500 caracteres e prompt a 16.000; a pergunta entra delimitada e rotulada como
  dado não confiável.
- **Sinônimos:** três status. `verificado` (279) é equivalência segura. `alias_de_intencao` (10:
  aluno, estudante, matriculado, universitário → matrículas; professor → docentes; candidato →
  inscrições; calouro → ingressantes; formado → concluintes; cota, cotista → reserva de vagas, só
  o agregado) direciona para a métrica canônica e leva ao prompt a terminologia obrigatória — a
  resposta nunca fala em "alunos" ou "candidatos". `proposto` (21) segue pendente do autor, sai
  marcado no contexto e é listável por `listar_sinonimos_propostos()`.
- **Dimensões que respondem direto (decisão do autor, 2026-10-07):** `gratuito` é atributo de
  curso e nunca equivale a rede pública; `comunitária` e `confessional` são a classificação da IES
  na fonte (Lei nº 12.881/2013; art. 19 da LDB, redação da Lei nº 13.868/2019), nunca inferidas de
  outra variável; `capital` é territorial e segue o recorte, sempre declarado.
- **Recusas:** termos em quarentena (IND-Q-01 a Q-10), denominações vedadas, turno e campus; razão
  entre duas medidas fora do catálogo; ano diferente de 2024. Negação leva a esclarecimento.
- **Ainda não faz:** representar filtro negativo, união nem faixa de valores; resolver município
  ou curso por nome. Limiar, limite e ordem são classificados desde a revisão da Fase 13.

### Ambiguidade

Ambiguidade que **altera o resultado** é esclarecida com o usuário, não resolvida por chute.
Na camada, cada ambiguidade é um objeto com gatilhos, leituras, magnitude medida, pergunta ao
usuário e padrão. **Sem padrão** (sempre perguntam): universidade, faculdade, pública, EAD e
UF-ou-município — esta só nos 8 nomes de UF que também são município, e só quando a palavra colada
ao nome ("estado de", "município de") não decide. **Resolvidas e sempre declaradas:** curso (cursos
contabilizados), recorte (sede) e capital (segue o recorte). Uma pergunta nunca sai "pronta" com
ambiguidade obrigatória pendente (testado). As medições estão em
`docs/data/raw/diagnostics/2026-10-07_semantica_verificacoes.csv`.

As duas ambiguidades centrais:

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
`line`, `composition`, `ranking`, `map`, `heatmap`. Spec fora do allowlist é rejeitada. `line` consta do vocabulário, mas é **sempre rejeitado** nesta base (só há 2024: não existe série temporal).

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

- [x] Comparar modelos locais por teste empírico (Fase 14, 2026-10-09, parcial; Ollama removido em 2026-11-06)
- [x] Região, mecanismo de credenciais e dependência do Bedrock (2026-10-19, ADR-0022)
- [ ] **Provedor AWS Bedrock**: autor fazer o login SSO; rodar a descoberta de modelos; escolher o
      modelo; implementar a fábrica (`LLM_PROVIDER=bedrock`, perfil por variável)
- [ ] Medir o(s) modelo(s) do Bedrock: a medição de modelos foi retirada do executor com o Ollama;
      volta com a fábrica Bedrock (casos, critérios e relatório inalterados)
- [ ] Corrigir o que o benchmark apontou e independe de provedor: teto de tokens, as duas regras
      do prompt, `limit` e `visualization_hint` (`think` era opção do Ollama). Decidir com o autor
      se entra antes da medição no Bedrock (como protocolo v2)
- [x] Host/credenciais do PostgreSQL do IESB (conexão direta desde 2026-09-05)
- [x] Usuário somente-leitura: a conta só tem `SELECT`; trava na sessão (ADR-0002)
- [x] Anos no banco: só 2024 no Censo (confirmado pelo autor)
- [x] Construir a camada semântica sobre o schema real (Fase 12, 2026-10-07 —
      [ADR-0019](../decisions/ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md))
- [x] Autor decidiu aliases de intenção, gratuito, comunitária, confessional, capital e as
      ambiguidades `faculdade` e `uf_ou_municipio` (2026-10-07)
- [ ] Autor decidir os 21 sinônimos ainda `proposto`
- [ ] Fase 13: validar que o texto da resposta respeita a terminologia obrigatória dos aliases;
      representar união ("ou"), filtro negativo e limiares, hoje só detectados
- [x] QueryPlan (Pydantic) validado contra a camada semântica e o contexto (Fase 13)
- [x] Testar o pipeline com um modelo real e medir aderência ao schema do QueryPlan (Fase 14)
- [ ] Autor decidir: base de `financiamento`/`reserva_vagas`; dimensão de oferta padrão (hoje
      pergunta-se); se "top N" deve sair marcado como truncado
- [ ] Composições, decomposições, razão por habitante e nome de município no Analista IA
- [ ] Segunda rodada do reviewer sobre as correções de I-1 a I-5 (não houve)
- [ ] Frontend: tela do Analista e intérprete da spec de visualização
- [ ] Sem autenticação nem rate limit (só um semáforo de 1 chamada ao LLM): uso local/demonstração
- [ ] Cobertura métrica × dimensão do gerador conferida por amostra, não exaustiva
- [ ] "técnicos" não é mapeado em "docentes e técnicos" (M-10 da revisão)
