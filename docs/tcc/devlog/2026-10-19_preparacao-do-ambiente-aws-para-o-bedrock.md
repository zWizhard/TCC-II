# Preparação do ambiente local para o provedor Bedrock

## Objetivo

Deixar o ambiente local pronto para a autenticação do autor no AWS Bedrock e para a descoberta de
modelos, sem custo de inferência e sem alterar a infraestrutura AWS. Continua o
[devlog anterior de 2026-10-19](2026-10-19_material-de-acesso-aws-e-protecao-de-segredos.md).

## Trabalho realizado

- O autor removeu do projeto a pasta com chave SSH, credenciais e dados da EC2; verificou-se que não
  restou nenhum `.pem`, `credentials.txt` ou `ec2.txt`.
- `.gitignore`: `bedrock-users-main/` (scripts de referência do orientador) passa a ser ignorada
  inteira; as exclusões defensivas anteriores foram mantidas.
- `boto3`/`botocore` 1.43.115 adicionados com `uv add`; override do mypy para ambos (sem tipos publicados).
- AWS CLI 2.38.1 instalada pelo pacote oficial da Amazon no winget (MSI com assinatura conferida).
- Perfil nomeado `tcc-bedrock` criado na configuração da CLI do usuário, fora do repositório, com
  bloco `sso-session`, sem credencial, sem perfil `default` e sem variável global.
- `scripts/aws/descobrir_modelos_bedrock.py`: descoberta somente leitura (identidade, catálogo de
  modelos, perfis de inferência, disponibilidade e, com `--precos`, Price List). Grava o catálogo em
  `docs/data/raw/diagnostics/<data>_bedrock_modelos.csv`, sem identidade. Destaca o Llama 4 Scout
  sem torná-lo obrigatório.
- `tests/test_descobrir_bedrock.py`: 13 testes com credenciais falsas e Stubber do botocore.

A documentação de ambiente e do Analista foi atualizada em [`ENVIRONMENT.md`](../../ENVIRONMENT.md)
e [`AI_ANALYST.md`](../architecture/AI_ANALYST.md).

## Decisões técnicas/metodológicas

Registradas na [ADR-0022](../decisions/ADR-0022-credenciais-aws-por-perfil-sso-fora-do-repositorio.md):
credenciais apenas por perfil SSO nomeado; login por `aws sso login --use-device-code`, escolhido
após identificar o mecanismo do portal sem presumi-lo; descoberta com trava técnica que barra, no
SDK, toda operação fora de uma allowlist, inclusive todo o `bedrock-runtime`; EC2 não iniciada nem
modificada; scripts do orientador apenas como referência.

## Validação

Suíte completa com 1064 testes aprovados (13 novos); ruff e mypy limpos; `uv lock --check` sem
divergência. Os testes incluem um controle negativo: sem a trava, a requisição seria montada.
Varredura dos arquivos versionáveis por identificadores de conta, portal, instância, IP, e-mail,
chaves AKIA/ASIA e chave privada: nada encontrado. `git check-ignore` confirma a pasta ignorada.

## Problemas/limitações

- O login SSO exige o autor no navegador a cada ~8 h; sem ele nada no Bedrock é verificável.
- O preço por modelo depende da Price List (o papel pode não ter permissão), e o casamento
  preço × modelo é manual.
- O suporte a saída estruturada por modelo não é exposto pela API de catálogo.
  > A confirmar: suporte a saída estruturada, pela documentação da AWS.
- Durante a depuração, uma chamada com credenciais falsas chegou ao endpoint público do
  `bedrock-runtime` e foi recusada na autenticação, sem custo; os testes finais não fazem isso.

## Próximo passo

O autor executa o login SSO; o agente roda a descoberta com `--precos` e analisa os candidatos
(permissão, compatibilidade com Converse, custo, saída estruturada, adequação ao QueryPlan); o autor
escolhe o modelo e autoriza inferências de teste; implementa-se a fábrica Bedrock em
`api/analista/llm.py` e estende-se o benchmark.
