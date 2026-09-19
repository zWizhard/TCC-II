-- =====================================================================
-- 07_fase2_aprofundamento.sql — SOMENTE LEITURA.
--
-- Investiga os tres achados novos do script 06 que ficaram sem explicacao:
--   (1) ibge_populacao_estimada tem 50 pares (ano, municipio) duplicados;
--   (2) municipio tem 5.599 linhas contra 5.570-5.571 municipios oficiais;
--   (3) cursos tem 9 linhas na dimensao "EAD ofertados no Brasil" sem territorio.
--
-- Exportar como: 2026-09-05_07_aprofundamento.csv
-- =====================================================================
SELECT * FROM (

    -- ---- 1. As duplicatas de populacao repetem o valor ou divergem? --
    -- Se divergirem, nao ha como escolher sem criterio: o denominador do
    -- coropletico fica comprometido ate decidirmos qual linha vale.
      SELECT 1 AS ord, 'populacao' AS bloco, 'pares (ano, municipio) duplicados' AS verificacao,
             (SELECT COUNT(*)::text FROM (
                SELECT ano, cod_municipio FROM ibge_populacao_estimada
                 GROUP BY ano, cod_municipio HAVING COUNT(*) > 1) s) AS resultado
    UNION ALL SELECT 2, 'populacao', 'desses, quantos tem populacao DIVERGENTE',
             (SELECT COUNT(*)::text FROM (
                SELECT ano, cod_municipio FROM ibge_populacao_estimada
                 GROUP BY ano, cod_municipio
                HAVING COUNT(*) > 1 AND COUNT(DISTINCT populacao) > 1) s)
    UNION ALL SELECT 3, 'populacao', 'anos em que a duplicata ocorre',
             (SELECT string_agg(DISTINCT ano::text, ', ' ORDER BY ano::text) FROM (
                SELECT ano, cod_municipio FROM ibge_populacao_estimada
                 GROUP BY ano, cod_municipio HAVING COUNT(*) > 1) s)
    UNION ALL SELECT 4, 'populacao', 'amostra de duplicata (municipio: valores)',
             (SELECT string_agg(t, ' | ') FROM (
                SELECT d.cod_municipio::text || ' em ' || d.ano::text || ': '
                       || (SELECT string_agg(p.populacao::text, '/')
                             FROM ibge_populacao_estimada p
                            WHERE p.ano = d.ano AND p.cod_municipio = d.cod_municipio) AS t
                  FROM (SELECT ano, cod_municipio FROM ibge_populacao_estimada
                         GROUP BY ano, cod_municipio HAVING COUNT(*) > 1
                         LIMIT 5) d) s)

    -- ---- 2. De onde vem o excedente de municipios --------------------
    UNION ALL SELECT 10, 'municipio', 'linhas totais',
             (SELECT COUNT(*)::text FROM municipio)
    UNION ALL SELECT 11, 'municipio', 'codigos sentinela (prefixo 9)',
             (SELECT COALESCE(string_agg(codigo_municipio_dv::text || '=' || nome_municipio, ' | '), 'nenhum')
                FROM municipio WHERE codigo_municipio_dv::text LIKE '9%')
    UNION ALL SELECT 12, 'municipio', 'linhas com codigo IBGE plausivel (prefixo 1-5)',
             (SELECT COUNT(*)::text FROM municipio
               WHERE codigo_municipio_dv::text ~ '^[1-5][0-9]{6}$')
    UNION ALL SELECT 13, 'municipio', 'UFs distintas (cd_uf)',
             (SELECT COUNT(DISTINCT cd_uf)::text FROM municipio)
    UNION ALL SELECT 14, 'municipio', 'pares (nome, cd_uf) duplicados',
             (SELECT COUNT(*)::text FROM (
                SELECT nome_municipio, cd_uf FROM municipio
                 GROUP BY nome_municipio, cd_uf HAVING COUNT(*) > 1) s)
    UNION ALL SELECT 15, 'municipio', 'linhas por prefixo de UF (2 primeiros digitos)',
             (SELECT string_agg(t, ' | ' ORDER BY t) FROM (
                SELECT left(codigo_municipio_dv::text, 2) || ':' || COUNT(*)::text AS t
                  FROM municipio WHERE codigo_municipio_dv::text ~ '^[1-5][0-9]{6}$'
                 GROUP BY left(codigo_municipio_dv::text, 2)) s)

    -- ---- 3. As 9 linhas de EAD sem territorio ------------------------
    -- Elas NAO sao removidas por filtro de tp_dimensao: e preciso saber
    -- se carregam matricula (e portanto somem do mapa mas contam no total).
    UNION ALL SELECT 20, 'ead_9', 'linhas EAD-ofertado-no-Brasil sem territorio',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_cursos
               WHERE tp_dimensao = 'Cursos a distância ofertados no Brasil'
                 AND co_municipio !~ '^[0-9]+$')
    UNION ALL SELECT 21, 'ead_9', 'soma de qt_mat / qt_curso nessas linhas',
             (SELECT 'qt_mat=' || COALESCE(SUM(qt_mat), 0)::text
                  || ' | qt_curso=' || COALESCE(SUM(qt_curso), 0)::text
                FROM inep_educacao_superior_cursos
               WHERE tp_dimensao = 'Cursos a distância ofertados no Brasil'
                 AND co_municipio !~ '^[0-9]+$')
    UNION ALL SELECT 22, 'ead_9', 'cursos e IES envolvidos',
             (SELECT string_agg(DISTINCT co_ies::text || '/' || co_curso::text, ' | ')
                FROM inep_educacao_superior_cursos
               WHERE tp_dimensao = 'Cursos a distância ofertados no Brasil'
                 AND co_municipio !~ '^[0-9]+$')
    UNION ALL SELECT 23, 'ead_9', 'esses cursos tambem tem linha COM territorio?',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_cursos c
               WHERE c.co_municipio ~ '^[0-9]+$'
                 AND c.co_curso IN (
                     SELECT co_curso FROM inep_educacao_superior_cursos
                      WHERE tp_dimensao = 'Cursos a distância ofertados no Brasil'
                        AND co_municipio !~ '^[0-9]+$'))

    -- ---- 4. O recorte territorial continua batendo? ------------------
    UNION ALL SELECT 30, 'territorio', 'municipios distintos: sede de IES',
             (SELECT COUNT(DISTINCT co_municipio_ies)::text FROM inep_educacao_superior_ies)
    UNION ALL SELECT 31, 'territorio', 'municipios distintos: oferta de curso (validos)',
             (SELECT COUNT(DISTINCT co_municipio)::text FROM inep_educacao_superior_cursos
               WHERE co_municipio ~ '^[0-9]{7}$')
    UNION ALL SELECT 32, 'territorio', 'orfaos: sede de IES sem linha em municipio',
             (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT i.co_municipio_ies FROM inep_educacao_superior_ies i
                 WHERE NOT EXISTS (SELECT 1 FROM municipio m
                                    WHERE m.codigo_municipio_dv::text = i.co_municipio_ies)) s)
    UNION ALL SELECT 33, 'territorio', 'orfaos: oferta de curso sem linha em municipio',
             (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT c.co_municipio FROM inep_educacao_superior_cursos c
                 WHERE c.co_municipio ~ '^[0-9]{7}$'
                   AND NOT EXISTS (SELECT 1 FROM municipio m
                                    WHERE m.codigo_municipio_dv::text = c.co_municipio)) s)

) z ORDER BY ord;
