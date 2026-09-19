#!/usr/bin/env python3
"""Executa SQL SOMENTE-LEITURA contra o PostgreSQL do IESB e grava o resultado em CSV.

Substitui o fluxo manual do DBeaver (rodar, exportar, colar). As travas de sessao da
ADR-0002 — que valem mesmo se a validacao do cliente aqui falhar — vivem em conexao.py.

Uso:
    python scripts/db/run_sql.py scripts/db/06_auditoria_fase2.sql --out docs/data/raw/diagnostics --prefix 2026-09-05_06
    python scripts/db/run_sql.py --query "SELECT COUNT(*) FROM municipio"

Credenciais vem do .env na raiz do projeto e NUNCA sao impressas. O agente nao le nem
escreve o .env (hook protect_secrets); quem preenche e o autor.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

import psycopg
from conexao import RAIZ, carregar_env, conectar

# Defesa em profundidade: o servidor ja recusa escrita (ADR-0002 + conta sem privilegio),
# mas barrar aqui evita gastar uma ida ao banco e deixa o motivo explicito no terminal.
PROIBIDO = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def remover_comentarios_e_textos(sql: str) -> str:
    """Devolve o SQL sem comentarios e sem literais, para o guarda-corpo olhar so codigo.

    Sem isso, `has_table_privilege(t, 'INSERT')` — que so LE um privilegio — e barrado
    porque a palavra INSERT aparece dentro de uma string. Palavra em literal nao executa nada.
    """
    saida: list[str] = []
    em_texto = False
    em_comentario = False
    i = 0
    while i < len(sql):
        c = sql[i]
        prox = sql[i + 1] if i + 1 < len(sql) else ""
        if em_comentario:
            if c == "\n":
                em_comentario = False
                saida.append(c)
            i += 1
            continue
        if em_texto:
            if c == "'":
                if prox == "'":
                    i += 2
                    continue
                em_texto = False
                saida.append(" ")
            i += 1
            continue
        if c == "-" and prox == "-":
            em_comentario = True
            i += 2
            continue
        if c == "'":
            em_texto = True
            i += 1
            continue
        saida.append(c)
        i += 1
    return "".join(saida)


def dividir_statements(sql: str) -> list[str]:
    """Divide o arquivo em statements, respeitando string literal e comentario de linha.

    Split ingenuo por ';' quebraria em qualquer ';' dentro de texto ou comentario.
    """
    saida: list[str] = []
    atual: list[str] = []
    em_texto = False
    em_comentario = False
    i = 0
    while i < len(sql):
        c = sql[i]
        prox = sql[i + 1] if i + 1 < len(sql) else ""
        if em_comentario:
            if c == "\n":
                em_comentario = False
                atual.append(c)
            i += 1
            continue
        if em_texto:
            atual.append(c)
            if c == "'":
                if prox == "'":  # '' escapado dentro do literal
                    atual.append(prox)
                    i += 2
                    continue
                em_texto = False
            i += 1
            continue
        if c == "-" and prox == "-":
            em_comentario = True
            i += 2
            continue
        if c == "'":
            em_texto = True
            atual.append(c)
            i += 1
            continue
        if c == ";":
            saida.append("".join(atual))
            atual = []
            i += 1
            continue
        atual.append(c)
        i += 1
    saida.append("".join(atual))
    return [s.strip() for s in saida if s.strip()]


def executar(
    conn: psycopg.Connection[Any],
    sql: str,
    ordem: int,
    out: Path | None,
    prefixo: str,
    preview: int = 400,
) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)  # noqa: S608 - SQL vem de arquivo versionado, nao de entrada externa
        if cur.description is None:
            print(f"[{ordem}] statement sem result set.")
            return
        colunas = [d.name for d in cur.description]
        linhas = cur.fetchall()

    print(f"\n[{ordem}] {len(linhas)} linhas x {len(colunas)} colunas")
    if out is not None:
        destino = out / f"{prefixo}{chr(96 + ordem)}.csv"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(colunas)
            w.writerows(linhas)
        alvo = destino.resolve()
        rotulo = alvo.relative_to(RAIZ) if alvo.is_relative_to(RAIZ) else alvo
        print(f"     gravado em {rotulo}")

    largura = min(len(linhas), preview)
    print("     " + " | ".join(colunas))
    for linha in linhas[:largura]:
        print("     " + " | ".join("" if v is None else str(v) for v in linha))
    if len(linhas) > largura:
        print(f"     ... (+{len(linhas) - largura} linhas apenas no CSV)")


def main() -> int:
    p = argparse.ArgumentParser(description="Executa SQL somente-leitura no PostgreSQL do IESB.")
    p.add_argument("arquivo", nargs="?", help="caminho do .sql a executar")
    p.add_argument("--query", help="SQL avulso, em vez de um arquivo")
    p.add_argument("--out", help="diretorio onde gravar os CSV")
    p.add_argument("--prefix", default="saida_", help="prefixo dos arquivos CSV")
    p.add_argument("--preview", type=int, default=400, help="linhas mostradas no terminal")
    args = p.parse_args()

    if args.query:
        sql_bruto = args.query
    elif args.arquivo:
        sql_bruto = Path(args.arquivo).read_text(encoding="utf-8")
    else:
        p.error("informe um arquivo .sql ou --query")

    if PROIBIDO.search(remover_comentarios_e_textos(sql_bruto)):
        sys.exit("BLOQUEADO: o SQL contem comando de escrita ou DDL. Esta conexao e somente-leitura.")

    statements = dividir_statements(sql_bruto)
    env = carregar_env(RAIZ / ".env")
    out = Path(args.out) if args.out else None

    conn = conectar(env)
    try:
        # Sem host nem usuario no stdout: ambos ficam so no .env (ver docs/ENVIRONMENT.md).
        print(f"conectado (sessao somente-leitura) · {len(statements)} statement(s)")
        for ordem, sql in enumerate(statements, start=1):
            executar(conn, sql, ordem, out, args.prefix, args.preview)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
