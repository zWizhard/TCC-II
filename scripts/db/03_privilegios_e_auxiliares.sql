-- =====================================================================
-- 03_privilegios_e_auxiliares.sql — SOMENTE LEITURA. Nada altera o banco.
--
-- Motivo: o DBeaver concatenou os resultados do script 01 num CSV unico,
-- misturando result sets de larguras diferentes. Aqui cada bloco devolve
-- UM result set com colunas rotuladas, sem ambiguidade de alinhamento.
--
-- Exportar cada aba separadamente, ou colar o texto da saida.
-- =====================================================================

-- ---------------------------------------------------------------------
-- BLOCO A — a conta pode escrever? (decide a estrategia de seguranca)
-- Usa has_*_privilege, que considera TODOS os caminhos: concessao direta,
-- PUBLIC e heranca de papel. information_schema mostra so o direto.
-- ---------------------------------------------------------------------
SELECT 'versao_servidor'          AS verificacao, version()                                                          AS resultado
UNION ALL SELECT 'usuario',        current_user
UNION ALL SELECT 'e_superusuario', (SELECT rolsuper::text      FROM pg_roles WHERE rolname = current_user)
UNION ALL SELECT 'pode_criar_papel',(SELECT rolcreaterole::text FROM pg_roles WHERE rolname = current_user)
UNION ALL SELECT 'pode_criar_banco',(SELECT rolcreatedb::text   FROM pg_roles WHERE rolname = current_user)
UNION ALL SELECT 'CREATE no banco',   has_database_privilege(current_user, current_database(), 'CREATE')::text
UNION ALL SELECT 'CREATE no schema public', has_schema_privilege(current_user, 'public', 'CREATE')::text
UNION ALL SELECT 'ies: SELECT',  has_table_privilege(current_user, 'public.inep_educacao_superior_ies', 'SELECT')::text
UNION ALL SELECT 'ies: INSERT',  has_table_privilege(current_user, 'public.inep_educacao_superior_ies', 'INSERT')::text
UNION ALL SELECT 'ies: UPDATE',  has_table_privilege(current_user, 'public.inep_educacao_superior_ies', 'UPDATE')::text
UNION ALL SELECT 'ies: DELETE',  has_table_privilege(current_user, 'public.inep_educacao_superior_ies', 'DELETE')::text
UNION ALL SELECT 'cursos: SELECT', has_table_privilege(current_user, 'public.inep_educacao_superior_cursos', 'SELECT')::text
UNION ALL SELECT 'cursos: INSERT', has_table_privilege(current_user, 'public.inep_educacao_superior_cursos', 'INSERT')::text
UNION ALL SELECT 'cursos: UPDATE', has_table_privilege(current_user, 'public.inep_educacao_superior_cursos', 'UPDATE')::text
UNION ALL SELECT 'cursos: DELETE', has_table_privilege(current_user, 'public.inep_educacao_superior_cursos', 'DELETE')::text;


-- ---------------------------------------------------------------------
-- BLOCO B — a aplicacao consegue se auto-travar em somente-leitura?
-- Qualquer papel pode aplicar isto a propria sessao, sem CREATEROLE.
-- Esperado: 'on', e a linha seguinte deve FALHAR com
--   ERROR: cannot execute CREATE TABLE in a read-only transaction
-- Rode as tres linhas juntas.
-- ---------------------------------------------------------------------
SET default_transaction_read_only = on;
SHOW default_transaction_read_only;
-- CREATE TABLE teste_trava (id int);   -- descomente: DEVE dar erro
RESET default_transaction_read_only;


-- ---------------------------------------------------------------------
-- BLOCO C — comprimento declarado das chaves textuais
-- co_municipio_ies e `character` (CHAR, preenchido com espacos a direita).
-- Se o tamanho for maior que 7, o valor carrega espacos e quebra
-- comparacao/concatenacao ingenua com a malha do IBGE.
-- ---------------------------------------------------------------------
SELECT table_name, column_name, data_type, character_maximum_length AS tamanho
FROM information_schema.columns
WHERE table_name IN ('inep_educacao_superior_ies', 'inep_educacao_superior_cursos')
  AND column_name IN ('co_municipio', 'co_municipio_ies', 'nu_ano_censo', 'tp_rede')
ORDER BY table_name, column_name;

-- Amostra crua, com delimitador visivel, para enxergar espacos a direita
SELECT DISTINCT '[' || co_municipio_ies || ']' AS valor_delimitado,
       length(co_municipio_ies)                AS comprimento
FROM inep_educacao_superior_ies
LIMIT 5;


-- ---------------------------------------------------------------------
-- BLOCO D — tabelas auxiliares que o banco JA oferece
-- Se houver malha/coordenadas e populacao municipal aqui, evita-se
-- baixar dado externo e garante-se consistencia de codigo IBGE.
-- ---------------------------------------------------------------------
SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_name IN ('municipio', 'regiao', 'unidade_federacao',
                       'ibge_populacao_estimada', 'ibge_munic_2024',
                       'IBGE_agregados_por_municipio_basico',
                       'ibge_densidade_populacional_area_municipios_2010',
                       'pib_municipios')
ORDER BY c.table_name, c.ordinal_position;


-- ---------------------------------------------------------------------
-- BLOCO E — a conta pode ler essas auxiliares?
-- ---------------------------------------------------------------------
SELECT tablename,
       has_table_privilege(current_user, 'public.' || quote_ident(tablename), 'SELECT') AS pode_ler
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('municipio', 'regiao', 'unidade_federacao',
                    'ibge_populacao_estimada', 'ibge_munic_2024',
                    'IBGE_agregados_por_municipio_basico',
                    'ibge_densidade_populacional_area_municipios_2010',
                    'pib_municipios')
ORDER BY tablename;
