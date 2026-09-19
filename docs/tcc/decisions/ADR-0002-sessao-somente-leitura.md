# ADR-0002 — Sessão somente-leitura imposta pela aplicação

- **Data:** 2026-09-05
- **Status:** **Aceita e confirmada empiricamente** em 2026-09-05

> **Confirmação (`scripts/db/03_...`, blocos A e B).** Via `has_*_privilege`, que considera concessão
> direta, `PUBLIC` e herança de papel: `data_iesb` tem `SELECT = true` e
> **`INSERT`/`UPDATE`/`DELETE` = false** nas duas tabelas; `CREATE` no banco e no schema `public`
> também são `false`; não é superusuário nem tem `CREATEROLE`/`CREATEDB`.
> **A conta é, de fato, incapaz de escrever em qualquer lugar.**
> O bloco B confirmou que `SET default_transaction_read_only = on` é aceito e retorna `on`.
- **Substitui:** [ADR-0001](ADR-0001-acesso-somente-leitura-ao-banco.md)

## Contexto

A [ADR-0001](ADR-0001-acesso-somente-leitura-ao-banco.md) previa criar um papel de banco dedicado,
`observatorio_ro`, restrito a leitura. O diagnóstico executado contra o servidor
(PostgreSQL 17.9, database `iesb`) invalidou essa via:

- a conta `data_iesb` **não possui `CREATEROLE`** — poder criar tabelas não implica poder criar papéis;
- as tabelas pertencem ao papel `iesb`, e `data_iesb` **não é proprietária**, o que também
  impediria repassar `SELECT` a terceiros sem `GRANT OPTION`.

O mesmo diagnóstico trouxe, porém, um resultado favorável e inesperado: sobre
`inep_educacao_superior_ies` e `inep_educacao_superior_cursos`, a conta aparece com **apenas
`SELECT`** — nenhuma concessão de `INSERT`, `UPDATE` ou `DELETE`. A premissa inicial do autor,
de que o acesso seria mais amplo que leitura, não se confirma para estas tabelas.

## Decisão

Abandonar a criação de papel e impor a restrição **na própria sessão da aplicação**, a cada conexão:

```sql
SET default_transaction_read_only = on;
SET statement_timeout = '60s';
SET idle_in_transaction_session_timeout = '60s';
```

Qualquer papel pode aplicar estes parâmetros à própria sessão — **não é preciso `CREATEROLE`**.
O efeito prático sobre a aplicação é o mesmo que se obteria com o papel dedicado: toda transação
nasce somente-leitura e qualquer `INSERT`, `UPDATE`, `DELETE` ou DDL falha no servidor, antes de
tocar em dado, ainda que uma falha na validação de SQL deixe o comando passar.

A execução desses comandos é responsabilidade do *pool* de conexões, não de cada consulta, para que
nenhum caminho de código possa esquecê-los. A verificação de que a trava está ativa
(`SHOW default_transaction_read_only`) integra o teste de fumaça da camada de dados.

As demais camadas previstas permanecem: allowlist de schemas e tabelas, validação AST com SQLGlot,
`LIMIT` obrigatório e parametrização.

## Alternativas consideradas

**Criar o papel dedicado (ADR-0001).** Inviável: falta `CREATEROLE` e propriedade das tabelas.

**Solicitar o papel ao IESB.** Continua sendo o ideal institucional e permanece como plano de
melhoria, mas deixa de ser bloqueante — a trava de sessão já entrega a garantia necessária, sem
depender de terceiros nem de prazo.

**Confiar apenas nas camadas de aplicação.** Rejeitada: era a opção 3 original, mais fraca, e
tornou-se desnecessária diante de uma alternativa gratuita e imediata.

## Consequências

A defesa em profundidade fica preservada e o `.env` deixa de exigir duas credenciais distintas —
a conta pessoal é a única, mas opera travada. A separação `PGUSER` / `PG_ADMIN_USER` no
`.env.example` perde a razão de ser e deve ser simplificada.

A garantia passa a depender de o pool aplicar os comandos em **toda** conexão nova: é um ponto único
de falha em código, que precisa de teste automatizado explícito, e não apenas de revisão.

A trava protege o banco, mas não substitui a validação AST — esta continua necessária contra
exfiltração de dados fora da allowlist e contra consultas de custo abusivo.

Se o bloco A do diagnóstico revelar que a conta possui privilégio de escrita por herança de papel
ou via `PUBLIC` — caminhos que `information_schema` não mostra —, a leitura acima se mantém válida:
a trava de sessão neutraliza a escrita de qualquer forma.

## Referências

- `scripts/db/03_privilegios_e_auxiliares.sql` — blocos A e B
- [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) — camadas de defesa
