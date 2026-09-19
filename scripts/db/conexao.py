#!/usr/bin/env python3
"""Fonte unica das travas de sessao da ADR-0002 para tudo que fala com o PostgreSQL do IESB.

Antes, run_sql.py carregava o .env e aplicava as travas por conta propria. Com o ETL
precisando da mesma conexao, manter duas copias significaria que um ajuste futuro numa
delas (um timeout, o SHOW de verificacao) deixaria a outra silenciosamente insegura.
Quem precisa do banco importa daqui.

Credenciais vem do .env na raiz do projeto e NUNCA sao impressas — nem em erro, nem em
log, nem no transcript do agente (hook protect_secrets).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import psycopg

RAIZ = Path(__file__).resolve().parents[2]


def carregar_env(caminho: Path) -> dict[str, str]:
    """Le KEY=VALUE do .env. Nao imprime nada: o valor da senha nao pode vazar no transcript."""
    if not caminho.exists():
        sys.exit(
            f"ERRO: {caminho.name} nao encontrado em {caminho.parent}.\n"
            "Copie .env.example para .env e preencha PGHOST, PGPORT, PGDATABASE, PGUSER e PGPASSWORD.\n"
            "O .env esta no .gitignore e nao vai para o GitHub."
        )
    env: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        env[chave.strip()] = valor.strip().strip("\"'")
    faltando = [k for k in ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD") if not env.get(k)]
    if faltando:
        sys.exit(f"ERRO: variaveis sem valor no .env: {', '.join(faltando)}")
    return env


def conectar(
    env: dict[str, str],
    *,
    statement_timeout: str | None = None,
    idle_timeout: str | None = None,
) -> psycopg.Connection[Any]:
    """Abre a conexao e aplica as travas de sessao da ADR-0002 antes de qualquer consulta.

    Os dois timeouts sao parametrizaveis porque a consulta exploratoria e a extracao tem
    perfis opostos: a primeira deve morrer rapido se escapar do controle; a segunda mantem
    um cursor server-side aberto enquanto grava lotes no DuckDB e seria derrubada pelo
    idle_in_transaction_session_timeout de 60s. Sem argumento, vale exatamente o que o .env
    define — o comportamento historico de run_sql.py. A trava somente-leitura, essa, nao e
    negociavel em nenhum dos dois casos.
    """
    conn = psycopg.connect(
        host=env["PGHOST"],
        port=int(env.get("PGPORT", "5432")),
        dbname=env["PGDATABASE"],
        user=env["PGUSER"],
        password=env["PGPASSWORD"],
        sslmode=env.get("PGSSLMODE", "prefer"),
        connect_timeout=15,
        autocommit=True,
    )
    timeout = statement_timeout or env.get("PG_STATEMENT_TIMEOUT", "60s")
    idle = idle_timeout or env.get("PG_IDLE_TX_TIMEOUT", "60s")
    with conn.cursor() as cur:
        cur.execute("SET default_transaction_read_only = on")
        cur.execute(f"SET statement_timeout = '{timeout}'")
        cur.execute(f"SET idle_in_transaction_session_timeout = '{idle}'")
        cur.execute("SHOW default_transaction_read_only")
        linha = cur.fetchone()
        if not linha or linha[0] != "on":
            conn.close()
            sys.exit("ERRO: a sessao nao ficou somente-leitura. Abortado.")
    return conn
