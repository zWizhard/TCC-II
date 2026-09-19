# Auditoria de schema das tabelas do Censo da Educação Superior 2024

## Objetivo

Descobrir e documentar o schema real das duas tabelas centrais do trabalho — instituições e
cursos — a partir de extrações em CSV fornecidas pelo autor, substituindo por fatos verificados
as marcações provisórias de *A confirmar* na documentação de dados.

## Trabalho realizado

Confirmou-se que a fonte é um banco **PostgreSQL** acadêmico do IESB, com autenticação por
login e senha. As extrações auditadas correspondem ao Censo de **2024**: `inep_educacao_superior_ies`
(2.561 linhas, 82 colunas, 1,2 MB) e `inep_educacao_superior_cursos` (720.349 linhas, 223 colunas,
560 MB). Os arquivos foram percorridos em passadas de leitura sequencial, sem carregamento integral
em memória, apurando-se contagens, distintos, categorias, nulos e somas de controle.

Foram reescritos com conteúdo verificado os documentos `DATA_DICTIONARY.md`, `DATA_GRAIN.md` e
`JOIN_STRATEGY.md`, e propagados ao `CLAUDE.md` os fatos cuja violação produz número errado.

## Decisões técnicas/metodológicas

**A granularidade da tabela de cursos não é o curso.** Uma linha corresponde a curso × município ×
dimensão de oferta: há 720.349 linhas para apenas 46.150 cursos distintos. Cursos presenciais têm
exatamente uma linha cada; cursos a distância são replicados por município de polo, chegando a
1.197 linhas para um único curso. A modalidade a distância responde por 93,5% das linhas.

**As métricas são distribuídas entre os polos, não replicadas.** A verificação foi feita por
inspeção de linhas reais de um mesmo curso, cujos valores de `qt_mat` variam por município em vez
de repetir. A soma direta é, portanto, correta, e totaliza 10.227.266 matrículas em 2024. A exceção
é `qt_curso`, nulo em toda linha de polo: por isso a contagem correta de cursos é `SUM(qt_curso)`
(45.776), e não `COUNT(*)` nem `COUNT(DISTINCT co_curso)`, que superestimam a métrica.

**A coluna `co_municipio` não é integralmente numérica:** 11.778 linhas trazem o literal
`'Cursos a distância'`. Estabeleceu-se como pré-condição de qualquer agregação territorial o
filtro por código IBGE de sete dígitos, sem o qual um município inexistente passa a figurar nos
mapas e rankings.

**Registraram-se duas ambiguidades de magnitude conhecida**, ambas a serem resolvidas junto ao
usuário e não por omissão: "universidade" como IES em sentido amplo (2.561) ou como Organização
Acadêmica (206), diferença de doze vezes; e o recorte territorial por sede da instituição (698
municípios) ou por local de oferta, incluindo polos (3.551 municípios), diferença de cinco vezes.
A definição do recorte territorial permanece **em aberto** e deve ser explicitada na plataforma.

## Validação

O JOIN entre cursos e instituições por `co_ies` foi verificado como N:1 com zero chaves órfãs nos
dois sentidos. Confirmou-se que `co_curso` é globalmente único e já determina a instituição,
tornando `co_ies` redundante na chave. O significado do código `tp_rede` na tabela de instituições
foi estabelecido por cruzamento com a categoria administrativa, com correspondência exata
(317 e 2.244 linhas), observando-se que o valor `'1'` agrega também as 28 instituições de categoria
*Especial* e portanto não equivale a "pública".

Um erro de método foi cometido e corrigido durante a auditoria: o script inicial acessava colunas
com valor-padrão, o que converteu **coluna inexistente em valor vazio** e levou a registrar
`in_capital` como integralmente nula na tabela de instituições. A coluna correta é `in_capital_ies`
e possui dados (919 e 1.642). A regra correspondente foi incorporada à skill `schema-audit`.

## Problemas/limitações

Ambos os extratos contêm **apenas o ano de 2024**, o que inviabiliza qualquer análise de série
temporal enquanto não se confirmar se o banco possui edições anteriores. A coluna `tp_rede` aparece
como código em uma tabela e como rótulo na outra, impedindo comparação direta. O autor relata que
seu acesso ao banco provavelmente não é restrito a leitura, o que compromete a primeira camada da
defesa em profundidade prevista para o Analista IA.

> A confirmar: cobertura temporal do banco, tipos reais das colunas e existência de usuário somente-leitura.

## Próximo passo

Confirmar junto ao IESB a cobertura de anos e solicitar credencial somente-leitura; obter a malha
municipal do IBGE para o mapa coroplético; em seguida, iniciar a camada semântica sobre o schema
agora verificado.
