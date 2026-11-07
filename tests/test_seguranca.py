"""Travas da conexao, superficie HTTP e coerencia do catalogo com o dado."""

from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.config import RAIZ, Settings
from api.db import BaseAnalitica
from api.erros import ConsultaExcedeuTempo
from api.indicadores import (
    CODIGO_REGIAO,
    MODALIDADE_DA_DIMENSAO,
    REDE_DA_CATEGORIA,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_ORGANIZACAO,
    ROTULO_REDE,
    ROTULO_REGIAO,
    UF,
    UF_INFO,
)
from api.main import create_app

ARQUIVO_EXISTENTE = (RAIZ / "pyproject.toml").as_posix()


@pytest.fixture(scope="module")
def base() -> BaseAnalitica:
    return BaseAnalitica(Settings().analytics_duckdb_path, timeout_s=0.3)


@pytest.mark.dados
@pytest.mark.parametrize(
    ("sql", "motivo"),
    [
        # match= exige o motivo certo: um erro qualquer (arquivo inexistente, sem rede) nao aprova.
        ("CREATE TABLE x (a INTEGER)", "read-only"),
        ("CREATE VIEW v AS SELECT 1", "read-only"),
        (f"SELECT * FROM read_csv('{ARQUIVO_EXISTENTE}')", "disabled by configuration"),
        ("COPY (SELECT 1) TO 'vazamento.csv'", "disabled by configuration"),
        ("ATTACH ':memory:' AS m", "read-only"),
        ("SET enable_external_access = true", "locked"),
        ("SET memory_limit = '64GB'", "locked"),
        ("INSTALL httpfs", "disabled by configur"),
        ("LOAD httpfs", "disabled through configuration"),
    ],
)
def test_conexao_recusa_escrita_arquivo_e_reconfiguracao(
    base: BaseAnalitica, sql: str, motivo: str
) -> None:
    with pytest.raises(duckdb.Error, match=motivo):
        base.consultar(sql, {})


@pytest.mark.dados
def test_timeout_interrompe_consulta(base: BaseAnalitica) -> None:
    with pytest.raises(ConsultaExcedeuTempo):
        base.consultar("SELECT count(*) FROM range(100000000000) a", {})


@pytest.mark.dados
def test_valores_literais_do_catalogo_existem_no_dado(base: BaseAnalitica) -> None:
    dims = {
        r[0]
        for r in base.consultar(
            "SELECT DISTINCT tp_dimensao FROM inep_educacao_superior_cursos", {}
        )
    }
    assert dims == set(ROTULO_DIMENSAO.values())
    for sql in (
        "SELECT DISTINCT sg_uf_ies FROM inep_educacao_superior_ies",
        "SELECT DISTINCT sg_uf FROM inep_educacao_superior_cursos "
        "WHERE regexp_full_match(co_municipio, '[0-9]{7}')",
    ):
        assert {r[0] for r in base.consultar(sql, {})} == {str(u) for u in UF}


@pytest.mark.dados
def test_literais_dos_filtros_existem_nas_duas_tabelas(base: BaseAnalitica) -> None:
    ies, cursos = "inep_educacao_superior_ies", "inep_educacao_superior_cursos"
    com_territorio = "regexp_full_match(co_municipio, '[0-9]{7}')"

    def distintos(sql: str) -> set[tuple[object, ...]]:
        return {tuple(r) for r in base.consultar(sql, {})}

    # Categoria administrativa -> rede: mesmos pares em IES (ds_rede) e em cursos (tp_rede).
    categorias = {(ROTULO_CATEGORIA[c], ROTULO_REDE[r]) for c, r in REDE_DA_CATEGORIA.items()}
    assert (
        distintos(f"SELECT DISTINCT tp_categoria_administrativa, ds_rede FROM {ies}") == categorias
    )
    assert (
        distintos(f"SELECT DISTINCT tp_categoria_administrativa, tp_rede FROM {cursos}")
        == categorias
    )
    organizacoes = {(r,) for r in ROTULO_ORGANIZACAO.values()}
    assert distintos(f"SELECT DISTINCT tp_organizacao_academica FROM {ies}") == organizacoes
    assert distintos(f"SELECT DISTINCT tp_organizacao_academica FROM {cursos}") == organizacoes
    # Os dois atributos sao da IES: nenhum curso diverge da sua instituicao. Agregado por
    # co_ies antes da comparacao; a contagem e de IES, nao de linhas de cursos.
    for coluna in ("tp_categoria_administrativa", "tp_organizacao_academica"):
        divergentes = base.consultar(
            f"SELECT count(*) FROM (SELECT DISTINCT co_ies, {coluna} AS v FROM {cursos}) c "
            f"LEFT JOIN {ies} i ON i.co_ies = c.co_ies AND i.{coluna} = c.v "
            "WHERE i.co_ies IS NULL",
            {},
        )
        assert divergentes[0][0] == 0
    # UF -> (nome, regiao) e regiao -> (codigo, nome).
    ufs = {
        (str(uf), nome, CODIGO_REGIAO[regiao], ROTULO_REGIAO[regiao])
        for uf, (nome, regiao) in UF_INFO.items()
    }
    assert set(UF_INFO) == set(UF)
    assert (
        distintos(
            "SELECT DISTINCT sg_uf_ies, no_uf_ies, CAST(co_regiao_ies AS VARCHAR), no_regiao_ies "
            f"FROM {ies}"
        )
        == ufs
    )
    assert (
        distintos(
            f"SELECT DISTINCT sg_uf, no_uf, co_regiao, no_regiao FROM {cursos} WHERE {com_territorio}"
        )
        == ufs
    )
    # Modalidade e funcao da dimensao de oferta.
    assert distintos(f"SELECT DISTINCT tp_dimensao, tp_modalidade_ensino FROM {cursos}") == {
        (ROTULO_DIMENSAO[d], m) for d, m in MODALIDADE_DA_DIMENSAO.items()
    }


def test_somente_get(cliente: TestClient) -> None:
    r = cliente.post("/api/v1/indicadores/ies")
    assert (r.status_code, r.json()["erro"]["codigo"]) == (405, "http_405")
    r = cliente.get("/api/v1/sql?q=SELECT 1")
    assert (r.status_code, r.json()["erro"]["codigo"]) == (404, "http_404")


@pytest.mark.dados
def test_slug_desconhecido_nao_e_ecoado(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/indicadores/<script>?nivel=brasil&recorte=sede")
    assert r.status_code == 404
    assert "<script>" not in r.text


def test_base_ausente_nao_derruba_a_api(cliente_sem_base: TestClient) -> None:
    assert cliente_sem_base.get("/api/health").json()["base_analitica"] == "indisponivel"
    r = cliente_sem_base.get("/api/v1/indicadores/ies?nivel=brasil&recorte=sede")
    assert r.status_code == 503
    assert r.json()["erro"]["codigo"] == "base_analitica_indisponivel"
    assert "inexistente" not in r.text  # caminho do arquivo nao vaza


def test_base_ilegivel_nao_derruba_a_api(tmp_path: Path) -> None:
    corrompida = tmp_path / "corrompida.duckdb"
    corrompida.write_bytes(b"isto nao e um arquivo duckdb" * 100)
    with TestClient(create_app(Settings(analytics_duckdb_path=corrompida))) as c:
        assert c.get("/api/health").json()["base_analitica"] == "indisponivel"
        r = c.get("/api/v1/indicadores/ies?nivel=brasil&recorte=sede")
        assert r.status_code == 503
        assert "corrompida" not in r.text
