# Fase 2 — inventário completo das tabelas de Educação Superior

## Objetivo

Fechar o inventário técnico das tabelas do Censo da Educação Superior no Big Data IESB: colunas,
grain, chaves, nulos, cardinalidade, categorias e identificadores territoriais, de modo a habilitar a
Fase 3 (estratégia de JOIN).

## Trabalho realizado

Auditoria em passada única sobre as extrações completas de `inep_educacao_superior_ies`
(2.561 × 82) e `inep_educacao_superior_cursos` (720.349 × 223). Confirmou-se que o universo de
Educação Superior no banco tem **exatamente estas duas tabelas** — as demais `inep_*` pertencem ao
Censo Escolar. Não existe tabela de docentes, discentes ou mantenedoras: corpo docente e técnico só
aparecem como colunas agregadas `qt_doc_*`/`qt_tec_*` no grain da IES, o que delimita o conjunto de
perguntas respondíveis pelo trabalho.

Atualizações: [`DATA_DICTIONARY.md`](../../data/DATA_DICTIONARY.md) (nova seção "Catálogo",
cardinalidade e proveniência por coluna, seções `ds_rede`, meso/microrregião e
`in_comunitaria`/`in_confessional`, pendências separadas entre "exigem o banco" e "independentes do
banco") e [`DATA_GRAIN.md`](../../data/DATA_GRAIN.md). Criado `scripts/db/06_auditoria_fase2.sql`,
somente-leitura, com inventário de tipos via `information_schema` e dez grupos de verificação.

## Decisões técnicas/metodológicas

- Auditar as extrações CSV em vez do banco, por ausência de caminho de conexão programática
  (`.env`, `psql`, `psycopg` e `.venv` inexistentes) — [ADR-0006](../decisions/ADR-0006-auditoria-sobre-extracoes-versionadas.md).
- Adotar `ies.ds_rede` ↔ `cursos.tp_rede` como comparação canônica de rede, dispensando tradução
  manual de códigos — [ADR-0007](../decisions/ADR-0007-comparacao-de-rede-via-ds-rede.md).

Achados que alteram a metodologia: chave natural exata de `cursos` provada em
`(nu_ano_censo, co_curso, co_municipio, tp_dimensao)` = 720.349 = `COUNT(*)`, encerrando as 452
sobras não explicadas; `co_curso` determina `co_ies`; `tp_dimensao` determina
`tp_modalidade_ensino`. **Correção relevante:** a contaminação por `'Cursos a distância'` atinge
**oito** colunas territoriais (`co_municipio`, `no_municipio`, `co_uf`, `sg_uf`, `no_uf`,
`co_regiao`, `no_regiao`, `in_capital`), as mesmas 11.778 linhas — logo `GROUP BY sg_uf` sem filtro
devolve 28 "UFs". `co_mesorregiao_ies` e `co_microrregiao_ies` não são códigos nacionais (15 códigos
para 131 nomes; 65 para 382): agrupar só pelo código funde regiões de estados distintos.
`qt_doc_total` é idêntica a `qt_doc_exe`. Identificação por nome é inválida (`no_ies` com 14
repetições, `sg_ies` vazia em 17,92%, homônimos municipais).

## Validação

Somas de controle reproduzidas exatamente: `qt_mat` 10.227.266, `qt_curso` 45.776, `qt_doc_total`
374.501, `qt_tec_total` 350.752. Nulos: nenhum em `cursos`; em IES apenas `sg_ies` (459) e
`nu_cep_ies` (26). Encoding UTF-8 conferido byte a byte, sem U+FFFD — o mojibake observado é
artefato do console Windows.

## Problemas/limitações

O padding de `co_municipio_ies` (`CHAR`) não é verificável por CSV; sem `btrim()`, um JOIN
territorial pode retornar zero linhas em silêncio. Apenas 12 das 305 colunas têm tipo SQL
confirmado; as demais permanecem `A confirmar` (a inferência já produzira divergência interna no
dicionário, corrigida). Nove linhas da dimensão "EAD ofertados no Brasil" não têm território e não
são elimináveis por filtro de `tp_dimensao` — motivo `A confirmar`. Nenhum JOIN foi executado.

## Próximo passo

Executar `scripts/db/06_auditoria_fase2.sql` no DBeaver e versionar as saídas em
`docs/data/raw/diagnostics/` ([ADR-0005](../decisions/ADR-0005-versionamento-das-evidencias-de-auditoria.md)),
ou instalar `psycopg` e criar o `.env`. Só então iniciar a Fase 3.
