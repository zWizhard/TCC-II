-- =====================================================================
-- 01_diagnostico.sql — SOMENTE LEITURA. Nada aqui altera o banco.
-- Rodar no DBeaver, conectado como data_iesb, e enviar a saida ao agente.
--
-- Objetivo: descobrir se a "opcao 2" (criar um papel somente-leitura com
-- a propria conta) e viavel, e confirmar schema/tipos reais das tabelas.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Versao do servidor
--    Importa porque em PostgreSQL < 15 qualquer usuario pode criar
--    objetos no schema public por padrao.
-- ---------------------------------------------------------------------
SELECT version() AS versao, current_database() AS banco, current_user AS usuario;


-- ---------------------------------------------------------------------
-- 2) Privilegios da conta atual  <<< DECIDE SE A OPCAO 2 E POSSIVEL
--    rolcreaterole = TRUE e o requisito para criar o papel de leitura.
--    Atencao: poder criar TABELAS (DDL) nao implica poder criar PAPEIS.
-- ---------------------------------------------------------------------
SELECT rolname,
       rolsuper      AS superusuario,
       rolcreaterole AS pode_criar_papel,   -- <<< precisa ser true
       rolcreatedb   AS pode_criar_banco,
       rolcanlogin   AS pode_logar
FROM pg_roles
WHERE rolname = current_user;


-- ---------------------------------------------------------------------
-- 3) Onde estao as tabelas do Censo, e quem e o dono
--    Se o dono NAO for data_iesb, a conta so consegue conceder SELECT
--    a terceiros se tiver GRANT OPTION (ver consulta 4).
-- ---------------------------------------------------------------------
SELECT schemaname   AS schema,
       tablename    AS tabela,
       tableowner   AS dono
FROM pg_tables
WHERE tablename ILIKE 'inep%'
   OR tablename ILIKE '%educacao_superior%'
ORDER BY schemaname, tablename;


-- ---------------------------------------------------------------------
-- 4) A conta pode repassar SELECT dessas tabelas a outro papel?
--    is_grantable = YES e o que permite o GRANT do script 02.
-- ---------------------------------------------------------------------
SELECT table_schema, table_name, privilege_type, is_grantable
FROM information_schema.table_privileges
WHERE grantee = current_user
  AND table_name IN ('inep_educacao_superior_ies', 'inep_educacao_superior_cursos')
ORDER BY table_name, privilege_type;


-- ---------------------------------------------------------------------
-- 5) Tipos reais das colunas-chave
--    Critico: se co_municipio for text e a malha IBGE vier como integer
--    (ou vice-versa), o JOIN territorial retorna vazio em silencio.
-- ---------------------------------------------------------------------
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name IN ('inep_educacao_superior_ies', 'inep_educacao_superior_cursos')
  AND column_name IN ('nu_ano_censo', 'co_ies', 'co_curso',
                      'co_municipio', 'co_municipio_ies',
                      'tp_rede', 'tp_dimensao', 'qt_curso', 'qt_mat')
ORDER BY table_name, column_name;


-- ---------------------------------------------------------------------
-- 6) Indices existentes — definem se filtro por municipio/ano sera rapido
-- ---------------------------------------------------------------------
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('inep_educacao_superior_ies', 'inep_educacao_superior_cursos')
ORDER BY tablename, indexname;


-- ---------------------------------------------------------------------
-- 7) Conferencia contra os CSVs ja auditados
--    Esperado: ies = 2.561 linhas / cursos = 720.349 linhas / ano = 2024.
--    Divergencia significa que o CSV e um recorte, nao a tabela inteira.
-- ---------------------------------------------------------------------
SELECT 'ies' AS tabela, nu_ano_censo, COUNT(*) AS linhas
FROM inep_educacao_superior_ies
GROUP BY nu_ano_censo
UNION ALL
SELECT 'cursos', nu_ano_censo, COUNT(*)
FROM inep_educacao_superior_cursos
GROUP BY nu_ano_censo
ORDER BY tabela, nu_ano_censo;


-- ---------------------------------------------------------------------
-- 8) Somas de controle — devem bater com a auditoria dos CSVs
--    Esperado: qt_curso = 45.776 e qt_mat = 10.227.266.
-- ---------------------------------------------------------------------
SELECT SUM(qt_curso) AS soma_qt_curso,   -- esperado 45776
       SUM(qt_mat)   AS soma_qt_mat,     -- esperado 10227266
       COUNT(DISTINCT co_curso) AS cursos_distintos  -- esperado 46150
FROM inep_educacao_superior_cursos;


-- ---------------------------------------------------------------------
-- 9) Outras tabelas disponiveis no banco (pode haver malha municipal,
--    IDH, populacao etc. que evitem baixar dados externos)
-- ---------------------------------------------------------------------
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename;
