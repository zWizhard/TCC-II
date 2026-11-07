# Fase 14 — Benchmark experimental dos modelos LLM do Analista IA (registro parcial)

> **Estado em 2026-10-09: fase em andamento.** Este registro traz o que já foi medido e o que
> falta. Os números abaixo são parciais, da condição P, e contados por execução (caso × repetição).

## Objetivo

Construir um benchmark pequeno, reproduzível e justo para comparar modelos locais (Ollama) na
tarefa do Analista IA, e registrar a decisão do autor de adotar a AWS Bedrock como provedor de
produção ([ADR-0021](../decisions/ADR-0021-provedor-llm-via-aws-bedrock.md)).

## Trabalho realizado

- Pacote `benchmark/`, sem alteração em `api/`: `casos.py` (conjunto de teste), `avaliacao.py`
  (critérios de correção), `provedor.py` (provedor instrumentado que reutiliza o `ProvedorOllama`
  de produção via transporte httpx), `executar.py` (executor, validação do conjunto e manifesto) e
  `relatorio.py` (agregação, IC de Wilson, McNemar exato, Holm, Q de Cochran).
- `tests/test_benchmark.py`, com 30 testes novos.
- Protocolo pré-registrado em [`PROTOCOLO.md`](../benchmark/PROTOCOLO.md), com registro das
  alterações pós-revisão; resultados brutos em `docs/tcc/benchmark/resultados/`, uma pasta por
  condição × modelo (`manifesto.json`, `execucoes.jsonl`, `sistema.json`). Pastas `_piloto_*` ficam
  fora da análise.
- Ambiente: Ollama 0.40.1 instalado via winget em 2026-10-09; modelos baixados (~37 GB):
  qwen3:8b, qwen3:14b, qwen2.5-coder:14b (Q4_K_M) e gpt-oss:20b (MXFP4). Ver
  [`ENVIRONMENT.md`](../../ENVIRONMENT.md).

## Decisões técnicas/metodológicas

O desenho completo está no protocolo; registram-se aqui apenas os pontos que condicionam a leitura
dos resultados.

1. **O que se mede.** A tarefa é "pergunta → QueryPlan", não SQL livre: no Analista IA o modelo não
   escreve SQL ([ADR-0020](../decisions/ADR-0020-queryplan-fechado-validado-contra-o-contexto.md)).
   Os números não se comparam com Spider ou BIRD.
2. **Dois blocos, nunca somados.** Bloco M: 28 casos que chegam ao LLM (agregação 3, filtro simples
   4, GROUP BY 4, HAVING 4, ranking 4, comparação 3, múltiplos filtros 4, razão 2). Bloco S: 12
   casos de JOIN, variação temporal, ambiguidade e fora de escopo, resolvidos pela camada semântica
   antes do LLM, de forma determinística e igual para qualquer modelo.
3. **Referência por caso.** QueryPlan e SQL de referência escritos à mão, o SQL direto nas tabelas e
   sem o gerador do sistema. O executor verifica apenas se os 28 planos de referência reproduzem os
   28 SQLs de referência. Rankings com empate são rejeitados; um caso foi trocado porque PE e RS
   empatam em 118 IES no top 10 de UFs.
4. **Métricas em funil**, nenhuma por texto de SQL: JSON válido; plano válido/SQL executável; plano
   correto (igualdade canônica); SQL semanticamente correto (equivalência por execução); resultado
   correto (= sucesso); latência.
5. **Análise.** Unidade = o caso (n = 28); sucesso = correto nas 3 repetições; IC 95% de Wilson;
   McNemar exato com correção de Holm e Q de Cochran; poder estatístico baixo, declarado.
6. **Três condições**, cada uma com um único conjunto de parâmetros, igual para todos os modelos.
   Temperatura 0, semente 20241007 e prompt único, não ajustado por modelo.

   | Condição | Parâmetros | Repetições | Papel |
   |---|---|---|---|
   | P | `num_predict` 1024, janela padrão 4096, prazo 120 s | 3 | Configuração de produção |
   | N | `think: false`, demais iguais a P | 3 | Sem raciocínio |
   | A | `num_predict` 4096, `num_ctx` 8192, prazo 600 s | 1 | Diagnóstico, só para modelos com parada por `length` ou prazo esgotado em P; fora da comparação entre modelos |

7. **Revisão metodológica independente** pelo subagent `reviewer`, antes de qualquer rodada
   oficial. Acatado: redesenho da condição A, inclusão da condição N, piloto nos quatro modelos,
   subgrupo pré-declarado "convenção implícita" (F4, G4, M1, M2), abstenção do Bloco S deixou de
   ser resultado, Holm e Cochran, hash do código e da base no manifesto (o repositório tem
   alterações não commitadas) e robustez do executor. Não acatado: corrigir o prompt de sistema
   antes de medir, porque mudaria o sistema avaliado com base nos pilotos.

## Resultados parciais (condição P)

| Modelo | Na GPU | Latência mediana | Execuções | Resultado correto | Casos corretos nas 3 repetições |
|---|---|---|---|---|---|
| qwen3:8b | 100% | 12,1 s | 84 de 84 | 12 | 3 de 28 (A1, A3, F1) |
| qwen2.5-coder:14b | 64% | 15,6 s | 84 de 84 | 6 | 2 de 28 (R1, R4) |
| gpt-oss:20b | 44% | 37,8 s | 84 de 84 | 26 | 7 de 28 (A1, A2, A3, F1, F3, G3, Z1) |
| qwen3:14b | 63% | — | não rodada | — | — |

- **qwen3:8b:** 64 planos rejeitados na validação e 8 respostas que não são um plano (8 paradas por
  `length`). Erro típico: filtros e dimensões inventados.
- **qwen2.5-coder:14b** (não raciocina): JSON válido nas 84 execuções; 78 planos rejeitados. Erro
  dominante: preencher `limit` quando a pergunta não pede N (`limite_diverge_do_contexto` em 63
  execuções; em 36 é o único motivo).
- **gpt-oss:20b:** 50 paradas por `length` nas 84 execuções — o raciocínio consome o teto de
  1.024 tokens antes de sair o JSON. Quando emite um plano, ele costuma estar certo: 26 corretos
  em 34.
- **qwen3:14b:** no piloto, cerca de 9 tokens/s e cerca de 50 s por pergunta.

As diferenças entre os três modelos não são estatisticamente significativas (Q de Cochran = 4,67,
gl = 2, p = 0,097). Nas 252 execuções, as 44 respostas entregues estavam todas corretas: nenhum
plano errado passou pela validação. Leitura completa em
[`../benchmark/RESULTADOS.md`](../benchmark/RESULTADOS.md).

Bloco S: as 12 perguntas são barradas sem chamar o LLM; a situação devolvida é a ideal em 10. As
duas divergências são de rótulo: "Como evoluíram as matrículas presenciais?" sai `nao_mapeada` em
vez de `recusada`, e duas medidas de tabelas diferentes saem `requer_esclarecimento` em vez de
`nao_suportada`.

> A confirmar: condição P do qwen3:14b e condições N e A de todos os modelos.

### Achados sobre o pipeline (não sobre os modelos)

Nenhum foi corrigido nesta fase.

- `LLM_MAX_TOKENS = 1024` é pequeno para modelos que raciocinam.
- O cliente não envia `think`.
- O prompt de sistema omite duas convenções que o validador exige: filtro por uma única unidade
  territorial exige `intent = distribuicao`; quebra por dimensão de oferta sem dimensão escolhida
  exige declarar as quatro.
- `limit` e `visualization_hint` rejeitam planos de resto corretos.
- A validação estrita cumpriu o papel: nenhum plano errado virou resposta.

## Validação

- `.venv/Scripts/python.exe -m benchmark.executar --validar-conjunto` → "conjunto valido: 28 casos
  de modelo, 12 de sistema".
- `pytest` completo aprovado (a suíte tinha 1021 testes antes dos 30 novos); ruff e mypy limpos em
  `benchmark/`.
- Teste específico confirma que um plano válido porém errado é reprovado no resultado: H1 com `>=`,
  dado que SC tem exatamente 100 IES.

## Problemas/limitações

- Fase incompleta: `RESULTADOS.md`, `TABELAS.md` e os CSVs ainda não existem.
- Conjunto pequeno e de um único autor, que também escreveu a camada semântica.
- Prompt único, escrito sem modelo real.
- Um hardware (RTX 2070 SUPER 8 GB), um servidor e uma quantização por modelo; os modelos de 14B e
  20B rodam parte na CPU.
- O executor só instrumenta o Ollama: o benchmark ainda não mede modelos do Bedrock.
- Nada foi commitado.

## Próximo passo

Concluir as rodadas locais (gpt-oss:20b em P, qwen3:14b em P, condições N e A), gerar
`TABELAS.md` e os CSVs e escrever `RESULTADOS.md`; obter do autor modelo, região e credenciais do
Bedrock; implementar o provedor Bedrock e repetir o benchmark com ele; corrigir os achados do
pipeline.
