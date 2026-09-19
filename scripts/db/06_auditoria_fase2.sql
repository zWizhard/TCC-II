-- =====================================================================
-- 06_auditoria_fase2.sql — SOMENTE LEITURA. Nada aqui altera o banco.
--
-- FASE 2 — fecha as lacunas que a auditoria dos CSVs NAO consegue resolver.
-- Rodar no DBeaver como data_iesb e exportar cada bloco em CSV para
--   docs/data/raw/diagnostics/  (ver ADR-0005).
--
-- Por que estas consultas e nao outras: a auditoria local dos CSVs
-- (2026-09-05, Fase 2) ja provou nomes de coluna, grain, chaves,
-- cardinalidade, categorias e ausencia de vazios. O que o CSV NAO pode
-- provar e: (a) o tipo SQL real, (b) NULL de verdade vs string vazia,
-- (c) padding de CHAR, (d) privilegio nas tabelas auxiliares.
--
-- Custo: o bloco B faz poucas varreduras de inep_educacao_superior_cursos
-- (720.349 x 223, 609 MB, SEM indice). Medido antes: ~0,9-1,5 s por
-- agregacao. Nenhuma consulta usa SELECT *, e nenhuma faz COUNT(DISTINCT)
-- sobre as ~190 colunas de metrica.
-- =====================================================================


-- ---------------------------------------------------------------------
-- BLOCO A — inventario COMPLETO de colunas com o tipo SQL real.
--   Exportar como: 2026-09-05_06a_colunas_tipos.csv
--   305 linhas (82 de IES + 223 de cursos). Le so o catalogo: custo zero.
--
--   Fecha a lacuna: hoje so 12 das 305 colunas tem tipo confirmado no
--   banco; o resto foi INFERIDO do CSV, e a inferencia ja gerou
--   divergencia dentro do proprio DATA_DICTIONARY (co_municipio_ies
--   aparece como "int(7)" numa secao e como "character" noutra).
-- ---------------------------------------------------------------------
SELECT c.table_name               AS tabela,
       c.ordinal_position         AS pos,
       c.column_name              AS coluna,
       c.data_type                AS tipo,
       c.character_maximum_length AS tam_texto,
       c.numeric_precision        AS precisao,
       c.is_nullable              AS aceita_null
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name IN ('inep_educacao_superior_ies',
                       'inep_educacao_superior_cursos')
ORDER BY c.table_name, c.ordinal_position;


-- ---------------------------------------------------------------------
-- BLOCO B — verificacoes consolidadas num unico result set.
--   Exportar como: 2026-09-05_06b_verificacoes.csv
--
--   Tudo em (ord, bloco, verificacao, resultado) para caber em UMA
--   exportacao do DBeaver, no mesmo formato do script 05.
-- ---------------------------------------------------------------------
SELECT * FROM (

    -- ---- B1. NULL real vs string vazia -----------------------------
    -- O CSV nao distingue os dois: uma exportacao renderiza NULL como
    -- vazio. A auditoria local achou ZERO vazios nas 223 colunas de
    -- cursos, e em IES apenas sg_ies (459) e nu_cep_ies (26).
    -- Aqui confirmamos NULL de verdade nas colunas que o projeto usa.
      SELECT 1 AS ord, 'nulos_ies' AS bloco, 'co_ies NULL' AS verificacao,
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE co_ies IS NULL) AS resultado
    UNION ALL SELECT 2, 'nulos_ies', 'co_municipio_ies NULL',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE co_municipio_ies IS NULL)
    UNION ALL SELECT 3, 'nulos_ies', 'sg_ies NULL',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE sg_ies IS NULL)
    UNION ALL SELECT 4, 'nulos_ies', 'sg_ies string vazia',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE btrim(sg_ies) = '')
    UNION ALL SELECT 5, 'nulos_ies', 'nu_cep_ies NULL',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE nu_cep_ies IS NULL)
    UNION ALL SELECT 6, 'nulos_ies', 'nu_cep_ies string vazia',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE btrim(nu_cep_ies) = '')

    -- ---- B2. CHAR padding: bloqueia JOIN se existir -----------------
    -- co_municipio_ies e do tipo `character` (CHAR), que preenche com
    -- espacos a direita. No CSV o valor sai com 7 caracteres, mas isso
    -- pode ser o DBeaver aparando. Se length() > 7 aqui, TODO JOIN
    -- territorial precisa de btrim() — e sem ele retorna zero linhas
    -- em silencio, sem erro de execucao.
    UNION ALL SELECT 10, 'padding', 'comprimentos distintos de co_municipio_ies (bruto)',
             (SELECT string_agg(DISTINCT length(co_municipio_ies)::text, ',')
                FROM inep_educacao_superior_ies)
    UNION ALL SELECT 11, 'padding', 'comprimentos distintos de co_municipio_ies (btrim)',
             (SELECT string_agg(DISTINCT length(btrim(co_municipio_ies))::text, ',')
                FROM inep_educacao_superior_ies)
    UNION ALL SELECT 12, 'padding', 'comprimentos distintos de nu_ano_censo em IES (bruto)',
             (SELECT string_agg(DISTINCT length(nu_ano_censo)::text, ',')
                FROM inep_educacao_superior_ies)
    UNION ALL SELECT 13, 'padding', 'linhas de IES que casam com o literal 2024 sem btrim',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies WHERE nu_ano_censo = '2024')

    -- ---- B3. cursos: NULL nas colunas usadas (UMA varredura) --------
    -- COUNT(*) FILTER agrupa tudo num unico seq scan da tabela.
    UNION ALL SELECT 20, 'nulos_cursos', 'contagens de NULL (uma varredura)',
             (SELECT 'linhas=' || COUNT(*)
                  || ' | co_curso=' || COUNT(*) FILTER (WHERE co_curso IS NULL)
                  || ' | co_ies=' || COUNT(*) FILTER (WHERE co_ies IS NULL)
                  || ' | co_municipio=' || COUNT(*) FILTER (WHERE co_municipio IS NULL)
                  || ' | co_uf=' || COUNT(*) FILTER (WHERE co_uf IS NULL)
                  || ' | co_regiao=' || COUNT(*) FILTER (WHERE co_regiao IS NULL)
                  || ' | tp_dimensao=' || COUNT(*) FILTER (WHERE tp_dimensao IS NULL)
                  || ' | qt_curso=' || COUNT(*) FILTER (WHERE qt_curso IS NULL)
                  || ' | qt_mat=' || COUNT(*) FILTER (WHERE qt_mat IS NULL)
                  || ' | co_cine_area_geral=' || COUNT(*) FILTER (WHERE co_cine_area_geral IS NULL)
                FROM inep_educacao_superior_cursos)

    -- ---- B4. contaminacao territorial confirmada NO BANCO -----------
    -- Achado novo da Fase 2: o literal 'Cursos a distancia' aparece nao
    -- so em co_municipio (ja documentado) mas em TODA a hierarquia
    -- territorial — no_regiao, co_regiao, no_uf, sg_uf, co_uf,
    -- no_municipio, co_municipio e in_capital — 11.778 linhas em CADA.
    -- Confirmar no banco antes de reescrever o dicionario.
    UNION ALL SELECT 30, 'contaminacao', 'linhas nao numericas por coluna territorial',
             (SELECT 'co_municipio=' || COUNT(*) FILTER (WHERE co_municipio !~ '^[0-9]+$')
                  || ' | co_uf=' || COUNT(*) FILTER (WHERE co_uf !~ '^[0-9]+$')
                  || ' | co_regiao=' || COUNT(*) FILTER (WHERE co_regiao !~ '^[0-9]+$')
                  || ' | in_capital fora de Sim/Nao=' || COUNT(*) FILTER (WHERE in_capital NOT IN ('Sim', 'Não'))
                FROM inep_educacao_superior_cursos)
    UNION ALL SELECT 31, 'contaminacao', 'valores distintos nao numericos de co_uf',
             (SELECT string_agg(DISTINCT co_uf, ' | ')
                FROM inep_educacao_superior_cursos WHERE co_uf !~ '^[0-9]+$')

    -- ---- B5. grain: a chave de 4 partes e realmente unica? ----------
    -- Provado no CSV: distinct(ano, co_curso, co_municipio, tp_dimensao)
    -- = 720.349 = COUNT(*). Se o banco confirmar, cursos TEM chave
    -- natural e a Fase 3 pode assumi-la com seguranca.
    UNION ALL SELECT 40, 'grain', 'COUNT(*) cursos',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_cursos)
    UNION ALL SELECT 41, 'grain', 'distinct (ano, co_curso, co_municipio, tp_dimensao)',
             (SELECT COUNT(*)::text FROM (
                SELECT DISTINCT nu_ano_censo, co_curso, co_municipio, tp_dimensao
                  FROM inep_educacao_superior_cursos) s)
    UNION ALL SELECT 42, 'grain', 'co_curso que aparecem com mais de um co_ies',
             (SELECT COUNT(*)::text FROM (
                SELECT co_curso FROM inep_educacao_superior_cursos
                 GROUP BY co_curso HAVING COUNT(DISTINCT co_ies) > 1) s)

    -- ---- B6. ds_rede: a ponte entre as duas codificacoes ------------
    -- Achado novo da Fase 2: IES tem a coluna ds_rede com os rotulos
    -- 'Publica'/'Privada' — os MESMOS de cursos.tp_rede. Se confirmado,
    -- resolve a incompatibilidade tp_rede codigo x rotulo sem traducao
    -- manual. Cuidado: 'Publica' inclui as 28 IES de categoria Especial.
    UNION ALL SELECT 50, 'ds_rede', 'pares (tp_rede, ds_rede) em IES',
             (SELECT string_agg(t, ' | ' ORDER BY t) FROM (
                SELECT tp_rede::text || '=' || ds_rede || ':' || COUNT(*)::text AS t
                  FROM inep_educacao_superior_ies GROUP BY tp_rede, ds_rede) s)
    UNION ALL SELECT 51, 'ds_rede', 'rotulos distintos de cursos.tp_rede',
             (SELECT string_agg(DISTINCT tp_rede, ' | ') FROM inep_educacao_superior_cursos)

    -- ---- B7. meso/microrregiao: o codigo e nacional ou por UF? ------
    -- Achado novo da Fase 2: co_mesorregiao_ies tem so 15 valores
    -- distintos para 131 nomes, e co_microrregiao_ies 65 para 382 nomes.
    -- Se o codigo for local a UF, agrupar por ele sozinho FUNDE
    -- mesorregioes de estados diferentes e produz numero errado sem
    -- nenhum erro de execucao. Se (co_uf, co_meso) der 131, esta provado.
    UNION ALL SELECT 60, 'mesorregiao', 'distintos: co_meso / no_meso / (uf, co_meso)',
             (SELECT (SELECT COUNT(DISTINCT co_mesorregiao_ies)::text FROM inep_educacao_superior_ies)
                  || ' / ' || (SELECT COUNT(DISTINCT no_mesorregiao_ies)::text FROM inep_educacao_superior_ies)
                  || ' / ' || (SELECT COUNT(*)::text FROM (
                        SELECT DISTINCT co_uf_ies, co_mesorregiao_ies FROM inep_educacao_superior_ies) s))
    UNION ALL SELECT 61, 'mesorregiao', 'distintos: co_micro / no_micro / (uf, co_micro)',
             (SELECT (SELECT COUNT(DISTINCT co_microrregiao_ies)::text FROM inep_educacao_superior_ies)
                  || ' / ' || (SELECT COUNT(DISTINCT no_microrregiao_ies)::text FROM inep_educacao_superior_ies)
                  || ' / ' || (SELECT COUNT(*)::text FROM (
                        SELECT DISTINCT co_uf_ies, co_microrregiao_ies FROM inep_educacao_superior_ies) s))

    -- ---- B8. qt_doc_total x qt_doc_exe ------------------------------
    -- No CSV as duas colunas sao IDENTICAS nas 2.561 linhas (soma
    -- 374.501 em ambas). Se o banco confirmar, uma delas e redundante e
    -- o dicionario deve dizer qual usar, para ninguem somar as duas.
    UNION ALL SELECT 70, 'docentes', 'linhas onde qt_doc_total <> qt_doc_exe',
             (SELECT COUNT(*)::text FROM inep_educacao_superior_ies
               WHERE qt_doc_total IS DISTINCT FROM qt_doc_exe)

    -- ---- B9. privilegio nas auxiliares (uma linha por tabela) -------
    -- ENVIRONMENT.md afirma SELECT=true em oito auxiliares, mas a
    -- evidencia versionada so mostra a checagem das duas do Censo.
    UNION ALL SELECT 80, 'privilegio', 'SELECT nas auxiliares',
             (SELECT string_agg(t.n || '=' || has_table_privilege('public.' || quote_ident(t.n), 'SELECT')::text, ' | ')
                FROM (VALUES ('municipio'), ('ibge_populacao_estimada'), ('pib_municipios'),
                             ('ibge_munic_2024'), ('ibge_densidade_populacional_area_municipios_2010'),
                             ('regiao'), ('unidade_federacao'),
                             ('IBGE_agregados_por_municipio_basico')) AS t(n))
    UNION ALL SELECT 81, 'privilegio', 'escrita continua bloqueada nas duas do Censo',
             (SELECT string_agg(p.t || ':' || p.a || '=' ||
                        has_table_privilege('public.' || p.t, p.a)::text, ' | ')
                FROM (VALUES ('inep_educacao_superior_ies', 'INSERT'),
                             ('inep_educacao_superior_ies', 'UPDATE'),
                             ('inep_educacao_superior_ies', 'DELETE'),
                             ('inep_educacao_superior_cursos', 'INSERT'),
                             ('inep_educacao_superior_cursos', 'UPDATE'),
                             ('inep_educacao_superior_cursos', 'DELETE')) AS p(t, a))

    -- ---- B10. pendencias abertas do DATA_DICTIONARY ------------------
    UNION ALL SELECT 90, 'pendencia', 'municipio: linhas / codigos distintos',
             (SELECT (SELECT COUNT(*)::text FROM municipio) || ' / '
                  || (SELECT COUNT(DISTINCT codigo_municipio_dv)::text FROM municipio))
    UNION ALL SELECT 91, 'pendencia', 'municipio: latitudes fora do envelope do Brasil',
             (SELECT COALESCE(string_agg(nome_municipio || '(' || codigo_municipio_dv || '): '
                        || latitude::text || ',' || longitude::text, ' | '), 'nenhuma')
                FROM municipio WHERE latitude > 5.3 OR latitude < -33.8)
    UNION ALL SELECT 92, 'pendencia', 'municipio: longitudes fora do envelope',
             (SELECT COALESCE(string_agg(nome_municipio || '(' || codigo_municipio_dv || '): '
                        || latitude::text || ',' || longitude::text, ' | '), 'nenhuma')
                FROM municipio WHERE longitude > -28.8 OR longitude < -74.0)
    UNION ALL SELECT 93, 'pendencia', 'municipio: codigos que NAO parecem IBGE de 7 digitos',
             (SELECT COUNT(*)::text FROM municipio
               WHERE codigo_municipio_dv::text !~ '^[1-5][0-9]{6}$')
    UNION ALL SELECT 94, 'pendencia', 'ibge_populacao_estimada: duplicata por (ano, municipio)?',
             (SELECT (SELECT COUNT(*)::text FROM ibge_populacao_estimada) || ' linhas / '
                  || (SELECT COUNT(*)::text FROM (
                        SELECT DISTINCT ano, cod_municipio FROM ibge_populacao_estimada) s)
                  || ' pares distintos')
    UNION ALL SELECT 95, 'pendencia', 'pib_municipios / densidade: digitos do codigo',
             (SELECT 'pib=' || (SELECT string_agg(DISTINCT length(codigo_municipio_dv::text)::text, ',')
                                  FROM pib_municipios)
                  || ' | densidade=' || (SELECT string_agg(DISTINCT length(codigo_municipio_dv::text)::text, ',')
                                  FROM ibge_densidade_populacional_area_municipios_2010))

) z ORDER BY ord;
