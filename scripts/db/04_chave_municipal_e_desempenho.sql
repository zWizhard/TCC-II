-- =====================================================================
-- 04_chave_municipal_e_desempenho.sql — SOMENTE LEITURA.
--
-- Objetivo:
--   (1) fechar qual coluna de `municipio` e a chave de 7 digitos;
--   (2) medir cobertura territorial e das auxiliares;
--   (3) MEDIR o custo real de uma consulta agregada em `cursos`,
--       que hoje nao tem indice nenhum — isso decide se a camada
--       analitica precisa de pre-agregacao local.
--
-- Exportar cada aba separadamente (o DBeaver mistura result sets
-- de larguras diferentes num CSV unico).
-- =====================================================================

-- ---------------------------------------------------------------------
-- BLOCO A — qual coluna de `municipio` casa com o Censo?
-- `co_municipio` do Censo tem 7 digitos. Juntar pela coluna errada
-- retorna vazio ou parcial EM SILENCIO.
-- ---------------------------------------------------------------------
SELECT codigo_municipio_dv,
       length(codigo_municipio_dv::text) AS tam_dv,
       codigo_municipio,
       length(codigo_municipio::text)    AS tam_sem_dv,
       nome_municipio, latitude, longitude
FROM municipio
LIMIT 5;


-- ---------------------------------------------------------------------
-- BLOCO B — cobertura: os municipios do Censo existem em `municipio`?
-- Testa as DUAS colunas candidatas de uma vez. A que der 0 orfaos vence.
-- ---------------------------------------------------------------------
WITH mun_censo AS (
    SELECT DISTINCT co_municipio
    FROM inep_educacao_superior_cursos
    WHERE co_municipio ~ '^[0-9]{7}$'
)
SELECT 'municipios distintos no Censo'        AS verificacao,
       (SELECT COUNT(*) FROM mun_censo)::text AS resultado
UNION ALL
SELECT 'linhas em municipio',
       (SELECT COUNT(*) FROM municipio)::text
UNION ALL
SELECT 'orfaos usando codigo_municipio_dv',
       (SELECT COUNT(*) FROM mun_censo m
         WHERE NOT EXISTS (SELECT 1 FROM municipio x
                            WHERE x.codigo_municipio_dv::text = m.co_municipio))::text
UNION ALL
SELECT 'orfaos usando codigo_municipio',
       (SELECT COUNT(*) FROM mun_censo m
         WHERE NOT EXISTS (SELECT 1 FROM municipio x
                            WHERE x.codigo_municipio::text = m.co_municipio))::text
UNION ALL
SELECT 'municipio com lat/long nulos',
       (SELECT COUNT(*) FROM municipio
         WHERE latitude IS NULL OR longitude IS NULL)::text
UNION ALL
SELECT 'lat fora do Brasil (-34..6)',
       (SELECT COUNT(*) FROM municipio
         WHERE latitude IS NOT NULL AND (latitude < -34 OR latitude > 6))::text
UNION ALL
SELECT 'long fora do Brasil (-74..-34)',
       (SELECT COUNT(*) FROM municipio
         WHERE longitude IS NOT NULL AND (longitude < -74 OR longitude > -34))::text;


-- ---------------------------------------------------------------------
-- BLOCO C — populacao: anos disponiveis e cobertura
-- ---------------------------------------------------------------------
SELECT ano, COUNT(*) AS municipios, SUM(populacao) AS populacao_total
FROM ibge_populacao_estimada
GROUP BY ano
ORDER BY ano;


-- ---------------------------------------------------------------------
-- BLOCO D — MEDICAO: quanto custa uma agregacao tipica em `cursos`?
-- Consulta representativa do mapa: matriculas presenciais por municipio.
-- Rodar DUAS vezes e usar o SEGUNDO tempo (o primeiro paga leitura de disco).
-- Olhar em especial: "Seq Scan", "Execution Time" e "shared read".
-- ---------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT co_municipio,
       SUM(qt_mat)   AS matriculas,
       SUM(qt_curso) AS cursos
FROM inep_educacao_superior_cursos
WHERE nu_ano_censo = '2024'
  AND tp_dimensao  = 'Cursos presenciais ofertados no Brasil'
  AND co_municipio ~ '^[0-9]{7}$'
GROUP BY co_municipio;


-- ---------------------------------------------------------------------
-- BLOCO E — MEDICAO: o caso pesado (EAD, 673 mil linhas)
-- E este que um mapa de polos EAD teria de rodar a cada interacao.
-- ---------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT co_municipio, SUM(qt_mat) AS matriculas_ead
FROM inep_educacao_superior_cursos
WHERE nu_ano_censo = '2024'
  AND tp_modalidade_ensino = 'Curso a distância'
  AND co_municipio ~ '^[0-9]{7}$'
GROUP BY co_municipio;


-- ---------------------------------------------------------------------
-- BLOCO F — tamanho fisico das tabelas (dimensiona uma copia local)
-- ---------------------------------------------------------------------
SELECT relname AS tabela,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS tamanho_total,
       n_live_tup AS linhas_estimadas
FROM pg_class c
JOIN pg_stat_user_tables s ON s.relid = c.oid
WHERE relname IN ('inep_educacao_superior_cursos', 'inep_educacao_superior_ies',
                  'municipio', 'ibge_populacao_estimada', 'pib_municipios')
ORDER BY pg_total_relation_size(c.oid) DESC;
