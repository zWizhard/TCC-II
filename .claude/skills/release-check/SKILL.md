---
name: release-check
description: Verificação final antes de dar uma feature por concluída — diff, lint, typecheck, testes, build, segredos, documentação e regressões óbvias. Use ao encerrar uma entrega.
---

# release-check

Rápido e proporcional. Não é auditoria completa do projeto.

## 1. Diff

`git diff --stat` primeiro; só então `git diff` nos arquivos relevantes.
Sobrou arquivo temporário, `console.log`, `print()` de depuração, código comentado, TODO esquecido?
Algo fora do escopo pedido entrou junto?

> Se `git` não estiver disponível na máquina, diga isso e faça a conferência pelos arquivos alterados na sessão.

## 2. Segredos (bloqueante)

Nenhuma senha do IESB, token, API key, connection string ou host interno em código, teste, log,
fixture ou doc. `.env` **não** versionado; `.env.example` presente e **sem valores reais**.
`.gitignore` cobrindo `.env`, credenciais, dados brutos e artefatos.

## 3. Qualidade automática

Rode **só o que existe no projeto** — não instale ferramenta para satisfazer o checklist:

- Python: `ruff check`, `ruff format --check`, `mypy` (se configurado)
- TypeScript: `tsc --noEmit`, `eslint`
- Testes: a suíte do escopo alterado; a suíte inteira só se for rápida
- Build: apenas quando a mudança puder quebrá-lo

Se uma ferramenta não estiver instalada, **diga isso explicitamente** — não declare "passou".

## 4. Dados e estatística

Se a mudança toca número: o grain está certo? Houve JOIN não validado? Indicador tem definição,
fórmula, unidade, grain, fonte, pressupostos e limitações? Nenhum texto sugere causalidade a partir de correlação?

## 5. Segurança do Analista IA

Se a mudança toca o pipeline de IA: conexão read-only, allowlist, validação AST, LIMIT, timeout,
parametrização — e nenhum caminho onde saída do LLM vire código executado.

## 6. Documentação

`docs/data/` atualizado se o schema foi descoberto. `docs/tcc/architecture/AI_ANALYST.md`
atualizado se a IA mudou. CLAUDE.md ainda descreve a realidade do projeto?

## 7. Encerramento

Chame `tcc-documentarian` com handoff compacto. **Não commite nem faça push automaticamente.**

## Relatório

O que passou, o que **não pôde ser verificado e por quê**, e o que ficou pendente.
Nunca declarar "tudo verificado" quando algo não rodou.
