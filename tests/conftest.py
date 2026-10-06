from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app

CAMINHO_BASE = Settings().analytics_duckdb_path


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # A camada analitica nao e versionada (ADR-0003): sem ela, os testes de dados sao pulados
    # com o motivo explicito, nunca dados como aprovados.
    if CAMINHO_BASE.is_file():
        return
    pular = pytest.mark.skip(reason=f"{CAMINHO_BASE} ausente; rode scripts/etl/pg_to_duckdb.py")
    for item in items:
        if "dados" in item.keywords:
            item.add_marker(pular)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "dados: exige a camada analitica DuckDB local")


@pytest.fixture(scope="session")
def cliente() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as c:
        yield c


@pytest.fixture
def cliente_sem_base(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(analytics_duckdb_path=tmp_path / "inexistente.duckdb")
    with TestClient(create_app(settings)) as c:
        yield c
