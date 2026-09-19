# ADR-0006 — Auditoria de dados sobre as extrações completas, não contra o banco

- **Data:** 2026-09-05
- **Status:** Aceita

## Contexto

A Fase 2 exigia inventariar 305 colunas (82 em `inep_educacao_superior_ies`, 223 em
`inep_educacao_superior_cursos`), medir cardinalidade, nulos, chaves candidatas e categorias.

Não há caminho de conexão programática configurado na máquina: não existe `.env` (apenas
`.env.example`), `psql` está ausente do PATH, `psycopg` não está instalado e não há `.venv`. O fluxo
herdado da Fase 1 é o autor executar SQL no DBeaver e exportar CSV. Existem, porém, extrações
completas das duas tabelas, e a Fase 1 provou que elas reproduzem o banco em cinco somas de
controle.

## Decisão

Realizar a auditoria da Fase 2 sobre as extrações completas e tratar como **fato verificado** tudo
que é derivável do conteúdo: contagem de linhas, cardinalidade, chave natural, grain, categorias,
distribuição, ausência de valor e formato de identificador.

Tudo que **não** é derivável da exportação — tipo SQL declarado, distinção entre `NULL` e string
vazia, padding de `CHAR`, índices, constraints — permanece marcado `A confirmar`, e cada afirmação
nova no dicionário recebe marcação explícita de proveniência. O script
`scripts/db/06_auditoria_fase2.sql` fica preparado para fechar essas lacunas contra o banco.

## Alternativas consideradas

- **Esperar a conexão direta.** Bloquearia a Fase 2 por tempo indeterminado, dependendo de instalação
  de dependências e de credenciais que o agente não pode criar.
- **Instalar `psycopg` e configurar `.env` imediatamente.** Exige credenciais do autor e altera o
  ambiente; adiado, mas mantido como caminho preferencial para as pendências de catálogo.
- **Auditar por amostragem.** Rejeitada: cardinalidade e prova de chave natural exigem a população
  inteira; amostra não distingue chave de quase-chave.

## Consequências

- O inventário fica completo e verificável a partir do repositório, sem acesso ao banco institucional.
- O dicionário passa a conviver com dois níveis de confiança, explicitados por coluna; apenas 12 das
  305 colunas têm tipo SQL confirmado.
- Fica pendente um bloqueio para a Fase 3: o padding de `co_municipio_ies` não pôde ser verificado, e
  um JOIN territorial sem `btrim()` retornaria zero linhas em silêncio.
- Nenhuma métrica do TCC pode se apoiar em tipo inferido; onde o tipo importa (comparação de
  `nu_ano_censo` como texto, `CHAR` com padding), a confirmação contra o banco é obrigatória.

## Desfecho da verificação (2026-09-05)

Ainda em 2026-09-05, o autor forneceu as credenciais e a conexão direta passou a funcionar
(`scripts/db/run_sql.py`). Todas as pendências `A confirmar` desta ADR foram verificadas contra o
banco. A decisão permanece **Aceita** — a auditoria sobre as extrações reproduziu o banco em tudo que
era derivável do conteúdo —, mas duas inferências foram **refutadas**:

- **Não há padding em `co_municipio_ies`** (`character(7)`, comprimento 7 no bruto e após `btrim()`).
  O bloqueio da Fase 3 registrado acima **não existe**: o JOIN territorial direto é seguro. A única
  coluna com padding real é `nu_cep_ies` (`character(12)`), que o projeto não usa.
- **Não existe `NULL` nas tabelas do Censo.** `cursos` é `NOT NULL` nas 223 colunas; `ies` só admite
  em `qt_tec_total`, onde há 0 ocorrências. O que a exportação mostrava como ausência é string vazia
  (459 `sg_ies`, 26 `nu_cep_ies`): o teste correto é `btrim(col) = ''`, não `IS NULL`.

Confirmados sem correção: tipos das 305 colunas lidos do `information_schema`, chave natural de
`cursos`, contaminação territorial, permissões e `ds_rede`. O dicionário deixa de conviver com dois
níveis de confiança nas colunas do Censo; o registro completo está no devlog
[Conexão direta ao banco e confirmação das pendências da Fase 2](../devlog/2026-09-05_conexao-direta-e-confirmacao-da-fase-2.md).
