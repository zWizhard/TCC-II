# Fase 12 — Camada semântica do Analista IA

## Objetivo

Construir a ponte validável entre a linguagem do usuário e a base do Censo da Educação Superior
2024, usando apenas schema e conceitos já verificados. Ficaram fora do escopo: QueryPlan, geração
de SQL, LLM e endpoint.

## Trabalho realizado

- `scripts/analise/auditar_schema_semantico.py` gerou duas evidências em
  `docs/data/raw/diagnostics/`: `2026-10-07_schema_duckdb.csv` (inventário das 318 colunas das
  quatro tabelas — `ies` 82, `cursos` 223, `municipio` 7, `ibge_populacao_estimada` 6) e
  `2026-10-07_semantica_verificacoes.csv` (162 medições de tipos, domínios, ambiguidades e relações).
- Pacote `api/semantica/`: 23 dimensões (108 valores), 22 métricas (IND-D-01 a D-11; razões
  IND-R-01, R-08 a R-11; composições IND-R-03 a R-07 e R-12), 4 entidades, 4 relacionamentos,
  16 regras de domínio, 15 termos vedados e 12 ambiguidades. A importação falha se houver
  referência pendente. Ponto de entrada: `recuperar_contexto(pergunta)`, que devolve um
  `ContextoSemantico` com `para_prompt()` e `para_dict()`.
- `tests/test_semantica.py` com 250 testes. Nenhuma rota, schema da API ou frontend foi alterado.

## Decisões técnicas/metodológicas

A decisão estruturante está em
[ADR-0019](../decisions/ADR-0019-camada-semantica-declarativa-e-recuperacao-lexica.md): camada
declarativa em Python derivada de `api/indicadores.py`, recuperação determinística por léxico e
prompt sem schema físico. Complementos:

- **Sinônimos com status**: 243 `verificado` e 67 `proposto` (coloquiais, pendentes de confirmação
  do autor); os propostos funcionam, mas saem marcados.
- **Ambiguidade como objeto de primeira classe**, com magnitude medida. Sem padrão (exigem
  pergunta): universidade, faculdade, pública, EAD, capital, gratuito, UF-ou-município. Com padrão
  sempre declarado: curso, recorte (sede, ADR-0004), aluno, candidato, docente.
- **Recusa explicada** para termos em quarentena (IND-Q-01 a Q-10), três denominações vedadas e
  dois conceitos não servidos (turno, campus). Razão entre duas medidas só passa se o par constar do
  catálogo na ordem numerador/denominador; ano diferente de 2024 é recusa temporal; negação leva a
  esclarecimento, pois a camada não representa filtro negativo.
- **Cobertura total**: cada coluna tem um único estado — 131 expostas (chave 8, dimensão 31,
  métrica 15, componente de decomposição 72, estrutural 5) e 187 fora (sem indicador 65, quarentena
  77, não auditada 30, redundante 15).

Magnitudes medidas (DuckDB, 2026-10-07): "universidade" 2.561 IES × 206; "pública" 317 IES /
2.065.067 matrículas × 289 / 2.019.667 sem as 28 "Especial"; "município" 698 (sede) × 3.551
(oferta); "gratuito" 1.993.055 matrículas × 2.065.067 da rede pública. As demais estão no CSV de
verificações.

## Validação

Reportado pelo implementador: 250 testes aprovados (198 sem a base; 52 com marcador `dados`), suíte
inteira com 506, `ruff` e `mypy api/semantica` limpos. A revisão independente (cerca de 200
perguntas adversariais) confirmou a camada declarativa e encontrou 4 falhas críticas na recuperação
— negação descartada, ano fora de marcador, razão em quarentena por paráfrase e "pará" minúsculo —
e 7 importantes, todas corrigidas com bateria de 81 perguntas parametrizadas.

Após as correções, a suíte inteira foi reexecutada pelo agente principal: 506 testes passando e
`ruff check api tests scripts` limpo. O reviewer não foi chamado uma segunda vez sobre as correções.

## Problemas/limitações

- Divergências de tipo entre a documentação e o DuckDB, **ainda não corrigidas** em
  `DATA_DICTIONARY.md` e `JOIN_STRATEGY.md`: `ies.tp_rede` é INTEGER; `in_comunitaria` e
  `in_confessional` são SMALLINT 0/1; `co_cine_area_geral` e `co_mantenedora` são SMALLINT; nenhuma
  coluna é NOT NULL (a ausência de NULL é fato medido); `municipio.municipio_capital` tem um
  terceiro valor `'0'`; 9 linhas da dimensão de polo não têm município. O DuckDB converte VARCHAR
  em número implicitamente: `nu_ano_censo = 2024` executa em silêncio.
- Trinta colunas de famílias nunca auditadas permanecem não expostas; "deficiência" em `cursos`
  não constava nas pendências de `INDICADORES.md`.
- `tp_nivel_academico` não é exposto: 4 linhas sequenciais (393 matrículas) integram toda métrica
  de cursos.
- IND-R-02 e IND-R-13 não foram mapeadas; IND-D-10 e D-11 vieram apenas das fichas.
- Falsos positivos seguros: "2000 matrículas" recusado como ano; "universidade federal" não
  mapeado; pergunta em maiúsculas perde siglas de UF. Limiares são detectados, não interpretados.
  Não há resolução de município ou curso por nome.

## Fechamento da fase (decisões do autor e gate final, 2026-10-07)

Os números das seções anteriores são os do primeiro ciclo; os finais estão aqui.

- **Sinônimos em três classes.** Dos 67 propostos: 36 confirmados como equivalência segura, 10
  viraram **alias de intenção** (aluno, estudante, matriculado, universitário → matrículas;
  professor → docentes; candidato → inscrições; calouro → ingressantes; formado → concluintes;
  cota, cotista → reserva de vagas, só o agregado de IND-R-09) e 21 continuam propostos. O alias
  aponta para a métrica canônica e leva ao prompt a terminologia obrigatória. "Online" apenas
  dispara a ambiguidade de EAD.
- **Dimensões que respondem direto:** gratuito (atributo de curso, nunca rede pública),
  comunitária e confessional (classificação da IES na fonte — Lei nº 12.881/2013 e art. 19 da LDB,
  redação da Lei nº 13.868/2019 —, sem inferência) e capital (territorial, segue o recorte).
- **Ambiguidades: 8.** Sem padrão: universidade, faculdade, pública, EAD e UF-ou-município (só a
  palavra colada ao nome desambigua; "por município" é nível de agregação e mantém a pergunta).
  Resolvidas e declaradas: curso, recorte e capital. As de aluno, candidato, docente e gratuito
  foram removidas.
- **Segunda passada do reviewer** (cerca de 400 perguntas novas): os quatro críticos fechados e os
  dois invariantes confirmados — nenhuma pergunta "pronta" com ambiguidade obrigatória pendente;
  alias coloquial nunca muda a unidade medida. Oito achados novos (N1 a N8), todos corrigidos:
  homônimo de UF com "por município", alias em posição de adjetivo, "ou" entre filtros, "por
  capital" como quebra, grafias de Pará e de ano, termos técnicos no prompt.
- **Gate executado pelo agente principal:** suíte com 596 testes aprovados (340 em
  `tests/test_semantica.py`), bateria de regressão de 129 perguntas aprovada, `ruff check`,
  `ruff format --check` e `mypy api/semantica` limpos. As correções de N1 a N8 não passaram por
  uma terceira revisão independente.
- **Tipos corrigidos** em `DATA_DICTIONARY.md`, `JOIN_STRATEGY.md` e `INDICADORES.md`:
  `ies.tp_rede` inteiro 1/2; `in_comunitaria` e `in_confessional` inteiros 0/1. As demais
  divergências listadas acima seguem sem correção nos documentos.

## Próximo passo

Decisão do autor sobre os 21 sinônimos ainda propostos; em seguida, Fase 13 — QueryPlan validado
contra a camada, que deve também verificar a terminologia da resposta e representar união, filtro
negativo e limiares.
