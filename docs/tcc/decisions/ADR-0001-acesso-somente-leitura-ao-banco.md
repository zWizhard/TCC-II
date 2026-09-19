# ADR-0001 — Acesso somente-leitura ao banco pelo Analista IA

- **Data:** 2026-09-05
- **Status:** **Substituída por [ADR-0002](ADR-0002-sessao-somente-leitura.md)** no mesmo dia.

> O diagnóstico executado em 2026-09-05 mostrou que a conta `data_iesb` **não possui `CREATEROLE`**
> e **não é dona** das tabelas — não pode criar o papel proposto aqui. Em compensação, revelou que a
> conta já tem apenas `SELECT` sobre as tabelas do Censo. A ADR-0002 registra a estratégia adotada.
> O script `02_criar_papel_somente_leitura.sql` fica mantido apenas como referência e **não deve ser executado**.

## Contexto

O Analista IA traduz perguntas em linguagem natural para SQL executado contra o PostgreSQL
acadêmico do IESB. A arquitetura de segurança prevê defesa em profundidade, cuja **primeira e
mais forte camada** é um usuário de banco sem qualquer permissão de escrita: as camadas de
aplicação (allowlist, validação AST, timeout) protegem contra SQL malicioso *conhecido*, mas
apenas a permissão do banco protege contra o que a aplicação deixar passar.

A conta disponível ao autor (`data_iesb`) **não é restrita a leitura**. Mantê-la na aplicação
significaria que uma falha na validação — um caso não previsto no parser, uma injeção via
saída do LLM — poderia alterar ou destruir dados de um banco **compartilhado** por outros usuários.

## Decisão

Criar um papel dedicado `observatorio_ro`, usado exclusivamente pela API e pelo Analista IA,
com a própria conta do autor. A conta pessoal nunca é usada pela aplicação.

A trava principal do papel **não são os `GRANT`**, e sim:

```sql
ALTER ROLE observatorio_ro SET default_transaction_read_only = on;
```

Toda transação do papel nasce somente-leitura. Isso resiste a um `GRANT` concedido por engano e
cobre o schema `public` aberto por padrão no PostgreSQL anterior à versão 15 — situação em que
`GRANT`/`REVOKE` isolados não impediriam a criação de objetos. Complementarmente,
`statement_timeout` e `idle_in_transaction_session_timeout` passam a ser impostos **pelo servidor**,
e não apenas pela aplicação.

A execução é manual e em dois passos: um diagnóstico somente-leitura verifica os pré-requisitos
(`CREATEROLE` e capacidade de repassar `SELECT`) antes de qualquer alteração; a criação do papel
só ocorre se o diagnóstico aprovar. Um teste de invasão — tentar `CREATE`, `DELETE` e `UPDATE`
conectado como o novo papel — valida a trava antes de a aplicação passar a usá-la.

## Alternativas consideradas

**Solicitar o papel ao IESB.** Seria o caminho mais limpo institucionalmente, por não exigir que
uma conta de aluno crie papéis num servidor compartilhado. Descartada como via principal pela
dependência de terceiros e prazo incerto, mas permanece como plano B.

**Manter a conta pessoal e confiar apenas nas camadas de aplicação.** Rejeitada: reduz a defesa em
profundidade a uma única linha falível e expõe um banco compartilhado. Se o diagnóstico reprovar
os pré-requisitos, esta passa a ser a situação de fato — e nesse caso a limitação deve ser
**declarada explicitamente** no texto do TCC, não silenciada.

## Consequências

A aplicação passa a exigir duas credenciais distintas no `.env`: a do papel de leitura, usada em
produção, e opcionalmente a pessoal, para exploração manual. O `.env.example` reflete essa separação.

O papel é um objeto novo num banco compartilhado, o que recomenda confirmação prévia com o
responsável pelo ambiente. Os scripts incluem seção de reversão.

Se os pré-requisitos falharem, esta ADR deverá ser substituída por outra que registre o caminho
efetivamente adotado e a limitação resultante.

## Referências

- `scripts/db/01_diagnostico.sql`, `scripts/db/02_criar_papel_somente_leitura.sql`
- [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) — camadas de defesa
- [`../../ENVIRONMENT.md`](../../ENVIRONMENT.md) — encaminhamento e alternativas
