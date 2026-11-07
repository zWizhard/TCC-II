# Material de acesso à AWS e proteção de segredos

## Objetivo

Preparar o ambiente para o provedor AWS Bedrock ([ADR-0021](../decisions/ADR-0021-provedor-llm-via-aws-bedrock.md)) a partir do material entregue pelo orientador, sem expor segredos no repositório.

## Trabalho realizado

O autor colocou na raiz do repositório duas pastas: `Nova pasta/` (chave SSH `.pem`, `credentials.txt` e `ec2.txt`, com dados de uma instância EC2 do aluno) e `bedrock-users-main/` (README e scripts Python do orientador para obter credenciais do Bedrock, além de `logins.csv`).

Constatou-se que `credentials.txt` e `ec2.txt` não estavam cobertos pelo `.gitignore`; um `git add` comum os teria versionado. Foram acrescentadas as exclusões `credentials.txt`, `Nova pasta/`, `ec2.txt` e `bedrock-users-main/logins.csv`. A permissão da `.pem` foi restrita ao usuário do Windows (`icacls /inheritance:r /grant:r <usuário>:(R)`), equivalente ao `chmod 600` exigido pelo OpenSSH.

O registro das pendências e do acesso está em [ENVIRONMENT.md](../../ENVIRONMENT.md) (seção "Acesso AWS"), na atualização de 2026-10-19 da ADR-0021 e em [AI_ANALYST.md](../architecture/AI_ANALYST.md).

## Decisões técnicas/metodológicas

- Credencial, chave, conta, instância e IP ficam fora de qualquer arquivo versionado.
- O agente não leu `credentials.txt` nem `logins.csv`; leu apenas o README, os scripts do orientador e `ec2.txt` (sem segredo).
- Pendências da ADR-0021 resolvidas: região `us-east-1`; autenticação por IAM Identity Center (SSO), com login no navegador e credenciais temporárias de cerca de 8 h, sem chave de acesso fixa. O exemplo do orientador usa `boto3` e Llama 4 Scout 17B Instruct — exemplo, não escolha de modelo.

## Validação

`git check-ignore -v` confirma os quatro arquivos sensíveis ignorados; `icacls` mostra apenas o usuário com leitura na `.pem`.

## Problemas/limitações

- AWS CLI ausente e `boto3` ausente do `.venv`.
- A EC2 foi entregue desligada; ligá-la exige CLI ou console.
- Os arquivos sensíveis continuam dentro da pasta do repositório; recomenda-se movê-los para fora.
- Os scripts do orientador (sem segredo) seguem como não rastreados.

## Próximo passo

Autor escolher o modelo do Bedrock e definir o papel da EC2; instalar `boto3`; primeiro login SSO pelo autor; implementar o provedor Bedrock e repetir o benchmark.
