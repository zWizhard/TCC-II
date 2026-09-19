# Documentação — Observatório Inteligente da Educação Superior

Mapa da documentação. Carregue apenas o arquivo relevante à tarefa em curso.

| Caminho | Conteúdo | Quando ler |
|---|---|---|
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | Máquina, ferramentas instaladas/ausentes, seleção do LLM local | Setup, escolha de modelo, problema de ambiente |
| [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md) | Tabelas e colunas **verificadas** do Big Data IESB | Antes de escrever SQL |
| [`data/DATA_GRAIN.md`](data/DATA_GRAIN.md) | Grain de cada tabela e como foi provado | Antes de agregar ou juntar |
| [`data/JOIN_STRATEGY.md`](data/JOIN_STRATEGY.md) | JOINs validados, chaves, cardinalidade | Antes de qualquer JOIN |
| [`tcc/architecture/AI_ANALYST.md`](tcc/architecture/AI_ANALYST.md) | Pipeline Text-to-SQL, QueryPlan, segurança | Tarefas de IA |
| [`tcc/DEVLOG_INDEX.md`](tcc/DEVLOG_INDEX.md) | Índice cronológico do desenvolvimento | Retomar contexto, escrever o artigo |
| [`tcc/devlog/`](tcc/devlog/) | Registros curtos por tarefa | Detalhe de uma etapa específica |
| [`tcc/decisions/`](tcc/decisions/) | ADRs — decisões estruturantes | Entender ou revisar uma escolha |

Scripts de banco (execução manual): [`../scripts/db/`](../scripts/db/).
Dados brutos, não versionados: `data/raw/`.

`tcc/methodology/` e `tcc/data/` serão criados quando houver conteúdo verificado — não antecipadamente.

## Convenção

Tudo aqui é **fato verificado** ou está explicitamente marcado como `A confirmar`.
Nada de schema, métrica ou resultado suposto. Ver a regra de ouro em [`../CLAUDE.md`](../CLAUDE.md).
