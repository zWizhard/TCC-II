# Confirmação do acesso ao banco e estratégia de papel somente-leitura

## Objetivo

Registrar os parâmetros de conexão ao PostgreSQL do IESB, encerrar a pendência sobre a cobertura
temporal dos dados e preparar a criação de um papel de banco restrito a leitura para uso da API e
do Analista IA.

## Trabalho realizado

O autor confirmou a conexão ao banco acadêmico (`iesb`, porta 5432, autenticação nativa por login
e senha) e informou que os dados cobrem **exclusivamente o ano de 2024**. Os arquivos CSV brutos
foram movidos para `docs/data/raw/`, e o `.gitignore` passou a ancorar o padrão em qualquer nível
(`**/data/raw/`), além da regra `*.csv` já existente.

Foram criados dois scripts em `scripts/db/`: um diagnóstico estritamente somente-leitura, que
verifica versão do servidor, privilégios da conta, propriedade das tabelas, tipos reais das colunas
e conferência das contagens contra a auditoria dos CSVs; e o script de criação do papel
`observatorio_ro`, marcado como execução manual condicionada à aprovação do diagnóstico.

Host e nome de usuário foram deliberadamente mantidos fora dos arquivos versionados, permanecendo
apenas no `.env` local, que o `.gitignore` exclui e um hook impede de ser lido ou escrito pelo agente.

## Decisões técnicas/metodológicas

Adotou-se a criação de um papel restrito com a própria conta do autor, entre três alternativas
avaliadas — decisão registrada em [ADR-0001](../decisions/ADR-0001-acesso-somente-leitura-ao-banco.md).

A trava principal do papel não são as concessões de privilégio, e sim
`default_transaction_read_only = on` aplicado ao papel: toda transação nasce somente-leitura,
o que resiste a uma concessão indevida e cobre o schema `public` aberto por padrão em versões do
PostgreSQL anteriores à 15, situação em que revogações isoladas não impediriam a criação de objetos.
Somaram-se limites de tempo impostos pelo servidor, e não apenas pela aplicação.

A execução foi deliberadamente dividida em diagnóstico e alteração, porque poder criar tabelas não
implica poder criar papéis, e porque a conta pode não ter permissão de repassar leitura sobre
tabelas de outro proprietário. Sem esses dois pré-requisitos a estratégia é inviável, e o script de
alteração não deve ser executado.

**A confirmação de que existe apenas o ano de 2024 restringe o trabalho a um recorte transversal.**
A restrição foi propagada ao `CLAUDE.md` como regra explícita: nem a interface nem o Analista IA
podem produzir afirmações de evolução, tendência ou crescimento, por não haver base nos dados.

## Validação

Nenhuma consulta foi executada contra o banco nesta etapa: o agente não possui a senha, e não deve
possuí-la. Os scripts foram escritos para execução manual pelo autor. O script de criação inclui
verificação posterior das travas aplicadas e um teste de invasão — tentativas de `CREATE`, `DELETE`
e `UPDATE` conectado como o novo papel, que devem falhar, e um `SELECT` que deve retornar 2.561 —
antes de a aplicação passar a usar a credencial.

## Problemas/limitações

A viabilidade da estratégia depende de dois privilégios ainda não verificados. Trata-se, além disso,
de um banco compartilhado: criar um papel afeta o servidor como um todo, o que recomenda
confirmação prévia com o responsável pelo ambiente.

Caso o diagnóstico reprove, restam solicitar o papel ao IESB ou operar apenas com as camadas de
aplicação — hipótese em que a limitação da defesa em profundidade deverá constar explicitamente
do texto do TCC.

## Próximo passo

Executar o diagnóstico e, conforme o resultado, criar o papel; em seguida, verificar se o banco já
oferece malha municipal e indicadores auxiliares, o que evitaria depender de download externo para
o mapa coroplético.
