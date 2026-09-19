-- =====================================================================
-- 05_verificacao_consolidada.sql — SOMENTE LEITURA.
--
-- O DBeaver exporta apenas UM result set por vez. Aqui TUDO cabe numa
-- consulta unica: basta exportar/copiar uma tabela.
--
-- As duas medicoes de tempo ficam no fim, separadas, porque EXPLAIN nao
-- pode ser combinado. Para elas, basta copiar a ultima linha do plano
-- ("Execution Time: ... ms").
-- =====================================================================

SELECT * FROM (

    -- ---- municipio: a tabela e realmente municipal? -------------------
    SELECT 1 AS ord, 'municipio' AS bloco, 'linhas (COUNT real)' AS verificacao,
           (SELECT COUNT(*)::text FROM municipio) AS resultado
    UNION ALL SELECT 2, 'municipio', 'codigos distintos (dv)',
           (SELECT COUNT(DISTINCT codigo_municipio_dv)::text FROM municipio)
    UNION ALL SELECT 3, 'municipio', 'amostra codigo_municipio_dv',
           (SELECT string_agg(x, ' | ') FROM (
                SELECT codigo_municipio_dv::text AS x FROM municipio ORDER BY 1 LIMIT 3) s)
    UNION ALL SELECT 4, 'municipio', 'amostra codigo_municipio',
           (SELECT string_agg(x, ' | ') FROM (
                SELECT codigo_municipio::text AS x FROM municipio ORDER BY 1 LIMIT 3) s)
    UNION ALL SELECT 5, 'municipio', 'comprimentos distintos de codigo_municipio_dv',
           (SELECT string_agg(DISTINCT length(codigo_municipio_dv::text)::text, ',') FROM municipio)
    UNION ALL SELECT 6, 'municipio', 'comprimentos distintos de codigo_municipio',
           (SELECT string_agg(DISTINCT length(codigo_municipio::text)::text, ',') FROM municipio)

    -- ---- a chave certa: qual coluna casa com o Censo? -----------------
    UNION ALL SELECT 10, 'chave', 'municipios distintos no Censo (7 digitos)',
           (SELECT COUNT(DISTINCT co_municipio)::text
              FROM inep_educacao_superior_cursos WHERE co_municipio ~ '^[0-9]{7}$')
    UNION ALL SELECT 11, 'chave', 'ORFAOS usando codigo_municipio_dv  (0 = chave certa)',
           (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT co_municipio FROM inep_educacao_superior_cursos
                 WHERE co_municipio ~ '^[0-9]{7}$') m
             WHERE NOT EXISTS (SELECT 1 FROM municipio x
                                WHERE x.codigo_municipio_dv::text = m.co_municipio))
    UNION ALL SELECT 12, 'chave', 'ORFAOS usando codigo_municipio     (0 = chave certa)',
           (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT co_municipio FROM inep_educacao_superior_cursos
                 WHERE co_municipio ~ '^[0-9]{7}$') m
             WHERE NOT EXISTS (SELECT 1 FROM municipio x
                                WHERE x.codigo_municipio::text = m.co_municipio))
    UNION ALL SELECT 13, 'chave', 'ORFAOS sede de IES vs municipio (dv)',
           (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT btrim(co_municipio_ies) AS m FROM inep_educacao_superior_ies) i
             WHERE NOT EXISTS (SELECT 1 FROM municipio x
                                WHERE x.codigo_municipio_dv::text = i.m))

    -- ---- coordenadas ---------------------------------------------------
    UNION ALL SELECT 20, 'coordenadas', 'lat OU long nulos',
           (SELECT COUNT(*)::text FROM municipio WHERE latitude IS NULL OR longitude IS NULL)
    UNION ALL SELECT 21, 'coordenadas', 'lat fora do Brasil (-34..6)',
           (SELECT COUNT(*)::text FROM municipio
             WHERE latitude IS NOT NULL AND (latitude < -34 OR latitude > 6))
    UNION ALL SELECT 22, 'coordenadas', 'long fora do Brasil (-74..-34)',
           (SELECT COUNT(*)::text FROM municipio
             WHERE longitude IS NOT NULL AND (longitude < -74 OR longitude > -34))
    UNION ALL SELECT 23, 'coordenadas', 'amostra lat,long',
           (SELECT string_agg(x, ' | ') FROM (
                SELECT nome_municipio || ' (' || latitude || ',' || longitude || ')' AS x
                  FROM municipio WHERE latitude IS NOT NULL ORDER BY 1 LIMIT 3) s)

    -- ---- populacao -----------------------------------------------------
    UNION ALL SELECT 30, 'populacao', 'anos disponiveis',
           (SELECT string_agg(DISTINCT ano::text, ',' ORDER BY ano::text) FROM ibge_populacao_estimada)
    UNION ALL SELECT 31, 'populacao', 'municipios no ano mais recente',
           (SELECT COUNT(*)::text FROM ibge_populacao_estimada
             WHERE ano = (SELECT MAX(ano) FROM ibge_populacao_estimada))
    UNION ALL SELECT 32, 'populacao', 'populacao total no ano mais recente',
           (SELECT SUM(populacao)::text FROM ibge_populacao_estimada
             WHERE ano = (SELECT MAX(ano) FROM ibge_populacao_estimada))
    UNION ALL SELECT 33, 'populacao', 'comprimentos de cod_municipio',
           (SELECT string_agg(DISTINCT length(cod_municipio::text)::text, ',')
              FROM ibge_populacao_estimada)

) t ORDER BY ord;


-- =====================================================================
-- MEDICAO 1 — agregacao presencial por municipio (caso leve)
-- Rodar DUAS vezes; reportar o "Execution Time" da SEGUNDA execucao.
-- =====================================================================
EXPLAIN (ANALYZE, BUFFERS)
SELECT co_municipio, SUM(qt_mat) AS matriculas, SUM(qt_curso) AS cursos
FROM inep_educacao_superior_cursos
WHERE nu_ano_censo = '2024'
  AND tp_dimensao  = 'Cursos presenciais ofertados no Brasil'
  AND co_municipio ~ '^[0-9]{7}$'
GROUP BY co_municipio;


-- =====================================================================
-- MEDICAO 2 — agregacao EAD por municipio (caso pesado, 673 mil linhas)
-- E o que um mapa de polos rodaria a cada interacao.
-- =====================================================================
EXPLAIN (ANALYZE, BUFFERS)
SELECT co_municipio, SUM(qt_mat) AS matriculas_ead
FROM inep_educacao_superior_cursos
WHERE nu_ano_censo = '2024'
  AND tp_modalidade_ensino = 'Curso a distância'
  AND co_municipio ~ '^[0-9]{7}$'
GROUP BY co_municipio;
