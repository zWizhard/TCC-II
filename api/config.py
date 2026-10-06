"""Configuracao da API, lida somente de variaveis de ambiente.

A API **nao le o `.env`**: ela nao precisa de segredo algum. O unico recurso de dados que
toca e o arquivo DuckDB local (ADR-0003), aberto em modo somente-leitura. As credenciais do
PostgreSQL do IESB servem apenas ao ETL (`scripts/etl/`) e nunca entram neste processo.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Sem env_file de proposito (ver docstring do modulo).
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    analytics_duckdb_path: Path = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
    etl_manifest_path: Path = RAIZ / "docs" / "data" / "ETL_MANIFEST.json"
    # Consultas do dashboard levam ~10-15 ms; o teto so existe para conter o anomalo.
    api_query_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    # Lista separada por virgula, no mesmo formato do .env.example.
    api_cors_origins: str = "http://localhost:5173"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
