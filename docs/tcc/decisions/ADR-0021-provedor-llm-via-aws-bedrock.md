# ADR-0021 — Provedor do Analista IA via AWS Bedrock

- **Data:** 2026-10-09
- **Status:** Aceita (implementação pendente)

## Contexto

Até a Fase 13, o projeto assumia orçamento zero e LLM exclusivamente local, servido pelo Ollama.
O pipeline do Analista IA
([ADR-0020](ADR-0020-queryplan-fechado-validado-contra-o-contexto.md)) já isola o modelo atrás de
uma única interface, `ProvedorLLM`, com as implementações registradas em `_FABRICAS` de
`api/analista/llm.py`.

Durante a Fase 14, o autor comunicou que o orientador disponibilizou acesso à AWS Bedrock. A
decisão foi comunicada pelo autor no decorrer da fase; não foi derivada do benchmark, que ainda
está em andamento
([devlog de 2026-10-09](../devlog/2026-10-09_fase-14-benchmark-de-modelos-llm.md)).

## Decisão

O Analista IA usará um modelo via **AWS Bedrock** como provedor de produção, em vez de LLM
exclusivamente local.

- A premissa "orçamento zero / LLM local via Ollama" é substituída. O custo permanece zero para o
  autor: o uso é custeado pela instituição.
- O pipeline não muda. O Bedrock entra como nova fábrica em `_FABRICAS`, atrás de `ProvedorLLM`.
- O Ollama permanece como provedor alternativo e como linha de base do benchmark.

O provedor Bedrock **ainda não está implementado**.

**Atualização em 2026-10-19 (material de acesso entregue pelo orientador):** região `us-east-1`;
credenciamento por **IAM Identity Center (SSO)** — login no navegador (fluxo de dispositivo) e
credenciais temporárias de um papel com acesso ao Bedrock, válidas por cerca de 8 h; sem chave de
acesso fixa. O exemplo do orientador usa `boto3` e o modelo `us.meta.llama4-scout-17b-instruct-v1:0`
(perfil de inferência entre regiões), o que é exemplo, não escolha. Junto veio o acesso SSH a uma
instância EC2 própria, entregue desligada. Conta, instância, IP e arquivos de acesso ficam fora do
repositório versionado.

> A confirmar: modelo, limites de custo/uso da conta, mecanismo de saída estruturada para o modelo
> escolhido e papel da instância EC2 no projeto (hospedar a aplicação?).

**Atualização em 2026-11-06 (decisão do autor):** o Ollama **não** permanece como provedor
alternativo nem como linha de base executável: foi removido do projeto (código, configuração,
testes, executor do benchmark e ferramental). Sem fábrica Bedrock, toda pergunta que chegaria ao
modelo recebe 503 explicado; as resolvidas pela camada semântica seguem respondidas. Os resultados
da Fase 14, medidos com Ollama, ficam como registro histórico do que foi executado.

## Alternativas consideradas

- **Manter apenas modelo local (Ollama).** Preserva o funcionamento sem rede e mantém a pergunta
  dentro da máquina. Os resultados parciais do benchmark da Fase 14 mostram taxa de sucesso baixa
  dos modelos locais na configuração atual; esses resultados são parciais e parte das falhas é
  atribuída ao pipeline (teto de tokens, convenções omitidas no prompt), não só aos modelos.

## Consequências

- **Saída de dados da máquina.** A pergunta do usuário e o contexto semântico passam a ser enviados
  a um serviço externo. O que não muda: nenhuma linha da base, SQL, nome físico de tabela ou coluna,
  nem credencial vai ao modelo.
- **Segredos na API.** Hoje a API não lê `.env` nem guarda segredo; isso deixa de valer e exige
  tratamento de credenciais. *Restringido pela
  [ADR-0022](ADR-0022-credenciais-aws-por-perfil-sso-fora-do-repositorio.md) (2026-10-19): a API
  continua sem segredo e lê só o nome do perfil SSO; as credenciais temporárias ficam com a AWS CLI.*
- **Dependência de rede.** Perde-se o funcionamento offline com o provedor de produção; daí a
  manutenção do Ollama como alternativa.
- **Benchmark.** O executor só instrumenta o Ollama; medir modelos do Bedrock exige estendê-lo e
  repetir as rodadas.
- **Documentação.** A descrição do provedor está em
  [`AI_ANALYST.md`](../architecture/AI_ANALYST.md), seção "Provedor: de Ollama para AWS Bedrock".
