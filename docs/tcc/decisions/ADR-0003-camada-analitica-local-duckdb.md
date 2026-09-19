# ADR-0003 — Camada analítica local em DuckDB

- **Data:** 2026-09-05
- **Status:** Aceita

## Contexto

A tabela `inep_educacao_superior_cursos` ocupa **609 MB** com 720.349 linhas e 223 colunas, e
**não possui nenhum índice**. Como a conta `data_iesb` detém apenas `SELECT` e não é proprietária
das tabelas ([ADR-0002](ADR-0002-sessao-somente-leitura.md)), criar índices é impossível.

Toda consulta filtrada por ano, unidade da federação, município ou dimensão de oferta implica
varredura sequencial completa da tabela, num servidor compartilhado por outros usuários da
instituição. Um mapa interativo, que reconsulta a cada deslocamento ou mudança de zoom, precisa
responder na ordem de 200 ms.

**Medição (`EXPLAIN ANALYZE`, 2026-09-05).** Duas agregações por município, ambas resolvidas por
*Parallel Seq Scan* com dois trabalhadores, lendo ~74.100 blocos de disco — a tabela inteira:

| Consulta | Linhas filtradas | Tempo de execução |
|---|---|---|
| Presenciais por município | 34.824 | **864 ms** |
| EAD por município | 673.756 | **1.492 ms** |

O custo é dominado pela varredura, não pelo volume filtrado: o caso "leve" também lê 609 MB.
Nenhum índice pode ser criado, e a filtragem por expressão regular sobre `co_municipio` impede
qualquer atalho. Entre quatro e sete vezes acima do orçamento de latência de uma interação de mapa,
e isso sem concorrência de outros usuários.

Um fato do domínio torna o problema tratável: **os dados são estáticos**. O recorte é o Censo de
2024, edição fechada, sem atualização prevista durante o trabalho.

## Decisão

Introduzir uma camada analítica local em **DuckDB**, alimentada por um script de ETL versionado que
lê do PostgreSQL do IESB uma única vez e materializa um arquivo local em formato colunar.

O PostgreSQL do IESB permanece a **fonte oficial** do dado. O arquivo local é camada de *serving*,
derivada e descartável: dashboard, mapa e Analista IA consultam apenas ele.

DuckDB foi escolhido por ser gratuito, de código aberto, embarcado — sem servidor nem serviço a
manter —, orientado a colunas, e por executar agregações sobre esse volume em tempo interativo numa
máquina comum. O ETL fica sob `scripts/etl/` e é parte do artefato acadêmico, garantindo reprodutibilidade.

## Alternativas consideradas

**PostgreSQL local espelhado.** Preservaria o dialeto SQL de origem, mas exige instalar e manter um
serviço, ocupa mais de 700 MB e, sendo orientado a linhas, permanece mais lento que uma solução
colunar para consultas que agregam poucas colunas sobre muitas linhas — exatamente o padrão do projeto.

**Apenas agregados pré-calculados, consultando o IESB para o detalhe.** Atenderia dashboard e mapa
com esforço mínimo, mas o Analista IA depende de consulta arbitrária sobre o grão fino e recairia
no caminho lento, justamente na funcionalidade mais sensível a latência percebida.

**Consultar o IESB diretamente, com cache.** Mantém a arquitetura original sem ETL, mas paga
varredura de 609 MB a cada combinação nova de filtros, fica sujeita à rede e à concorrência no
servidor compartilhado, e impede operação offline.

## Consequências

O tempo de resposta deixa de depender de rede e de concorrência de terceiros, e a plataforma passa a
**funcionar offline** — relevante para a apresentação e a defesa, onde falha de rede é risco real.

Ganho de segurança não previsto inicialmente: o SQL gerado a partir do LLM passa a executar **apenas
contra o arquivo local**, e nunca alcança o banco institucional. A validação continua necessária —
contra exfiltração fora da allowlist e consultas de custo abusivo —, mas o raio de alcance de uma
falha fica contido na máquina local.

Em contrapartida, surge um passo de ETL a manter, e o dado servido é um instantâneo. Como a edição
do Censo é fechada, o instantâneo não perde informação; ainda assim o artefato precisa registrar a
**data de extração** e o total de linhas, e a interface deve exibir a data de referência.

A validação do pipeline passa a exigir **conferência das somas de controle** entre origem e cópia
(2.561 e 720.349 linhas; `SUM(qt_curso)` = 45.776; `SUM(qt_mat)` = 10.227.266). Divergência
invalida a cópia.

O dialeto SQL do Analista IA passa a ser o do DuckDB, o que afeta a configuração do SQLGlot e a
allowlist, que agora aponta para as tabelas locais.

## Referências

- [`../../data/DATA_DICTIONARY.md`](../../data/DATA_DICTIONARY.md) — tamanhos e ausência de índices
- [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) — pipeline Text-to-SQL
