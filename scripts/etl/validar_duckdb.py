#!/usr/bin/env python3
"""Confere se a copia DuckDB reproduz a origem — linha a linha, soma a soma.

Um ETL que termina sem excecao nao prova nada: lote perdido, tipo trocado e truncamento
silencioso passam pelo caminho feliz. Este script e a evidencia de que a camada analitica
local pode substituir o banco institucional sem mudar o numero do TCC.

Uso:
    .venv/Scripts/python.exe scripts/etl/validar_duckdb.py
    .venv/Scripts/python.exe scripts/etl/validar_duckdb.py --sem-origem

Sai com codigo != 0 se qualquer verificacao FALHAR.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import catalogo
import duckdb
from catalogo import Tabela

RAIZ = Path(__file__).resolve().parents[2]

# Mesma razao de pg_to_duckdb.py: nao ha pacote instalavel e as travas da ADR-0002 moram
# em scripts/db/conexao.py.
sys.path.insert(0, str(RAIZ / "scripts" / "db"))

from conexao import carregar_env, conectar  # noqa: E402

# As somas de controle varrem 720 mil linhas na origem; os 60s padrao do .env sao curtos.
VALIDACAO_STATEMENT_TIMEOUT = "10min"

DIAGNOSTICOS = "docs/data/raw/diagnostics"

# Situacoes. So FALHA muda o codigo de saida: PENDENTE e "ainda nao copiado" e ESPERADO e
# divergencia documentada da origem — tratar qualquer um dos dois como erro ensinaria a
# ignorar o relatorio.
OK = "OK"
FALHA = "FALHA"
PENDENTE = "PENDENTE"
ESPERADO = "ESPERADO"
ATENCAO = "ATENCAO"


@dataclass
class Resultado:
    tabela: str
    verificacao: str
    esperado: str
    obtido: str
    situacao: str
    detalhe: str = ""


def escalar_duck(duck: duckdb.DuckDBPyConnection, sql: str) -> Any:
    """Primeiro valor da primeira linha, na copia."""
    linha = duck.execute(sql).fetchone()
    return linha[0] if linha else None


def escalar_pg(conn: Any, sql: str) -> Any:
    """Primeiro valor da primeira linha, na origem. Mesma consulta dos dois lados e o ponto: se o SQL precisar de dialeto diferente, a comparacao deixa de ser comparacao."""
    with conn.cursor() as cur:
        cur.execute(sql)
        linha = cur.fetchone()
    return linha[0] if linha else None


def tabelas_na_copia(duck: duckdb.DuckDBPyConnection) -> set[str]:
    linhas = duck.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    return {str(linha[0]) for linha in linhas}


def colunas_na_copia(duck: duckdb.DuckDBPyConnection, tabela: str) -> dict[str, str]:
    linhas = duck.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
        [tabela],
    ).fetchall()
    return {str(linha[0]): str(linha[1]) for linha in linhas}


def comparar(
    tabela: str, verificacao: str, esperado: Any, obtido: Any, detalhe: str = ""
) -> Resultado:
    igual = esperado == obtido
    return Resultado(
        tabela=tabela,
        verificacao=verificacao,
        esperado=str(esperado),
        obtido=str(obtido),
        situacao=OK if igual else FALHA,
        detalhe=detalhe,
    )


def validar_tabela(
    duck: duckdb.DuckDBPyConnection,
    conn: Any | None,
    tabela: Tabela,
) -> list[Resultado]:
    """Contagem, colunas, unicidade da chave e somas de controle de uma tabela da copia."""
    res: list[Resultado] = []
    nome = tabela.nome

    linhas_copia = int(escalar_duck(duck, f'SELECT COUNT(*) FROM "{nome}"'))
    res.append(
        comparar(
            nome,
            "COUNT(*) vs catalogo",
            tabela.linhas_esperadas,
            linhas_copia,
            "contagem medida na origem em 2026-09-05",
        )
    )
    if conn is not None:
        linhas_origem = int(
            escalar_pg(conn, f'SELECT COUNT(*) FROM "{catalogo.SCHEMA_ORIGEM}"."{nome}"')
        )
        res.append(comparar(nome, "COUNT(*) vs origem", linhas_origem, linhas_copia))

    colunas = colunas_na_copia(duck, nome)
    if tabela.colunas_esperadas is not None:
        res.append(comparar(nome, "n colunas vs catalogo", tabela.colunas_esperadas, len(colunas)))
    if conn is not None:
        n_origem = int(
            escalar_pg(
                conn,
                "SELECT COUNT(*) FROM information_schema.columns "
                f"WHERE table_schema = '{catalogo.SCHEMA_ORIGEM}' AND table_name = '{nome}'",
            )
        )
        res.append(comparar(nome, "n colunas vs origem", n_origem, len(colunas)))

    # Chave natural: o ETL nao cria PK, entao a unicidade e conferida aqui. Coluna que nao
    # existe na copia vira FALHA explicita em vez de erro de SQL sem contexto.
    faltando = [c for c in tabela.chave_natural if c not in colunas]
    chave = ", ".join(f'"{c}"' for c in tabela.chave_natural)
    if faltando:
        res.append(
            Resultado(
                nome,
                "chave natural presente",
                ", ".join(tabela.chave_natural),
                f"ausente: {', '.join(faltando)}",
                FALHA,
            )
        )
    else:
        distintos = int(
            escalar_duck(duck, f'SELECT COUNT(*) FROM (SELECT DISTINCT {chave} FROM "{nome}")')
        )
        excedente = linhas_copia - distintos
        rotulo = f"unicidade de ({', '.join(tabela.chave_natural)})"
        if tabela.duplicatas_conhecidas:
            # Duplicata da ORIGEM, nao da copia: a copia fiel tem de reproduzi-la.
            conforme = excedente == tabela.duplicatas_conhecidas
            res.append(
                Resultado(
                    nome,
                    rotulo,
                    f"{tabela.duplicatas_conhecidas} linhas excedentes (duplicatas da origem)",
                    f"{excedente} linhas excedentes ({distintos} chaves distintas em {linhas_copia} linhas)",
                    ESPERADO if conforme else ATENCAO,
                    "divergencia conhecida da origem (anos 2000-2020); copia fiel tem de reproduzi-la"
                    if conforme
                    else "numero de duplicatas mudou em relacao ao medido na origem — conferir a origem",
                )
            )
        else:
            res.append(
                comparar(nome, rotulo, linhas_copia, distintos, "chave natural deve ser unica")
            )

    for expressao, valor in tabela.somas_controle.items():
        try:
            obtido = escalar_duck(duck, f'SELECT {expressao} FROM "{nome}"')
        except duckdb.Error as erro:
            res.append(
                Resultado(nome, f"{expressao} (copia)", str(valor), "erro", FALHA, str(erro))
            )
            continue
        res.append(
            comparar(
                nome,
                f"{expressao} vs constante",
                valor,
                int(obtido),
                "medido no Censo 2024, unico ano da tabela",
            )
        )
        if conn is not None:
            na_origem = escalar_pg(
                conn, f'SELECT {expressao} FROM "{catalogo.SCHEMA_ORIGEM}"."{nome}"'
            )
            res.append(comparar(nome, f"{expressao} vs origem", int(na_origem), int(obtido)))

    # nu_ano_censo e TEXTO na origem nas duas tabelas do Censo. Se a copia o converteu para
    # inteiro, todo filtro do projeto (que usa '2024') passa a devolver zero linha.
    if "nu_ano_censo" in colunas:
        tipo = colunas["nu_ano_censo"]
        res.append(
            Resultado(
                nome,
                "tipo de nu_ano_censo",
                "VARCHAR",
                tipo,
                OK if tipo.upper().startswith("VARCHAR") else FALHA,
                "filtrar com '2024', nunca 2024",
            )
        )
    return res


def imprimir(res: list[Resultado]) -> None:
    largura = max((len(r.verificacao) for r in res), default=20)
    atual = ""
    for r in res:
        if r.tabela != atual:
            atual = r.tabela
            print(f"\n== {atual}")
        print(
            f"   [{r.situacao:<9}] {r.verificacao:<{largura}}  esperado={r.esperado}  obtido={r.obtido}"
        )


def gravar_csv(res: list[Resultado], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["tabela", "verificacao", "esperado", "obtido", "situacao", "detalhe"])
        for r in res:
            w.writerow([r.tabela, r.verificacao, r.esperado, r.obtido, r.situacao, r.detalhe])


def main() -> int:
    p = argparse.ArgumentParser(description="Valida a copia DuckDB contra a origem e o catalogo.")
    p.add_argument("--arquivo", default=catalogo.DESTINO_PADRAO, help="arquivo .duckdb a validar")
    p.add_argument(
        "--sem-origem",
        action="store_true",
        help="valida so a copia, sem abrir conexao com o PostgreSQL",
    )
    p.add_argument("--out", default=DIAGNOSTICOS, help="diretorio do CSV de evidencia")
    args = p.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    if not caminho.exists():
        sys.exit(f"ERRO: {caminho} nao existe. Rode scripts/etl/pg_to_duckdb.py antes.")

    duck = duckdb.connect(str(caminho), read_only=True)
    conn = None
    if not args.sem_origem:
        conn = conectar(carregar_env(RAIZ / ".env"), statement_timeout=VALIDACAO_STATEMENT_TIMEOUT)
        print(
            "conectado a origem (sessao somente-leitura) — as somas de controle varrem cursos inteiro"
        )
    else:
        print("--sem-origem: conferindo a copia contra o catalogo apenas")

    res: list[Resultado] = []
    try:
        presentes = tabelas_na_copia(duck)
        for tabela in catalogo.tabelas_em_ordem():
            if tabela.nome not in presentes:
                res.append(
                    Resultado(
                        tabela.nome,
                        "presenca na copia",
                        "tabela carregada",
                        "ausente",
                        PENDENTE,
                        "rode pg_to_duckdb.py --tabelas " + tabela.nome,
                    )
                )
                continue
            res.extend(validar_tabela(duck, conn, tabela))
    finally:
        duck.close()
        if conn is not None:
            conn.close()

    imprimir(res)

    out = Path(args.out)
    if not out.is_absolute():
        out = RAIZ / out
    # Sufixo proprio para --sem-origem: sem ele, uma conferencia parcial (17 verificacoes)
    # sobrescreve a evidencia completa (30, com a comparacao contra a origem) e o repositorio
    # passa a guardar a prova mais fraca das duas.
    sufixo = "_validacao_duckdb_sem_origem" if args.sem_origem else "_validacao_duckdb"
    destino = out / f"{date.today().isoformat()}{sufixo}.csv"
    gravar_csv(res, destino)

    falhas = [r for r in res if r.situacao == FALHA]
    atencoes = [r for r in res if r.situacao == ATENCAO]
    pendentes = [r for r in res if r.situacao == PENDENTE]
    print(
        f"\n{len(res)} verificacoes · {len(falhas)} falha(s) · {len(atencoes)} atencao(oes) · "
        f"{len(pendentes)} pendente(s)"
    )
    print(f"evidencia: {destino}")
    if pendentes:
        print("Copia PARCIAL: ha tabela do catalogo ainda nao carregada.")
    if falhas:
        for r in falhas:
            print(f"FALHA: {r.tabela} · {r.verificacao} · esperado={r.esperado} obtido={r.obtido}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
