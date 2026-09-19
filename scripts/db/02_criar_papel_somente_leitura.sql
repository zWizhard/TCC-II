-- =====================================================================
-- 02_criar_papel_somente_leitura.sql
--
-- >>> ESTE SCRIPT ALTERA O BANCO. NAO EXECUTE NO AUTOMATICO. <<<
--
-- Rodar SOMENTE se 01_diagnostico.sql mostrar:
--   - consulta 2: pode_criar_papel = true
--   - consulta 4: is_grantable = YES para SELECT nas duas tabelas
--                 (ou a conta atual e dona das tabelas, consulta 3)
--
-- Se qualquer uma falhar, PARE: a opcao 2 nao e viavel com esta conta.
-- Nesse caso, solicitar o papel ao IESB ou seguir para a opcao 3
-- (allowlist + validacao AST + timeout apenas na aplicacao, com a
-- limitacao declarada explicitamente no TCC).
--
-- CONTEXTO: este e um banco academico COMPARTILHADO. Criar um papel
-- afeta o servidor inteiro, nao so este projeto. Confirme com o
-- responsavel pelo ambiente antes de executar.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0) TROQUE A SENHA ABAIXO antes de executar.
--    Use uma senha forte e diferente da senha de data_iesb.
--    Depois de criar, guarde-a apenas no arquivo .env local (nao versionado).
-- ---------------------------------------------------------------------

BEGIN;

-- 1) Papel de aplicacao, apenas login. Sem CREATEDB, sem CREATEROLE.
CREATE ROLE observatorio_ro WITH LOGIN PASSWORD 'TROQUE_ESTA_SENHA'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

-- 2) DEFESA PRINCIPAL: toda transacao deste papel nasce somente-leitura.
--    Vale mesmo que algum GRANT de escrita escape por engano, e cobre
--    inclusive o schema public aberto do PostgreSQL < 15.
ALTER ROLE observatorio_ro SET default_transaction_read_only = on;

-- 3) Timeout imposto pelo servidor, nao so pela aplicacao.
ALTER ROLE observatorio_ro SET statement_timeout = '60s';
ALTER ROLE observatorio_ro SET idle_in_transaction_session_timeout = '60s';

-- 4) Acesso minimo: conectar, enxergar o schema, ler as duas tabelas.
GRANT CONNECT ON DATABASE iesb TO observatorio_ro;
GRANT USAGE   ON SCHEMA public TO observatorio_ro;

GRANT SELECT ON TABLE public.inep_educacao_superior_ies    TO observatorio_ro;
GRANT SELECT ON TABLE public.inep_educacao_superior_cursos TO observatorio_ro;

COMMIT;


-- =====================================================================
-- VERIFICACAO — rodar depois do COMMIT
-- =====================================================================

-- Confere as travas aplicadas ao papel
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolconfig
FROM pg_roles
WHERE rolname = 'observatorio_ro';
-- rolconfig deve conter default_transaction_read_only=on e statement_timeout=60s

-- Confere que o papel so tem SELECT
SELECT table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'observatorio_ro'
ORDER BY table_name, privilege_type;
-- Esperado: apenas SELECT nas duas tabelas


-- =====================================================================
-- TESTE DE INVASAO — reconectar COMO observatorio_ro e rodar isto.
-- As tres primeiras DEVEM falhar. Se alguma passar, o papel nao esta seguro.
-- =====================================================================
-- CREATE TABLE teste_escrita (id int);
--   esperado: ERROR: cannot execute CREATE TABLE in a read-only transaction
--
-- DELETE FROM inep_educacao_superior_ies WHERE false;
--   esperado: ERROR: cannot execute DELETE in a read-only transaction
--
-- UPDATE inep_educacao_superior_ies SET no_ies = no_ies WHERE false;
--   esperado: ERROR: cannot execute UPDATE in a read-only transaction
--
-- SELECT COUNT(*) FROM inep_educacao_superior_ies;
--   esperado: 2561  (esta DEVE funcionar)


-- =====================================================================
-- DESFAZER, se necessario
-- =====================================================================
-- REVOKE ALL ON TABLE public.inep_educacao_superior_ies, public.inep_educacao_superior_cursos FROM observatorio_ro;
-- REVOKE ALL ON SCHEMA public FROM observatorio_ro;
-- REVOKE ALL ON DATABASE iesb FROM observatorio_ro;
-- DROP ROLE observatorio_ro;
