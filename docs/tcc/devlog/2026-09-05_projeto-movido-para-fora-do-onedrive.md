# Projeto movido para fora do OneDrive e revalidação da infraestrutura

## Objetivo

Encerrar a última pendência bloqueante da Fase 1: retirar o repositório da pasta sincronizada pelo
OneDrive e confirmar, no novo caminho, que versionamento, dados brutos e ferramental de qualidade
permanecem íntegros.

## Trabalho realizado

O autor moveu manualmente o projeto de `C:\Users\Eduardo\OneDrive\Documents\projetos\TCC-II` para
`C:\Users\Eduardo\Documents\TCC-II`. O caminho antigo deixou de existir.

Três arquivos foram ajustados em decorrência da mudança:

- `.claude/settings.json` — a primeira regra da lista `allow` apontava para o caminho absoluto antigo
  (`Read(//c/Users/.../OneDrive/...)`), obsoleto após a movimentação. Foi substituída por `Read(./**)`,
  relativa à raiz do projeto.
- `CLAUDE.md`, bloco "Estado atual" — a linha que declarava o projeto dentro do OneDrive passou a
  registrar o caminho novo e a condição de estar fora da sincronização.
- `docs/ENVIRONMENT.md` — a implicação "mover para fora do OneDrive / ainda não executado" foi
  reescrita como pendência resolvida em 2026-09-05.

Devlogs anteriores não foram alterados: registram o estado vigente à data em que foram escritos.

## Decisões técnicas/metodológicas

Nenhuma decisão nova. A [ADR-0005](../decisions/ADR-0005-versionamento-das-evidencias-de-auditoria.md)
e as decisões do registro anterior permanecem válidas. A única mudança de critério foi preferir
caminho relativo a caminho absoluto na configuração de permissões, para torná-la imune a futuras
mudanças de pasta.

## Validação

Toda a verificação foi executada no caminho novo:

- `git rev-parse --show-toplevel` retorna `C:/Users/Eduardo/Documents/TCC-II`; branch `main`,
  0 commits e 0 remotos; diretório `.git` íntegro após a movimentação.
- Confirmado que o destino não é sincronizado: a raiz do OneDrive é `C:\Users\Eduardo\OneDrive` e
  `C:\Users\Eduardo\Documents` é diretório real, não junção.
- Dados brutos intactos: `docs/data/raw/inep_educacao_superior_cursos.csv` com 560.702.960 bytes,
  o CSV correspondente de IES e os quatro CSVs de evidência em `diagnostics/`.
- `python .claude/hooks/_selftest.py`: 49 casos, todos aprovados; *stop hook* em 0,04 s.
- `ruff check .` sem apontamentos; `settings.json` e `pyproject.toml` validados por parser.
- `git check-ignore` sobre dez caminhos: brutos do Censo, `.env`, `settings.local.json` e
  `.ruff_cache/` corretamente ignorados; evidências, `.env.example`, `CLAUDE.md`, `pyproject.toml`
  e a ADR-0005 corretamente versionáveis.
- Primeiro commit candidato: 50 arquivos.

## Problemas/limitações

Nenhum problema de integridade. Registra-se uma ressalva de navegação: o *Known Folder Move* do
OneDrive continua ativo para a pasta "Documentos" do shell (`User Shell Folders\Personal` aponta para
`OneDrive\Documents`), de modo que "Documentos" no Explorer abre a pasta sincronizada, e não a do
projeto. É questão de navegação, não de risco de sincronização sobre o repositório.

Node/npm e Ollama seguem ausentes, sem impacto na Fase 1.

## Próximo passo

Realizar o primeiro commit e criar o repositório remoto no GitHub.
