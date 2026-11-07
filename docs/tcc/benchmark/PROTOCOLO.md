# Protocolo do benchmark de modelos locais para o Analista IA (Fase 14)

Escrito e revisado **antes** da rodada oficial (2026-10-09). O que mudou depois da revisão está em
[Registro de alterações](#registro-de-alterações). Resultados em `resultados/` e em
[`RESULTADOS.md`](RESULTADOS.md).

## 1. Pergunta de pesquisa

Entre modelos de linguagem que rodam localmente em hardware de consumo (8 GB de VRAM), qual
interpreta melhor perguntas em português sobre o Censo da Educação Superior 2024, **dentro do
pipeline do Analista IA**, e a que custo de latência?

## 2. O que este benchmark mede — e o que não mede

No Analista IA o modelo **não escreve SQL**. Ele recebe o contexto semântico da pergunta (só
identificadores de negócio, sem tabela nem coluna) e devolve um **QueryPlan** em JSON; o backend
valida o plano e gera o SQL ([ADR-0020](../decisions/ADR-0020-queryplan-fechado-validado-contra-o-contexto.md)).
Logo:

- a tarefa avaliada é **pergunta → QueryPlan**, e a correção do SQL é consequência do plano;
- os números **não se comparam** com benchmarks de Text-to-SQL em que o modelo emite SQL livre
  (Spider, BIRD): a tarefa aqui é mais restrita, por projeto;
- recusa, ambiguidade, JOIN e variação temporal são decididos pela camada semântica **antes** do
  modelo, de forma determinística. Essas perguntas não discriminam modelos e ficam em bloco próprio.

## 3. Unidade experimental e conjunto de teste

Conjunto em [`benchmark/casos.py`](../../../benchmark/casos.py), construído só com métricas,
dimensões e valores que existem na camada semântica e na base local (DuckDB, Censo 2024).

**Bloco M — modelo (28 casos).** Perguntas que chegam ao LLM. Cada caso tem:

1. o **QueryPlan de referência**, escrito à mão;
2. um **SQL de referência**, escrito à mão direto sobre as tabelas, **sem** usar o gerador de SQL
   do sistema;
3. o **resultado esperado** = o resultado do SQL de referência na base local.

| Categoria | Casos | O que exige do modelo |
|---|---|---|
| Agregação | A1–A3 | métrica e entidade certas, nenhum filtro |
| Filtro simples | F1–F4 | um filtro; F4 por código de município (muda o nível territorial) |
| GROUP BY | G1–G4 | quebra por nível territorial ou por dimensão; G4 sem dimensão de oferta escolhida |
| HAVING | H1–H4 | limiar com operador no sentido da pergunta (`>`, `>=`, `<`) |
| Ranking | R1–R4 | ordem, direção e N |
| Comparação | C1–C3 | duas medidas ou duas unidades lado a lado |
| Múltiplos filtros | M1–M4 | dois ou três filtros, com nível territorial implícito |
| Razão | Z1–Z2 | métrica derivada do catálogo (por vaga) |

**Bloco S — sistema (12 casos).** JOIN (J1–J3), variação temporal (T1–T3), ambiguidade (B1–B5) e
fora de escopo (X1). O LLM não é chamado; o desfecho é igual para qualquer modelo. É rodado uma
vez e reportado à parte. A `situacao` ideal de cada caso é a que a especificação pede, não a que o
código devolve.

**Validação do conjunto (obrigatória, automática).** Antes de qualquer medição o executor confere,
para cada caso do Bloco M, que o plano de referência passa na validação e que o SQL gerado a partir
dele devolve exatamente o resultado do SQL de referência. Dois artefatos escritos de forma
independente têm de concordar; se um caso falha, nada é medido. Rankings com empate (na ordem ou no
corte) são rejeitados: a resposta esperada dependeria do desempate, não da pergunta.

O tamanho (28) é deliberadamente pequeno: cada caso tem referência verificada. A consequência
estatística está na seção 8.

## 4. Fatores controlados

| Fator | Valor | Observação |
|---|---|---|
| Pipeline | `api.analista.pipeline.responder`, sem alteração | o mesmo código da API |
| Prompt de sistema | único, `PROMPT_DE_SISTEMA` | sha256 no manifesto; **não é ajustado por modelo** |
| Contexto da pergunta | `ContextoSemantico.para_prompt()` | determinístico |
| Saída estruturada | `format` = JSON Schema do QueryPlan | igual para todos |
| Temperatura | 0 | |
| Semente | 20241007 | única opção acrescentada à requisição de produção |
| Quantização | a padrão da tag do Ollama (`Q4_K_M`; `MXFP4` no `gpt-oss`) | registrada por modelo, com o digest |
| Hardware | Ryzen 7 5700X, 32 GB RAM, RTX 2070 SUPER 8 GB | registrado no manifesto |
| Ordem dos casos | embaralhada por repetição, igual para todos os modelos | |
| Aquecimento | carga do modelo + 1 pergunta fora do conjunto, descartada | tempo de carga reportado à parte |
| Concorrência | um modelo por vez; descarregado ao fim | |
| Raciocínio (`think`) | não enviado: vale o padrão de cada modelo | ver seção 5 |

Não há nova tentativa: uma resposta inválida conta como falha, como em produção.

## 5. Condições

Os pilotos (pastas `_piloto_*`, fora da análise: 6 casos no `qwen3:8b`, 3 no `qwen3:14b`, 2 no
`qwen2.5-coder:14b` e 2 no `gpt-oss:20b`) mostraram que `qwen3` e `gpt-oss` raciocinam antes de
emitir o JSON (campo `thinking`) e podem esgotar o teto de 1.024 tokens de produção sem produzir
resposta. Esse teto foi fixado na Fase 13 sem nenhum modelo real. Para não confundir "o modelo
interpreta mal" com "a configuração corta o modelo", há três condições. Cada uma é **um conjunto
único de parâmetros, enviado igual a todos os modelos**:

| Condição | `think` | `num_predict` | `num_ctx` | Prazo | Repetições | Modelos | Papel |
|---|---|---|---|---|---|---|---|
| **P — produção** | não enviado | 1.024 | padrão (4.096) | 120 s | 3 | os quatro | o sistema como está |
| **N — sem raciocínio** | `false` | 1.024 | padrão (4.096) | 120 s | 3 | os quatro | a configuração candidata a produção |
| **A — orçamento ampliado** | não enviado | 4.096 | 8.192 | 600 s | 1 | ver regra | diagnóstico |

- **N** muda um único parâmetro em relação a P. Conferido no piloto: `think: false` desliga o
  raciocínio do `qwen3`; não tem efeito no `qwen2.5-coder` (que não raciocina); e é **ignorado**
  pelo `gpt-oss`, que só aceita níveis. Não se envia um valor diferente para o `gpt-oss`: seria
  ajuste por modelo. Para esses dois, N funciona como réplica de P.
- **A** responde a outra pergunta: com tokens e tempo de sobra, o raciocínio acerta mais? Roda só
  para os modelos que tiverem, em P, parada por `length` **ou** prazo esgotado. Muda três
  parâmetros de uma vez (o teto maior não cabe na janela padrão, e a janela maior tira o modelo da
  GPU), então **não isola** o efeito do teto e **não entra** na comparação entre modelos. É
  comparada só com a repetição 1 de P (mesma ordem de casos), e o sucesso é reportado também
  restrito às execuções que terminaram em até 120 s.

## 6. Modelos

Candidatos: `qwen3:8b` (baseline rápido), `qwen3:14b`, `qwen2.5-coder:14b`, `gpt-oss:20b`. Nenhum
é excluído de antemão. Para cada um registram-se digest, parâmetros, quantização, tempo de carga,
memória ocupada e **fração do modelo na GPU**. Modelo que não carrega, ou que estoura o prazo, é
reportado como tal — é um resultado sobre a adequação ao hardware, não um dado faltante.

## 7. Métricas

Por execução (caso × modelo × repetição), em funil:

| # | Métrica | Critério |
|---|---|---|
| 1 | **JSON válido** | a resposta é um QueryPlan sintaticamente válido (parse estrito) |
| 2 | **Plano válido / SQL executável** | o plano passa na validação, o SQL é gerado, aprovado no validador AST e executa |
| 3 | **Plano correto** | igualdade **canônica** com o plano de referência (ordem de listas e `visualization_hint` não contam) |
| 4 | **SQL semanticamente correto** | equivalência por **execução**: o SQL gerado, reexecutado, devolve o mesmo conjunto de linhas do SQL de referência |
| 5 | **Resultado correto** | as linhas da resposta final (rótulos, corte, arredondamento) são as esperadas, com o recorte declarado |
| 6 | **Taxa de sucesso** | = métrica 5; é a métrica principal |
| 7 | **Latência** | tempo de parede da pergunta (mediana e P90), tokens gerados e tokens/s medidos pelo servidor |

Nenhuma métrica compara texto de SQL. Linhas são comparadas como multiconjunto; como lista ordenada
nos rankings. Inteiros exatos; razões a 4 casas. As métricas 2 e 4 coincidem com frequência por
construção (o SQL é função determinística do plano); divergem quando um plano válido mas diferente
da referência produz, ou não, o mesmo resultado — por exemplo `>=` no lugar de `>`.

Falhas são classificadas: resposta que não é plano (`resposta_do_modelo_invalida`), plano rejeitado
(`plano_invalido`, com os códigos), modelo sem resposta no prazo (`modelo_indisponivel`).

As métricas 2 a 5 tendem a sair quase iguais (efeito de construção): a validação fixa limite,
operador, filtros e ordem pelo contexto da pergunta, então quase não existe plano válido e errado.

Bloco S: **situação exata** (a `situacao` devolvida é a ideal). A abstenção — não chamar o LLM e
não devolver número — é condição de entrada no bloco, não resultado: vale 100% por construção.

## 8. Análise

- **Unidade de análise: o caso** (n = 28), não a execução. Repetições a temperatura 0 não são
  amostras independentes; servem para medir estabilidade e variação de latência.
- Sucesso de um caso = correto em **todas** as repetições. Reporta-se também a taxa por execução e
  a **estabilidade** (casos com saída idêntica em todas as repetições).
- Intervalo de confiança de 95% de Wilson para cada taxa.
- **Subgrupo pré-declarado — convenção implícita (F4, G4, M1, M2).** O plano de referência desses
  quatro casos depende de uma convenção do validador que o prompt não enuncia (F4, M1, M2: filtro
  por uma única unidade territorial exige `distribuicao`, embora a resposta tenha uma linha; G4:
  sem dimensão de oferta escolhida, exige declarar as quatro). O prompt **não é corrigido** depois
  dos pilotos; a taxa de sucesso é reportada com os 28 casos e também com os 24 restantes.
- **Entre modelos, dentro de uma condição:** teste Q de Cochran (global) e, par a par, McNemar
  exato com correção de Holm para as 6 comparações. Com Holm, só um par com pelo menos 8 casos
  discordantes, todos na mesma direção, chega a p < 0,05; n = 28 só detecta diferenças grandes.
  Não se declara "melhor modelo" sem diferença significativa: reporta-se a ordem observada e a
  incerteza.
- **Entre condições, dentro de um modelo (P × N):** McNemar exato, sem correção, como descrição.
- **Latência:** mediana e P90 sobre todas as execuções (uma execução que estoura o prazo entra com
  o tempo que consumiu), mediana só sobre as execuções corretas e número de execuções sem resposta
  no prazo.

## 9. Reprodução

```
.venv/Scripts/python.exe -m benchmark.executar --validar-conjunto
.venv/Scripts/python.exe -m benchmark.executar --rotulo P_<modelo> --modelos <modelo>
.venv/Scripts/python.exe -m benchmark.executar --rotulo N_<modelo> --modelos <modelo> --think false
.venv/Scripts/python.exe -m benchmark.executar --rotulo A_<modelo> --modelos <modelo> \
    --repeticoes 1 --max-tokens 4096 --num-ctx 8192 --timeout 600
.venv/Scripts/python.exe -m benchmark.relatorio
```

Cada rodada grava `manifesto.json` (ambiente, versões, hashes do prompt, do schema, do conjunto,
das referências, da base DuckDB e do código — o repositório tem alterações não commitadas, então o
código medido é identificado por hash, não pelo commit —, configuração e dados de cada modelo), `execucoes.jsonl` (uma linha por execução,
com a resposta bruta do modelo) e `sistema.json`. Uma rodada nunca sobrescreve outra.

## 10. Ameaças à validade (conhecidas de antemão)

- **Conjunto pequeno e de um único autor**, que também escreveu a camada semântica: as perguntas
  usam o vocabulário que a camada reconhece. Mede-se o modelo dentro do sistema, não a robustez a
  linguagem livre.
- **Prompt único, escrito sem modelo real**: pode favorecer por acaso uma família. Não foi ajustado
  depois dos pilotos.
- **Validação estrita**: o plano tem de coincidir com o contexto determinístico, então quase não há
  "plano válido e errado". A taxa de sucesso mede sobretudo a aderência ao esquema e às regras.
- **Um hardware, um servidor (Ollama), uma quantização.** A latência não se generaliza.
- **Raciocínio no padrão de cada modelo** em P: parte da diferença de latência vem daí, não do
  tamanho. N controla isso onde o modelo permite; o `gpt-oss` não permite.
- **Blocos definidos pelo desfecho da camada semântica**: um caso só está no Bloco M porque a
  camada o classifica como pronto. O conjunto não mede a cobertura da camada.
- **Modelos de 14B e 20B não cabem em 8 GB**: rodam parte na CPU. O resultado de latência deles é
  deste hardware.

## Registro de alterações

Revisão metodológica independente (subagent `reviewer`) em 2026-10-09, **antes** de qualquer
rodada oficial. Alterações decorrentes:

1. Condição A redesenhada: prazo de 600 s (a 8,7 tokens/s, 120 s cortam antes de 1.024 tokens),
   gatilho inclui prazo esgotado, passa a ser diagnóstico fora da comparação entre modelos.
2. Condição N (`think: false`) acrescentada.
3. Piloto estendido aos quatro modelos antes de congelar o protocolo.
4. Subgrupo "convenção implícita" pré-declarado, no lugar de corrigir o prompt.
5. Abstenção do Bloco S deixou de ser reportada como resultado.
6. Análise: Q de Cochran, Holm, latência só dos acertos, comparação A × P pela repetição 1.
7. Manifesto: hash do código e da base, versões das bibliotecas, ficha do modelo no servidor,
   variáveis `OLLAMA_*`, VRAM em uso antes da carga; memória medida depois do aquecimento.
8. Executor: falha por caso não derruba a rodada; recarga do modelo depois de prazo esgotado;
   resposta com métrica a mais é reprovada; razões comparadas com tolerância absoluta.

Não acatado: corrigir as duas regras do prompt antes de medir. Mudaria o sistema avaliado com base
no que os pilotos mostraram; fica como achado e trabalho futuro.
