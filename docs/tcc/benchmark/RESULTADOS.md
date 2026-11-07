# Resultados do benchmark de modelos locais para o Analista IA (Fase 14)

**Estado em 2026-10-09: parcial.** Medida a condição P (produção) em três dos quatro modelos.
Faltam `qwen3:14b` em P e as condições N (`think: false`) e A (orçamento ampliado) para todos.
Tudo o que se afirma abaixo vale **só para a condição P**.

Protocolo: [`PROTOCOLO.md`](PROTOCOLO.md). Tabelas completas, geradas dos dados brutos:
[`TABELAS.md`](TABELAS.md) e os CSVs desta pasta. Dados brutos: `resultados/P_*/`.

## 1. O que foi medido

A tarefa é **pergunta em português → QueryPlan**. No Analista IA o modelo não escreve SQL: escolhe
identificadores de um plano fechado, que o backend valida e converte em SQL. Os números não se
comparam com benchmarks em que o modelo emite SQL livre (Spider, BIRD).

- **28 perguntas** que chegam ao modelo, em 8 categorias, cada uma com plano de referência e SQL de
  referência escritos à mão e conferidos um contra o outro.
- **3 repetições** por pergunta e modelo, temperatura 0, semente fixa, prompt único.
- Configuração de produção: teto de 1.024 tokens gerados, janela de 4.096, prazo de 120 s.
- Hardware: Ryzen 7 5700X, 32 GB de RAM, RTX 2070 SUPER (8 GB), Ollama 0.40.1.
- Um caso conta como acerto quando o resultado final está correto **nas 3 repetições**.

## 2. Resultado principal

| Modelo | Sucesso (28 casos) | IC 95% | Sucesso por execução | Mediana de latência | Na GPU |
|---|---|---|---|---|---|
| `gpt-oss:20b` | 7 (25,0%) | 12,7–43,4% | 31,0% | 37,8 s | 44% |
| `qwen3:8b` | 3 (10,7%) | 3,7–27,2% | 14,3% | 12,1 s | 100% |
| `qwen2.5-coder:14b` | 2 (7,1%) | 2,0–22,6% | 7,1% | 15,6 s | 64% |
| `qwen3:14b` | não medido | — | — | — | 63% |

**Na configuração de produção, nenhum modelo local testado é utilizável:** o melhor acerta uma em
cada quatro perguntas. As diferenças entre os modelos **não são estatisticamente significativas**
(Q de Cochran = 4,67, gl = 2, p = 0,097; nenhum par com p < 0,05 no teste de McNemar, com ou sem
correção de Holm). Com 28 casos só se detectam diferenças grandes; a ordem acima é a observada, não
uma classificação.

Sem os quatro casos de convenção implícita (F4, G4, M1, M2), que nenhum modelo acertou, as taxas
passam a 7/24, 3/24 e 2/24. A conclusão não muda.

## 3. Por que cada modelo falha

As falhas têm causas diferentes, e só uma delas é erro de interpretação.

**`gpt-oss:20b` — cortado pelo teto de tokens.** Em 50 das 84 execuções o modelo gastou os 1.024
tokens raciocinando e parou sem emitir o JSON. Quando chegou a emitir um plano (34 execuções), ele
estava correto em 26. É o modelo que melhor interpreta, medido na configuração que mais o prejudica.

**`qwen2.5-coder:14b` — obedece ao formato, desobedece a uma regra.** JSON válido nas 84 execuções
e saída idêntica entre repetições em todos os casos. Mas preenche `limit` quando a pergunta não
pede N: o motivo `limite_diverge_do_contexto` aparece em 63 execuções. Também inclui o nível
territorial em `group_by` (21) e omite o limiar do `HAVING` (15).

**`qwen3:8b` — inventa.** Cria filtros e dimensões que não existem no contexto
(`filtro_diverge_do_contexto` 38, `filtro_invalido` 30, `dimensao_inexistente` 29) e erra `intent`
(21). É também o menos estável: saída idêntica nas três repetições em só 4 dos 28 casos, apesar da
temperatura 0 e da semente fixa.

## 4. Por categoria

| Categoria | n | `gpt-oss:20b` | `qwen2.5-coder:14b` | `qwen3:8b` |
|---|---|---|---|---|
| Agregação | 3 | 3 | 0 | 2 |
| Filtro simples | 4 | 2 | 0 | 1 |
| GROUP BY | 4 | 1 | 0 | 0 |
| HAVING | 4 | 0 | 0 | 0 |
| Ranking | 4 | 0 | 2 | 0 |
| Comparação | 3 | 0 | 0 | 0 |
| Múltiplos filtros | 4 | 0 | 0 | 0 |
| Razão | 2 | 1 | 0 | 0 |

Nenhum modelo acertou um caso sequer de HAVING, comparação ou múltiplos filtros. Com 2 a 4 casos
por categoria, a tabela descreve; não sustenta inferência por categoria.

## 5. O funil não discrimina

Plano válido, plano correto, SQL semanticamente correto e resultado correto deram **o mesmo número
em todos os modelos**. É efeito de construção, previsto no protocolo: a validação confere o plano
contra o contexto determinístico da pergunta, então um plano que passa já é o plano certo. A única
etapa que separa os modelos é a primeira (JSON válido: 28/28, 24/28 e 9/28).

A leitura positiva é a de segurança: **em 252 execuções, nenhum plano errado virou resposta.** As
44 respostas entregues estavam todas corretas.

## 6. Latência

| Modelo | Mediana | P90 | Mediana dos acertos | Tokens gerados (mediana) | Tokens/s |
|---|---|---|---|---|---|
| `qwen3:8b` | 12,1 s | 18,2 s | 11,2 s | 563 | 58,9 |
| `qwen2.5-coder:14b` | 15,6 s | 19,1 s | 17,4 s | 109 | 9,4 |
| `gpt-oss:20b` | 37,8 s | 40,6 s | 23,4 s | 1.024 | 28,8 |

Nenhuma execução estourou o prazo de 120 s. O `qwen2.5-coder` gera pouco (não raciocina) e por isso
responde rápido mesmo a 9 tokens/s. A mediana do `gpt-oss` está presa ao teto de tokens.

## 7. Bloco de sistema

As 12 perguntas de JOIN, variação temporal, ambiguidade e fora de escopo foram resolvidas pela
camada semântica sem chamar o modelo, de forma idêntica nas três rodadas. A situação devolvida foi
a ideal em **10 de 12**. As duas divergências são de rótulo, não de segurança:

- "Como evoluíram as matrículas presenciais?" sai `nao_mapeada` em vez de `recusada`;
- "Quantas matrículas presenciais e quantos docentes há por UF?" sai `requer_esclarecimento` em
  vez de `nao_suportada`.

Esse bloco não compara modelos, e a abstenção em si é condição de entrada nele, não resultado.

## 8. O que isso diz sobre o sistema

Boa parte das falhas vem da configuração e do prompt, escritos na Fase 13 sem modelo real:

1. O teto de 1.024 tokens é pequeno para modelos que raciocinam.
2. O cliente não envia `think`.
3. O prompt omite duas convenções que o validador exige (os quatro casos de convenção implícita).
4. `limit` e `visualization_hint`, que não mudam a consulta pedida, rejeitam planos de resto corretos.

Nada disso foi corrigido nesta fase: ajustar o sistema depois de ver os resultados invalidaria a
comparação. Detalhe em [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md).

## 9. Limitações

- **Benchmark incompleto.** Falta um modelo e faltam as duas condições que separariam "o modelo
  interpreta mal" de "a configuração corta o modelo". A condição P sozinha subestima os modelos
  que raciocinam.
- **Conjunto pequeno (28) e de um único autor**, que também escreveu a camada semântica. As
  perguntas usam o vocabulário que a camada reconhece: mede-se o modelo dentro do sistema, não a
  robustez a linguagem livre.
- **Prompt único**, não ajustado; pode favorecer por acaso uma família de modelos.
- **Um hardware, um servidor, uma quantização por modelo.** A latência não se generaliza; dois dos
  três modelos medidos rodam parte na CPU.
- **Repetições não são amostras independentes.** Mesmo assim houve variação entre repetições em
  dois modelos, o que a semente fixa não eliminou.
- **Não mede o modelo de produção.** Em 2026-10-09 o autor decidiu usar AWS Bedrock
  ([ADR-0021](../decisions/ADR-0021-provedor-llm-via-aws-bedrock.md)). Em 2026-11-06 o autor
  determinou a remoção do Ollama do projeto: estes resultados ficam como **registro histórico** do
  que foi medido, não como linha de base executável.

## 10. Reprodução

```
.venv/Scripts/python.exe -m benchmark.executar --validar-conjunto
.venv/Scripts/python.exe -m benchmark.relatorio
```

**Atualização em 2026-11-06:** a medição de modelos (`--modelos`) saiu do executor junto com o
Ollama; as rodadas `P_*` acima **não podem ser repetidas** com o código atual. O código que as
produziu está identificado pelo `codigo_sha256` de cada manifesto. Hoje o executor valida o
conjunto e roda só o bloco de sistema (`--rotulo <nome>`); o relatório ignora rodadas sem
`execucoes.jsonl`. A medição volta com a fábrica Bedrock, sem mudar casos, critérios nem relatório.
O prompt de sistema, o JSON Schema do plano e o conjunto continuam com os mesmos sha256 dos
manifestos (conferido na revisão da Fase 15).

Cada pasta em `resultados/` tem o manifesto (ambiente, versões, hashes do prompt, do esquema, do
conjunto, da base e do código, digest do modelo) e uma linha por execução com a resposta bruta.
