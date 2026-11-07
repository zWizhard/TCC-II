# ADR-0022 — Credenciais AWS por perfil SSO fora do repositório

- **Data:** 2026-10-19
- **Status:** Aceita

## Contexto

A [ADR-0021](ADR-0021-provedor-llm-via-aws-bedrock.md) adotou o AWS Bedrock como provedor do
Analista IA e registrou como consequência que a API passaria a exigir tratamento de credenciais.
O orientador entregou um endereço de acesso e scripts de referência; o mecanismo de autenticação
precisava ser identificado, não presumido.

O endereço foi verificado por requisição GET pública, não autenticada: trata-se de um "AWS access
portal" do IAM Identity Center, com instância em `us-east-1` (título da página e endpoints
`portal.sso` e `oidc` dessa região na política de conteúdo). Os scripts do orientador usam o fluxo
*device code* do SSO-OIDC seguido de `GetRoleCredentials`, o mesmo protocolo do `aws sso login`.

## Decisão

1. **Credenciais só por perfil SSO nomeado da AWS CLI** (`tcc-bedrock`): temporárias (~8 h),
   guardadas pela própria CLI fora do repositório. Nunca chave fixa no `.env`; nunca credencial
   temporária copiada para o repositório. A API continuará sem segredo: lerá apenas o nome do perfil,
   e a cadeia padrão de credenciais do boto3 as resolve.
2. **Login por `aws sso login --profile tcc-bedrock --use-device-code`**, por ser o fluxo equivalente
   ao dos scripts do orientador. O fluxo padrão da CLI (PKCE com retorno a localhost) não foi testado
   com o portal do IESB.
3. **Descoberta de modelos somente leitura, com trava técnica**: um handler `before-call` registrado
   como primeiro no SDK barra, antes de qualquer requisição sair, toda operação fora da allowlist
   (STS, catálogo e disponibilidade do Bedrock, Price List). Todo o `bedrock-runtime` (`InvokeModel`,
   `Converse`), onde a inferência é cobrada, fica bloqueado. Nenhuma inferência paga sem autorização
   do autor; a permissão de invocar um modelo só se prova invocando e fica para esse momento.
4. **EC2 reservada** para possível hospedagem ou demonstração: não iniciada, configurada nem
   modificada. Desenvolvimento, testes e validação inicial do provedor são locais.
5. **Scripts do orientador** preservados como referência, ignorados no git e não copiados para a
   implementação.

## Alternativas consideradas

- **Chaves de acesso no `.env`.** Rejeitada: introduz segredo de longa duração no projeto.
- **Reaproveitar o cache JSON próprio dos scripts do orientador.** Rejeitada: formato *ad hoc*, fora
  da cadeia padrão de credenciais do SDK.

## Consequências

- A consequência "segredos na API" da ADR-0021 fica restrita ao nome do perfil; nenhum segredo
  entra no repositório nem no `.env`.
- O autor precisa refazer o login no navegador a cada ~8 h; sem login, nada no Bedrock pode ser
  verificado.
- A descoberta não gera custo de inferência por construção, não por disciplina; os testes provam a
  trava sem acessar a AWS, incluindo controle negativo.

> A confirmar no primeiro login: se a identidade do autor tem o papel atribuído na conta e se o portal
> federa para um provedor de identidade externo.
