"""Gerador de SQL e validador AST. O validador e atacado diretamente com SQL hostil."""

import re
from typing import Any

import pytest
from apoio_analista import (
    P_IES_BRASIL,
    P_UF_PRIVADA,
    PLANO_IES_BRASIL,
    dims,
    filtro,
    plano,
    plano_dict,
    plano_uf_privada,
)
from fastapi.testclient import TestClient

from api.analista.plano import TETO_LINHAS
from api.analista.sql import ConsultaGerada, gerar_sql
from api.analista.validacao import validar_plano
from api.analista.validador_sql import COLUNAS_PERMITIDAS, TABELAS_PERMITIDAS, validar_sql
from api.consultas import FiltrosConsulta, consultar_indicador
from api.db import BaseAnalitica
from api.erros import SqlRejeitado
from api.fluxo import consultar_razao
from api.indicadores import CATALOGO, RAZOES, Agrupamento, Dimensao, Nivel, Recorte, Rede
from api.semantica import CAMADA, recuperar_contexto

IES = "inep_educacao_superior_ies"
CURSOS = "inep_educacao_superior_cursos"
TODAS = ("presencial", "ead_polo", "ead_nacional", "ead_exterior")


def consulta(pergunta: str, **campos: Any) -> ConsultaGerada:
    return gerar_sql(validar_plano(plano(**campos), recuperar_contexto(pergunta)))


def motivo(sql: str, params: dict[str, Any] | None = None, teto: int = TETO_LINHAS) -> str:
    with pytest.raises(SqlRejeitado) as exc:
        validar_sql(sql, params or {}, teto)
    assert exc.value.status == 500
    # A mensagem publica e fixa: nao ecoa o SQL nem o detalhe tecnico.
    assert exc.value.mensagem == "A consulta gerada foi barrada pela validação de segurança."
    return exc.value.motivo


# --- gerador --------------------------------------------------------------------------------------


def test_sql_gerado_aplica_as_regras_de_dados() -> None:
    c = consulta(P_UF_PRIVADA, **plano_uf_privada())
    assert f"FROM {CURSOS}" in c.sql
    assert "nu_ano_censo = $ano" in c.sql and c.params["ano"] == "2024"  # ano como TEXTO
    assert "list_contains($oferta, tp_dimensao)" in c.sql
    assert c.params["oferta"] == ["Cursos presenciais ofertados no Brasil"]
    assert "regexp_full_match(co_municipio, '[0-9]{7}')" in c.sql  # territorio em cursos
    assert "list_contains($f0, tp_rede)" in c.sql and c.params["f0"] == ["Privada"]
    assert "SUM(qt_mat)" in c.sql and "GROUP BY sg_uf" in c.sql
    assert c.sql.rstrip().endswith("LIMIT $limite")
    assert c.params["limite"] == c.limite + 1  # a linha a mais so detecta truncamento
    assert [x.id for x in c.colunas] == ["uf_codigo", "uf", "matriculas"]
    validar_sql(c.sql, c.params, TETO_LINHAS + 1, c.entidade)


def test_valores_nunca_sao_concatenados_no_sql() -> None:
    """Rotulo de rede, UF, limiar, limite e codigo de municipio so existem nos parametros."""
    pergunta = "matrículas presenciais por UF com mais de 500000"
    c = consulta(
        pergunta,
        intent="distribuicao",
        dimensions=dims("oferta", "uf", "presencial"),
        having=[{"metrica": "matriculas", "operador": ">", "valor": 500000}],
    )
    assert "HAVING SUM(qt_mat) > $h0" in c.sql and c.params["h0"] == 500000
    assert "500000" not in c.sql and "presenciais" not in c.sql
    c = consulta(
        "matrículas presenciais no município 3550308",
        intent="distribuicao",
        dimensions=dims("oferta", "municipio", "presencial"),
        filters=[filtro("municipio", "3550308")],
    )
    assert "3550308" not in c.sql and c.params["f0"] == ["3550308"]
    # Os unicos literais do SQL sao os fragmentos fixos da camada (o padrao dos 7 digitos e o 0).
    assert set(re.findall(r"'[^']*'", c.sql)) == {"'[0-9]{7}'"}


def test_ies_usa_a_tabela_de_ies_e_a_ponte_de_rede() -> None:
    c = consulta(P_IES_BRASIL, **PLANO_IES_BRASIL)
    assert f"FROM {IES}" in c.sql and CURSOS not in c.sql
    assert "tp_dimensao" not in c.sql and "regexp_full_match" not in c.sql
    assert "COUNT(*)" in c.sql and "GROUP BY" not in c.sql
    c = consulta(
        "docentes por região na rede pública",
        intent="distribuicao",
        entity="ies",
        metrics=["docentes"],
        dimensions=dims("sede", "regiao"),
        filters=[filtro("rede", "publica")],
    )
    # Rede em IES e ds_rede (rotulo), nunca o tp_rede cru.
    assert "list_contains($f0, ds_rede)" in c.sql and "tp_rede" not in c.sql
    assert c.params["f0"] == ["Pública"]
    assert "SUM(qt_doc_total)" in c.sql and "JOIN" not in c.sql


def test_sem_territorio_nao_ha_filtro_de_7_digitos() -> None:
    c = consulta("matrículas presenciais no Brasil", **plano_dict())
    assert "regexp_full_match" not in c.sql
    c = consulta(
        "matrículas presenciais nas capitais", **plano_dict(filters=[filtro("capital", "sim")])
    )
    assert "regexp_full_match(co_municipio, '[0-9]{7}')" in c.sql  # filtro territorial


def test_todo_sql_gerado_passa_no_validador_e_so_usa_a_allowlist() -> None:
    casos: list[tuple[str, dict[str, Any]]] = [
        (P_UF_PRIVADA, plano_uf_privada()),
        (P_IES_BRASIL, PLANO_IES_BRASIL),
        (
            "matrículas por modalidade",
            plano_dict(
                intent="distribuicao",
                dimensions=dims("oferta", "brasil", *TODAS),
                group_by=["dimensao"],
            ),
        ),
        (
            "UF com menores inscrições por vaga presenciais",
            plano_dict(
                intent="ranking",
                metrics=["inscricoes_por_vaga"],
                dimensions=dims("oferta", "uf", "presencial"),
                order_by=[{"por": "inscricoes_por_vaga", "direcao": "asc"}],
            ),
        ),
        (
            "matrículas presenciais por região e por grau",
            plano_dict(
                intent="distribuicao",
                dimensions=dims("oferta", "regiao", "presencial"),
                group_by=["grau"],
            ),
        ),
    ]
    for pergunta, dados in casos:
        c = consulta(pergunta, **dados)
        validar_sql(c.sql, c.params, TETO_LINHAS + 1, c.entidade)
        assert c.sql.count(";") == 0 and "--" not in c.sql


def test_allowlists_vem_da_camada() -> None:
    assert {IES, CURSOS, "municipio", "ibge_populacao_estimada"} == TABELAS_PERMITIDAS
    assert {"qt_mat", "sg_uf", "co_municipio", "ds_rede"} <= COLUNAS_PERMITIDAS
    # Coluna classificada como proibida/irrelevante na camada nao e consultavel.
    fora = {c.nome for c in CAMADA.colunas} - COLUNAS_PERMITIDAS
    assert "no_municipio" in fora


# --- validador AST: SQL hostil --------------------------------------------------------------------

HOSTIS: list[tuple[str, str]] = [
    (f"DROP TABLE {IES}", "comando_proibido"),
    (f"DELETE FROM {IES}", "comando_proibido"),
    (f"DELETE FROM {IES} WHERE 1 = 1 RETURNING *", "comando_proibido"),
    (f"UPDATE {IES} SET qt_doc_total = 0", "comando_proibido"),
    (f"INSERT INTO {IES} SELECT * FROM {IES}", "comando_proibido"),
    (f"ALTER TABLE {IES} ADD COLUMN x INT", "comando_proibido"),
    (f"TRUNCATE TABLE {IES}", "comando_proibido"),
    ("CREATE TABLE t AS SELECT 1", "comando_proibido"),
    # O motor NAO barra tabela temporaria em modo read-only: e o validador que barra.
    (f"CREATE TEMP TABLE t AS SELECT * FROM {IES}", "comando_proibido"),
    (f"CREATE VIEW v AS SELECT * FROM {IES}", "comando_proibido"),
    (f"GRANT SELECT ON {IES} TO PUBLIC", "comando_proibido"),
    (f"REVOKE SELECT ON {IES} FROM PUBLIC", "comando_proibido"),
    ("ATTACH 'outro.duckdb' AS outro", "comando_proibido"),
    (f"COPY {IES} TO 'saida.csv'", "comando_proibido"),
    (f"COPY (SELECT * FROM {IES}) TO 'saida.csv'", "comando_proibido"),
    ("PRAGMA database_list", "comando_proibido"),
    ("SET memory_limit = '64GB'", "comando_proibido"),
    ("SET enable_external_access = true", "comando_proibido"),
    ("INSTALL httpfs", "comando_proibido"),
    ("LOAD httpfs", "comando_proibido"),
    ("CALL pragma_version()", "comando_proibido"),
    ("EXECUTE consulta", "comando_proibido"),
    ("USE memory", "comando_proibido"),
    ("BEGIN TRANSACTION", "comando_proibido"),
    (f"SELECT co_ies INTO t FROM {IES} LIMIT 1", "comando_proibido"),
    (
        f"MERGE INTO {IES} a USING {IES} b ON a.co_ies = b.co_ies WHEN MATCHED THEN DELETE",
        "comando_proibido",
    ),
    (f"DESCRIBE {IES}", "comando_proibido"),
    ("SHOW TABLES", "comando_proibido"),
    (f"SUMMARIZE {IES}", "comando_proibido"),
    # Mais de um statement, inclusive com o segundo "escondido".
    (f"SELECT co_ies FROM {IES} LIMIT 1; DROP TABLE {IES}", "multiplos_statements"),
    (f"SELECT co_ies FROM {IES} LIMIT 1; SELECT co_ies FROM {IES} LIMIT 1", "multiplos_statements"),
    ("", "multiplos_statements"),
    (";", "multiplos_statements"),
    # Comentario, com ou sem statement dentro.
    (f"SELECT co_ies FROM {IES} /* ; DROP TABLE {IES} */ LIMIT 1", "comentario"),
    (f"SELECT co_ies FROM {IES} LIMIT 1 -- ; DROP TABLE {IES}", "comentario"),
    (f"SELECT co_ies FROM {IES} --\nLIMIT 1", "comentario"),
    (f"/* inofensivo */ SELECT co_ies FROM {IES} LIMIT 1", "comentario"),
    # Tabela fora da allowlist: direta, em subquery, em CTE e em JOIN.
    ("SELECT co_ies FROM segredos LIMIT 1", "tabela_fora_da_allowlist"),
    ("SELECT co_ies FROM (SELECT co_ies FROM segredos) AS s LIMIT 1", "tabela_fora_da_allowlist"),
    (
        "WITH x AS (SELECT co_ies FROM segredos) SELECT co_ies FROM x LIMIT 1",
        "tabela_fora_da_allowlist",
    ),
    (
        f"SELECT a.co_ies FROM {IES} a JOIN segredos s ON a.co_ies = s.co_ies LIMIT 1",
        "tabela_fora_da_allowlist",
    ),
    (
        f"SELECT co_ies FROM {IES} WHERE co_ies IN (SELECT co_ies FROM segredos) LIMIT 1",
        "tabela_fora_da_allowlist",
    ),
    ("SELECT co_ies FROM 'arquivo.parquet' LIMIT 1", "tabela_fora_da_allowlist"),
    ("SELECT co_ies FROM sqlite_master LIMIT 1", "tabela_fora_da_allowlist"),
    # Schema ou catalogo qualificado, mesmo apontando para tabela permitida.
    ("SELECT table_name FROM information_schema.tables LIMIT 1", "tabela_qualificada"),
    (f"SELECT co_ies FROM main.{IES} LIMIT 1", "tabela_qualificada"),
    (f"SELECT co_ies FROM outro.main.{IES} LIMIT 1", "tabela_qualificada"),
    ("SELECT name FROM pg_catalog.pg_tables LIMIT 1", "tabela_qualificada"),
    # Funcao de tabela e leitura de arquivo.
    ("SELECT co_ies FROM read_csv('C:/Users/x/.env') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM read_csv_auto('x.csv') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM read_parquet('x.parquet') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM read_json('x.json') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM read_text('x.txt') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM glob('*') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM duckdb_tables() LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM duckdb_settings() LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM pragma_table_info('x') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM query('SELECT 1') LIMIT 1", "funcao_de_tabela"),
    (f"SELECT co_ies FROM query_table('{IES}') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM sqlite_scan('x.db', 't') LIMIT 1", "funcao_de_tabela"),
    ("SELECT co_ies FROM range(1000000000) LIMIT 1", "funcao_de_tabela"),
    # Funcao fora da allowlist em posicao escalar.
    (f"SELECT getenv('PGPASSWORD') AS co_ies FROM {IES} LIMIT 1", "funcao_nao_permitida"),
    (
        f"SELECT current_setting('memory_limit') AS co_ies FROM {IES} LIMIT 1",
        "funcao_nao_permitida",
    ),
    (f"SELECT version() AS co_ies FROM {IES} LIMIT 1", "funcao_nao_permitida"),
    (f"SELECT repeat(co_ies, 1000000) AS co_ies FROM {IES} LIMIT 1", "funcao_nao_permitida"),
    (f"SELECT md5(co_ies) AS co_ies FROM {IES} LIMIT 1", "funcao_nao_permitida"),
    # Construcao fora da allowlist.
    (f"SELECT co_ies FROM {IES} UNION ALL SELECT co_ies FROM {IES} LIMIT 1", "nao_e_select"),
    (f"SELECT co_ies FROM {IES} LIMIT 1 OFFSET 10", "construcao_nao_permitida"),
    (f"SELECT ROW_NUMBER() OVER () AS co_ies FROM {IES} LIMIT 1", "funcao_nao_permitida"),
    (
        f"WITH RECURSIVE r AS (SELECT co_ies FROM {IES}) SELECT co_ies FROM r LIMIT 1",
        "tabela_fora_da_allowlist",
    ),
    # Coluna fora da camada e SELECT *.
    (f"SELECT senha FROM {IES} LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT * FROM {IES} LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT a.* FROM {IES} a LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT no_municipio FROM {CURSOS} LIMIT 1", "coluna_nao_permitida"),
    # LIMIT ausente, acima do teto ou que nao e inteiro.
    (f"SELECT co_ies FROM {IES}", "sem_limit"),
    (f"SELECT co_ies FROM (SELECT co_ies FROM {IES} LIMIT 1) AS s", "construcao_nao_permitida"),
    (f"SELECT co_ies FROM {IES} LIMIT {TETO_LINHAS + 1}", "limit_invalido"),
    (f"SELECT co_ies FROM {IES} LIMIT 999999999", "limit_invalido"),
    (f"SELECT co_ies FROM {IES} LIMIT 0", "limit_invalido"),
    (f"SELECT co_ies FROM {IES} LIMIT ALL", "limit_invalido"),
    # Parametro sem valor vinculado.
    (f"SELECT co_ies FROM {IES} WHERE nu_ano_censo = $ano LIMIT 1", "parametro_sem_valor"),
    (f"SELECT co_ies FROM {IES} WHERE nu_ano_censo = ? LIMIT 1", "parametro_sem_valor"),
    # Parse falho.
    ("SELECT co_ies FROM WHERE LIMIT", "parse_falhou"),
    (f"SELECT co_ies FROM {IES} WHERE (", "parse_falhou"),
    ("isto não é SQL", "parse_falhou"),
]


@pytest.mark.parametrize(("sql", "esperado"), HOSTIS, ids=[s[:60] or "(vazio)" for s, _ in HOSTIS])
def test_validador_ast_rejeita_sql_hostil(sql: str, esperado: str) -> None:
    obtido = motivo(sql)
    # O que importa e a rejeicao; o motivo confere que a regra certa disparou. Alguns ataques
    # violam mais de uma regra e a primeira a disparar depende da forma como o SQLGlot os le.
    equivalentes = {
        "parse_falhou": {
            "parse_falhou",
            "comando_proibido",
            "nao_e_select",
            "construcao_nao_permitida",
        },
        "limit_invalido": {"limit_invalido", "sem_limit", "construcao_nao_permitida"},
        "construcao_nao_permitida": {"construcao_nao_permitida", "funcao_nao_permitida"},
        "funcao_nao_permitida": {"construcao_nao_permitida", "funcao_nao_permitida"},
        "funcao_de_tabela": {
            "funcao_de_tabela",
            "funcao_nao_permitida",
            "construcao_nao_permitida",
        },
        "multiplos_statements": {"multiplos_statements", "parse_falhou"},
        "coluna_nao_permitida": {"coluna_nao_permitida", "construcao_nao_permitida"},
    }
    assert obtido in equivalentes.get(esperado, {esperado}), obtido


def test_validador_ast_so_aceita_a_forma_que_o_gerador_emite() -> None:
    validar_sql(f"SELECT co_ies FROM {IES} LIMIT 10", {}, TETO_LINHAS)
    validar_sql(f"SELECT co_ies FROM {IES} LIMIT $n", {"n": TETO_LINHAS}, TETO_LINHAS)
    validar_sql(
        f"SELECT sg_uf AS sigla, SUM(qt_mat) AS total FROM {CURSOS} WHERE nu_ano_censo = $ano "
        "GROUP BY sg_uf HAVING SUM(qt_mat) > $h ORDER BY total DESC, sigla ASC LIMIT 5",
        {"ano": "2024", "h": 1},
        TETO_LINHAS,
        "cursos",
    )
    # CTE, subconsulta, JOIN e alias de tabela NAO fazem parte da forma aceita, mesmo so com
    # tabelas e colunas permitidas: o gerador nao os usa.
    for sql in (
        f"SELECT sg_uf FROM (SELECT sg_uf FROM {CURSOS}) AS s LIMIT 5",
        f"SELECT sg_uf FROM {CURSOS} AS c LIMIT 5",
        f"SELECT co_ies FROM {IES} WHERE co_ies = (SELECT co_ies FROM {IES} LIMIT 1) LIMIT 1",
        f"SELECT co_ies FROM {IES} WHERE co_ies IN (SELECT co_ies FROM {IES}) LIMIT 1",
        f"SELECT co_ies FROM {IES} WHERE EXISTS (SELECT co_ies FROM {IES}) LIMIT 1",
        f"SELECT co_ies FROM {IES} WHERE co_ies = '1' OR co_ies = '2' LIMIT 1",
    ):
        assert motivo(sql) == "construcao_nao_permitida", sql
    # Uma CTE nao e tabela: o nome dela nao esta na allowlist.
    cte = f"WITH agg AS (SELECT sg_uf FROM {CURSOS}) SELECT sg_uf FROM agg LIMIT 5"
    assert motivo(cte) == "tabela_fora_da_allowlist"


BYPASSES: list[tuple[str, str]] = [
    # I-1: alias com nome de coluna nao exposta legitimava a coluna.
    (f"SELECT no_ies AS no_ies FROM {IES} LIMIT 5", "coluna_nao_permitida"),
    (
        f"SELECT co_ies FROM {IES} WHERE no_ies = 'x' OR 1 = (SELECT 1 AS no_ies) LIMIT 1",
        "construcao_nao_permitida",
    ),
    (f"SELECT co_ies AS apelido FROM {IES} WHERE apelido = 'x' LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT co_ies AS apelido FROM {IES} GROUP BY apelido LIMIT 1", "coluna_nao_permitida"),
    (
        f"SELECT co_ies AS apelido FROM {IES} GROUP BY co_ies HAVING apelido = 'x' LIMIT 1",
        "coluna_nao_permitida",
    ),
    (f"SELECT co_ies AS apelido, apelido AS outro FROM {IES} LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT co_ies FROM {IES} ORDER BY no_ies LIMIT 1", "coluna_nao_permitida"),
    (f"SELECT co_ies AS no_ies FROM {IES} ORDER BY no_ies LIMIT 1", "coluna_nao_permitida"),
    # I-2: CTE declarada numa subconsulta legitimava o mesmo nome (view de sistema) no FROM externo.
    (
        "SELECT path AS path FROM (WITH duckdb_databases AS (SELECT 1 AS co_ies) "
        "SELECT co_ies FROM duckdb_databases) AS z, duckdb_databases LIMIT 5",
        "tabela_fora_da_allowlist",
    ),
    (
        "SELECT sql AS sql FROM (WITH sqlite_master AS (SELECT 1 AS co_ies) "
        "SELECT co_ies FROM sqlite_master) AS z, sqlite_master LIMIT 5",
        "tabela_fora_da_allowlist",
    ),
    (
        "SELECT tablename AS tablename FROM (WITH pg_tables AS (SELECT 1 AS co_ies) "
        "SELECT co_ies FROM pg_tables) AS z, pg_tables LIMIT 5",
        "tabela_fora_da_allowlist",
    ),
    (
        f"WITH {IES} AS (SELECT co_ies FROM segredos) SELECT co_ies FROM {IES} LIMIT 1",
        "tabela_fora_da_allowlist",
    ),
    # I-3: JOIN e produto cartesiano entre tabelas permitidas.
    (f"SELECT a.co_ies FROM {CURSOS} a, {CURSOS} b LIMIT 1", "construcao_nao_permitida"),
    (f"SELECT co_curso FROM {CURSOS}, {CURSOS} LIMIT 1", "construcao_nao_permitida"),
    (f"SELECT co_curso FROM {CURSOS} CROSS JOIN {IES} LIMIT 1", "construcao_nao_permitida"),
    (f"SELECT co_curso FROM {CURSOS} NATURAL JOIN {IES} LIMIT 1", "construcao_nao_permitida"),
    (f"SELECT co_curso FROM {CURSOS} POSITIONAL JOIN {IES} LIMIT 1", "construcao_nao_permitida"),
    (
        f"SELECT co_curso FROM {CURSOS} ASOF JOIN {IES} ON qt_mat >= qt_doc_total LIMIT 1",
        "construcao_nao_permitida",
    ),
    (
        f"SELECT co_curso FROM {CURSOS} JOIN {IES} USING (co_ies) LIMIT 1",
        "construcao_nao_permitida",
    ),
]


@pytest.mark.parametrize(("sql", "esperado"), BYPASSES, ids=[s[:70] for s, _ in BYPASSES])
def test_bypasses_da_revisao_de_seguranca_estao_fechados(sql: str, esperado: str) -> None:
    assert motivo(sql) == esperado


def test_escopo_do_validador_e_a_entidade_do_plano() -> None:
    """Com a entidade, tabela e coluna de outra tabela do escopo tambem sao barradas."""
    validar_sql(f"SELECT qt_doc_total FROM {IES} LIMIT 1", {}, TETO_LINHAS, "ies")
    with pytest.raises(SqlRejeitado) as exc:
        validar_sql(f"SELECT co_ies FROM {CURSOS} LIMIT 1", {}, TETO_LINHAS, "ies")
    assert exc.value.motivo == "tabela_fora_da_allowlist"
    with pytest.raises(SqlRejeitado) as exc:
        validar_sql(f"SELECT qt_mat FROM {IES} LIMIT 1", {}, TETO_LINHAS, "ies")
    assert exc.value.motivo == "coluna_nao_permitida"
    with pytest.raises(SqlRejeitado) as exc:
        validar_sql("SELECT latitude FROM municipio LIMIT 1", {}, TETO_LINHAS, "cursos")
    assert exc.value.motivo == "tabela_fora_da_allowlist"
    with pytest.raises(ValueError):
        validar_sql(f"SELECT co_ies FROM {IES} LIMIT 1", {}, TETO_LINHAS, "segredos")


def test_listas_de_classes_do_sqlglot_resolvem_todas() -> None:
    """Nome de classe inexistente falha na importacao, em vez de encolher a lista em silencio."""
    from api.analista import validador_sql as v

    with pytest.raises(ImportError):
        v._classes("Select", "ClasseQueNaoExiste")
    assert len(v._PROIBIDOS) >= 40 and len(v._PERMITIDOS) == 8 + 8 + 18
    for fora in ("With", "CTE", "Subquery", "Join", "TableAlias", "Or", "In", "Paren"):
        assert getattr(v.exp, fora) not in v._PERMITIDOS


def test_limit_vinculado_tambem_respeita_o_teto() -> None:
    sql = f"SELECT co_ies FROM {IES} LIMIT $n"
    assert motivo(sql, {"n": TETO_LINHAS + 1}) == "limit_invalido"
    assert motivo(sql, {"n": "10"}) == "limit_invalido"
    assert motivo(sql, {"n": True}) == "limit_invalido"
    assert motivo(sql, {"n": 50}, teto=10) == "limit_invalido"


# --- execucao: numeros conferidos contra as somas de controle e contra o catalogo -----------------


@pytest.fixture
def base(cliente: TestClient) -> BaseAnalitica:
    b: BaseAnalitica = cliente.app.state.base  # type: ignore[attr-defined]
    return b


def executar(base: BaseAnalitica, c: ConsultaGerada) -> list[tuple[Any, ...]]:
    validar_sql(c.sql, c.params, TETO_LINHAS + 1, c.entidade)
    return base.consultar(c.sql, c.params)


@pytest.mark.dados
def test_somas_de_controle_nacionais(base: BaseAnalitica) -> None:
    por_dimensao = plano_dict(
        intent="distribuicao", dimensions=dims("oferta", "brasil", *TODAS), group_by=["dimensao"]
    )
    linhas = executar(base, consulta("matrículas por modalidade", **por_dimensao))
    assert (
        sum(r[-1] for r in linhas) == 10_227_266 == CAMADA.metrica("matriculas").controle_nacional
    )
    linhas = executar(
        base, consulta("cursos por modalidade", **{**por_dimensao, "metrics": ["cursos"]})
    )
    assert sum(r[-1] for r in linhas) == 45_776  # SUM(qt_curso), nunca COUNT(*)
    assert executar(base, consulta(P_IES_BRASIL, **PLANO_IES_BRASIL)) == [(2561,)]


@pytest.mark.dados
@pytest.mark.parametrize(
    ("metrica", "pergunta"),
    [
        ("ies", "IES no Brasil"),
        ("docentes", "docentes no Brasil"),
        ("tecnicos", "técnicos administrativos no Brasil"),
        ("municipios_com_sede", "municípios com sede de IES no Brasil"),
    ],
)
def test_metricas_de_ies_batem_com_o_controle(
    base: BaseAnalitica, metrica: str, pergunta: str
) -> None:
    dados = plano_dict(entity="ies", metrics=[metrica], dimensions=dims("sede", "brasil"))
    linhas = executar(base, consulta(pergunta, **dados))
    assert linhas == [(CAMADA.metrica(metrica).controle_nacional,)]


@pytest.mark.dados
def test_municipios_com_oferta_aplica_o_filtro_obrigatorio(base: BaseAnalitica) -> None:
    pergunta = "municípios com oferta presencial e polo EAD no Brasil"
    dados = plano_dict(
        metrics=["municipios_com_oferta"],
        dimensions=dims("oferta", "brasil", "presencial", "ead_polo"),
    )
    c = consulta(pergunta, **dados)
    assert "COUNT(DISTINCT co_municipio)" in c.sql
    assert c.sql.count("regexp_full_match(co_municipio, '[0-9]{7}')") == 1
    assert executar(base, c) == [(3551,)]  # 3.551 municipios com oferta (ADR-0004)


@pytest.mark.dados
def test_por_uf_bate_com_o_catalogo_fechado(base: BaseAnalitica) -> None:
    linhas = executar(base, consulta(P_UF_PRIVADA, **plano_uf_privada()))
    oficial = consultar_indicador(
        base,
        CATALOGO["matriculas"],
        Nivel.UF,
        Recorte.OFERTA,
        [Dimensao.PRESENCIAL],
        FiltrosConsulta(rede=Rede.PRIVADA),
    )
    assert len(linhas) == 27  # sem o filtro de 7 digitos seriam 28 "UFs"
    assert {r[0]: r[2] for r in linhas} == {x.uf: x.valor for x in oficial.linhas}
    assert sum(r[2] for r in linhas) == oficial.total
    assert [r[2] for r in linhas] == sorted((r[2] for r in linhas), reverse=True)


@pytest.mark.dados
def test_razao_bate_com_o_catalogo_fechado(base: BaseAnalitica) -> None:
    dados = plano_dict(
        intent="distribuicao",
        metrics=["inscricoes_por_vaga"],
        dimensions=dims("oferta", "uf", "presencial"),
    )
    linhas = executar(base, consulta("inscrições por vaga presenciais por UF", **dados))
    oficial = consultar_razao(
        base,
        RAZOES["inscricoes_por_vaga"],
        Recorte.OFERTA,
        [Dimensao.PRESENCIAL],
        por=Agrupamento.UF,
    )
    esperado = {x.uf: x.valor for x in oficial.linhas}
    assert len(linhas) == 27
    for sigla, _, valor in linhas:
        assert valor == pytest.approx(esperado[sigla])


@pytest.mark.dados
def test_ies_por_organizacao_e_por_regiao(base: BaseAnalitica) -> None:
    dados = plano_dict(
        intent="distribuicao", entity="ies", metrics=["ies"], dimensions=dims("sede", "brasil"),
        group_by=["organizacao"],
    )  # fmt: skip
    linhas = dict(executar(base, consulta("IES por organização acadêmica", **dados)))
    assert linhas["Universidade"] == 206 and linhas["Faculdade"] == 1897
    assert sum(linhas.values()) == 2561
    dados = plano_dict(
        intent="distribuicao", entity="ies", metrics=["docentes"], dimensions=dims("sede", "regiao")
    )
    regioes = executar(base, consulta("docentes por região", **dados))
    assert len(regioes) == 5 and sum(r[2] for r in regioes) == 374_501
