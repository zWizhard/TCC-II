# Camada analítica local e definição do recorte territorial

## Objetivo

Decidir como servir os dados ao dashboard, ao mapa e ao Analista IA diante da ausência de índices na
tabela de cursos, e resolver a ambiguidade territorial identificada na auditoria de schema.

## Trabalho realizado

O terceiro diagnóstico confirmou que a conta `data_iesb` é incapaz de escrever em qualquer objeto do
banco — `SELECT` verdadeiro e `INSERT`, `UPDATE`, `DELETE`, `CREATE` falsos, verificados por
`has_*_privilege`, que considera também concessões via `PUBLIC` e herança de papel. A
[ADR-0002](../decisions/ADR-0002-sessao-somente-leitura.md) passou a confirmada empiricamente.

O mesmo diagnóstico revelou oito tabelas auxiliares legíveis, entre as quais `municipio`, que contém
**latitude e longitude**, e `ibge_populacao_estimada`, que fornece o denominador necessário à
normalização do mapa coroplético. Ambas dispensam download externo. Não há, porém, geometria de
polígono no banco: apenas ponto.

Levantou-se o tamanho físico das tabelas, e registraram-se duas decisões estruturantes em ADR.

## Decisões técnicas/metodológicas

**Camada analítica local em DuckDB ([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)).**
A tabela de cursos ocupa 609 MB, não possui índice algum e não é possível criá-los, de modo que todo
filtro implica varredura sequencial completa num servidor compartilhado — duas ordens de grandeza
acima do que um mapa interativo tolera. Como o recorte é o Censo de 2024, edição fechada, um
instantâneo local não perde informação. O PostgreSQL do IESB permanece a fonte oficial; o arquivo
local é camada de serviço, derivada e reprodutível por script de ETL versionado.

Um ganho de segurança não previsto acompanha a decisão: o SQL originado do LLM passa a executar
apenas contra o arquivo local, sem alcançar o banco institucional. As camadas de validação
permanecem necessárias, mas o raio de alcance de uma falha fica contido.

**Recorte territorial explícito ([ADR-0004](../decisions/ADR-0004-recorte-territorial-duplo.md)).**
Em vez de escolher entre sede da instituição (698 municípios) e local de oferta, incluindo polos de
educação a distância (3.551 municípios), a plataforma expõe os dois como controle de primeira classe.
O recorte torna-se dimensão obrigatória do QueryPlan, e todo indicador territorial declara sob qual
foi calculado. A diferença de aproximadamente cinco vezes deixa de ser decisão oculta de
implementação e passa a constituir achado do trabalho sobre a interiorização do ensino superior.

## Validação

Corrigiu-se um alarme falso registrado na etapa anterior: havia-se advertido que `co_municipio_ies`,
por ser do tipo `character`, traria preenchimento com espaços à direita. A amostragem mostrou
valores de comprimento exatamente sete, sem preenchimento, tornando o JOIN direto seguro.

Constatou-se que `n_live_tup` do catálogo é estimativa e não contagem — a tabela de cursos aparece
com 718.906 linhas onde há 720.349. Por isso o valor de 27 linhas atribuído a `municipio` não foi
aceito: 800 kB são incompatíveis com essa contagem, e a verificação real ficou pendente.

## Problemas/limitações

O DBeaver exporta apenas um conjunto de resultados por vez, o que fez os scripts 03 e 04 chegarem
truncados. O script 05 foi reescrito para consolidar todas as verificações numa consulta única.

Permanecem pendentes: a contagem real de `municipio` e qual de suas duas colunas de código casa com
o Censo — juntar pela errada retorna resultado parcial em silêncio —, além da medição do tempo de
execução das agregações, que confirmará a magnitude do ganho esperado com a camada local.

> A confirmar: cobertura de `municipio`, chave municipal correta e tempos medidos.

## Próximo passo

Executar o script 05 e, com a chave municipal confirmada, escrever o ETL de carga do DuckDB com
conferência das somas de controle entre origem e cópia.
