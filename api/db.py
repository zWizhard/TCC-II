"""Conexao com a camada analitica local (DuckDB, ADR-0003) — somente leitura.

Defesa em profundidade, verificada em 2026-09-26 contra o DuckDB 1.5.5:

- `read_only=True`: escrita no arquivo e ATTACH em memoria sao recusados pelo motor.
  **`CREATE TEMP TABLE` NAO e recusado** (tabela temporaria vive fora do arquivo): hoje nao ha
  SQL livre, mas o validador AST do Analista IA tera de bloquear CREATE por conta propria;
- `enable_external_access=False`: nenhuma leitura ou escrita de arquivo (`read_csv`, `COPY TO`);
- autoload/autoinstall de extensoes desligados: nada e baixado nem carregado em tempo de consulta;
- `memory_limit`: teto de memoria do motor (o timeout limita tempo, nao memoria);
- `lock_configuration=True`: nenhum `SET` posterior consegue desfazer as travas acima;
- timeout por consulta via `interrupt()`.

O PostgreSQL do IESB **nunca** e acessado pela API.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any

import duckdb

from api.erros import BaseAnaliticaIndisponivel, ConsultaExcedeuTempo

log = logging.getLogger("api.db")

_CONFIG_TRAVAS: dict[str, str | bool | int | float | list[str]] = {
    "enable_external_access": False,
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "memory_limit": "1GB",
    "lock_configuration": True,
}


class BaseAnalitica:
    """Uma conexao DuckDB por processo; um cursor por consulta (seguro entre threads)."""

    def __init__(self, caminho: Path, timeout_s: float) -> None:
        if not caminho.is_file():
            raise BaseAnaliticaIndisponivel(
                "Camada analítica local ausente. Gere-a com scripts/etl/pg_to_duckdb.py."
            )
        try:
            self._con = duckdb.connect(str(caminho), read_only=True, config=_CONFIG_TRAVAS)
        except duckdb.Error as exc:
            # Arquivo travado (ETL gravando: no Windows o escritor tem trava exclusiva),
            # corrompido ou de versao incompativel. Detalhe so no log.
            log.error("falha ao abrir a camada analitica: %s", exc)
            raise BaseAnaliticaIndisponivel(
                "Camada analítica local ilegível ou em uso pelo ETL."
            ) from exc
        self._timeout_s = timeout_s

    def consultar(self, sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Executa SQL parametrizado. O SQL vem sempre de fragmentos fixos do backend."""
        cur = self._con.cursor()
        timer = threading.Timer(self._timeout_s, cur.interrupt)
        inicio = time.perf_counter()
        timer.start()
        try:
            return cur.execute(sql, params).fetchall()
        except duckdb.InterruptException as exc:
            raise ConsultaExcedeuTempo(
                f"A consulta excedeu o limite de {self._timeout_s:g} s."
            ) from exc
        finally:
            timer.cancel()
            cur.close()
            log.debug("consulta em %.1f ms", (time.perf_counter() - inicio) * 1000)

    def fechar(self) -> None:
        self._con.close()
