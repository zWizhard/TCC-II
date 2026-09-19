# Chave municipal, tabela-ponte e medição de desempenho

## Objetivo

Fechar qual coluna identifica o município nas tabelas auxiliares, verificar a cobertura das
coordenadas e medir o custo real das agregações sobre a tabela de cursos, confirmando ou refutando
a premissa que motivou a adoção de uma camada analítica local.

## Trabalho realizado

Executou-se a verificação consolidada. A tabela `municipio` possui **5.599 linhas** — e não as 27
sugeridas pelo catálogo, cuja estimativa se mostrou inservível também para a tabela de cursos, ali
reportada com 718.906 linhas onde existem 720.349.

Confirmou-se que `codigo_municipio_dv` tem sete dígitos e casa com o Censo **sem nenhum órfão**,
enquanto `codigo_municipio`, de seis dígitos, falha em todos os 3.551 municípios. Os municípios de
sede das instituições também casam integralmente. As coordenadas estão preenchidas em 100% das
linhas.

Registraram-se as medições de desempenho e atualizaram-se dicionário, estratégia de JOIN e a
[ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md) com os números apurados.

## Decisões técnicas/metodológicas

**`municipio` passa a ser tabela-ponte obrigatória.** Descobriu-se que as auxiliares não concordam
sobre o formato do código: o Censo usa sete dígitos, ao passo que `ibge_populacao_estimada` usa
**seis**. Ligar população diretamente ao Censo produziria **zero linhas sem gerar erro algum** —
precisamente a classe de falha silenciosa que o projeto se comprometeu a evitar. Como `municipio`
carrega as duas representações, todo caminho entre o Censo e as auxiliares passa obrigatoriamente
por ela, e o padrão de consulta foi documentado com exemplo correto e incorreto lado a lado.

**Adotou-se a população de 2024 como denominador**, para coincidir com o ano do Censo. A série vai
de 2000 a 2026, mas 2025 e 2026 são projeção e **2023 não existe** na tabela.

## Validação

As duas agregações típicas de mapa foram medidas com `EXPLAIN ANALYZE`. Ambas foram resolvidas por
varredura sequencial paralela com dois trabalhadores, lendo cerca de 74.100 blocos — a tabela
inteira, em ambos os casos:

| Consulta | Linhas após filtro | Tempo |
|---|---|---|
| Presenciais por município | 34.824 | **864 ms** |
| EAD por município | 673.756 | **1.492 ms** |

O resultado confirma a premissa da ADR-0003 e acrescenta um detalhe relevante: o custo é dominado
pela varredura, não pelo volume filtrado — a consulta "leve" também percorre os 609 MB. Estando
entre quatro e sete vezes acima do orçamento de latência de uma interação de mapa, e isso sem
concorrência de outros usuários, a camada local deixa de ser otimização e passa a ser requisito.

## Problemas/limitações

Dois achados ficaram em aberto e ambos precedem qualquer plotagem ou cálculo de cobertura.

Há **cinco registros com coordenada fora do envelope do território brasileiro**: três em longitude,
provavelmente ilhas legítimas — Fernando de Noronha situa-se além do limite adotado —, e **dois em
latitude, sem explicação plausível**, já que o país se estende de −33,75° a +5,27°.

A tabela contém **5.599 municípios**, cerca de 29 a mais que os 5.570 a 5.571 oficiais. A diferença
pode corresponder a municípios extintos ou a entidades não municipais, e precisa ser esclarecida
antes que o total seja usado como denominador de cobertura territorial.

> A confirmar: as duas latitudes anômalas, a origem dos registros excedentes e a cardinalidade
> entre `municipio` e a tabela de população.

## Próximo passo

Investigar os registros anômalos de `municipio` e, em seguida, escrever o ETL de carga do DuckDB com
conferência das somas de controle entre origem e cópia.
