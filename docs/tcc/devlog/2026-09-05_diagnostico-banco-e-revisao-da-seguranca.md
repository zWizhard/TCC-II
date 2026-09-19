# Diagnóstico do banco e revisão da estratégia de segurança

## Objetivo

Executar o diagnóstico de privilégios e schema contra o PostgreSQL do IESB, verificar a viabilidade
do papel somente-leitura previsto na ADR-0001 e confrontar a auditoria feita sobre os CSVs com as
tabelas reais.

## Trabalho realizado

O autor executou `scripts/db/01_diagnostico.sql` e forneceu a saída. Confirmou-se servidor
**PostgreSQL 17.9**, database `iesb`, schema `public`, com as tabelas do Censo pertencentes ao papel
`iesb` e a conta `data_iesb` figurando com **apenas `SELECT`** sobre elas.

**A auditoria dos CSVs foi integralmente validada contra o banco**: 2.561 linhas em instituições,
720.349 em cursos, soma de `qt_curso` igual a 45.776, soma de `qt_mat` igual a 10.227.266 e 46.150
cursos distintos — todos idênticos ao apurado nos arquivos. Os CSVs são, portanto, as tabelas
completas, e não recortes.

Documentaram-se os tipos reais das colunas, criou-se `scripts/db/03_privilegios_e_auxiliares.sql`
para dirimir pontos que a exportação do DBeaver deixou ambíguos, e revisou-se a decisão de segurança.

## Decisões técnicas/metodológicas

**A ADR-0001 foi substituída pela [ADR-0002](../decisions/ADR-0002-sessao-somente-leitura.md).**
A conta não possui `CREATEROLE` nem é proprietária das tabelas, o que inviabiliza criar o papel
`observatorio_ro`. Adotou-se impor a restrição **na sessão**, com o pool de conexões aplicando
`default_transaction_read_only`, `statement_timeout` e `idle_in_transaction_session_timeout` em toda
conexão nova. Qualquer papel pode aplicar esses parâmetros a si próprio, sem privilégio especial, e
o efeito prático é equivalente ao do papel dedicado, com a vantagem de não criar objeto novo num
banco compartilhado.

**Três incompatibilidades de tipo foram registradas**, todas capazes de produzir erro silencioso:
`nu_ano_censo` é texto nas duas tabelas, exigindo `'2024'` e não `2024`; `co_municipio_ies` é `CHAR`
e portanto vem preenchido com espaços à direita, exigindo `btrim()` antes de comparação com a malha
do IBGE; e `tp_rede` é `integer` em instituições e `character varying` em cursos, confirmando que a
divergência observada nos CSVs pertence ao schema e não à exportação.

## Validação

Todas as somas de controle da auditoria anterior foram reproduzidas pelo banco sem divergência.
O bloco A do novo script substitui `information_schema.table_privileges` por `has_table_privilege`,
que considera também concessões via `PUBLIC` e herança de papel — caminhos invisíveis na consulta
original e capazes de esconder permissão de escrita.

## Problemas/limitações

Constatou-se que existe **um único índice** em todo o conjunto, a chave primária da tabela de
instituições. A tabela de cursos, com 720.349 linhas e 223 colunas, **não possui nenhum**, e como a
conta detém apenas `SELECT` e não é proprietária, não há como criá-los. Todo filtro por ano, unidade
da federação, município ou dimensão implica varredura sequencial completa, o que inviabiliza consultar
essa tabela ao vivo a cada interação de mapa. A camada analítica precisará de pré-agregação, e a
forma de obtê-la permanece **decisão de arquitetura em aberto**.

O catálogo revelou tabelas auxiliares potencialmente úteis — `municipio`, `ibge_populacao_estimada`,
`IBGE_agregados_por_municipio_basico`, `pib_municipios`, entre outras — cujas colunas e permissão de
leitura ainda não foram verificadas. A tabela de população é particularmente relevante por fornecer
o denominador sem o qual o mapa coroplético representaria a distribuição populacional em vez do
fenômeno estudado.

> A confirmação empírica dos blocos A e B do script 03 continua pendente.

## Próximo passo

Executar o script 03 para confirmar a ausência de privilégio de escrita, validar a trava de sessão e
inspecionar as tabelas auxiliares; em seguida, decidir a estratégia de pré-agregação da camada analítica.
