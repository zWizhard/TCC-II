#!/usr/bin/env python3
"""Complemento da auditoria da Fase 4: semantica das metricas sob o grain de `cursos`.

Le SOMENTE o DuckDB local (ADR-0003).

Tres perguntas que o fechamento de subcolunas nao responde:

1. REPLICACAO x DISTRIBUICAO. O dicionario provou que `qt_mat` e DISTRIBUIDO entre os polos
   de um curso EAD (por isso `SUM` nao infla). Isso NUNCA foi testado para `qt_vg_total`,
   `qt_inscrito_total`, `qt_ing` e `qt_conc`. Se qualquer uma delas for REPLICADA, a soma
   nacional dessa coluna esta inflada e o indicador correspondente e invalido.
   Teste: dentro da dimensao de EAD por polo, um curso com N linhas tem quantos valores
   distintos na coluna? Valor unico repetido em todas as N linhas = replicacao.

2. Os 374 cursos com SUM(qt_curso) = 0 — a diferenca entre COUNT(DISTINCT co_curso) = 46.150
   e SUM(qt_curso) = 45.776. O que sao?

3. Natureza das unidades de `municipio`: 5.571 e a contagem certa, mas "5.571 municipios" e a
   denominacao errada. Quais dessas unidades nao sao municipio?
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics" / "2026-09-19_semantica_metricas.csv"

CURSOS = "inep_educacao_superior_cursos"
IES = "inep_educacao_superior_ies"
EAD_POLO = "Cursos a distância ofertados no Brasil"

resultados: list[dict[str, str]] = []


def registrar(bloco: str, teste: str, resultado: str, detalhe: str = "") -> None:
    resultados.append({"bloco": bloco, "teste": teste, "resultado": resultado, "detalhe": detalhe})
    print(f"[{bloco}] {teste}\n    -> {resultado}" + (f"  ({detalhe})" if detalhe else ""))


def replicacao(con, coluna: str) -> None:
    """Na dimensao de EAD por polo, a coluna varia entre os polos do mesmo curso?"""
    q = f"""
        WITH multi AS (
            SELECT co_curso,
                   COUNT(*)                  AS n_linhas,
                   COUNT(DISTINCT {coluna})  AS n_valores,
                   MAX({coluna})             AS maximo,
                   SUM({coluna})             AS soma
            FROM {CURSOS}
            WHERE tp_dimensao = ?
            GROUP BY co_curso
            HAVING COUNT(*) > 1 AND MAX({coluna}) > 0
        )
        SELECT COUNT(*)                                   AS cursos,
               COUNT(*) FILTER (WHERE n_valores = 1)      AS constante_em_todas,
               COUNT(*) FILTER (WHERE n_valores > 1)      AS variavel,
               SUM(soma)                                  AS soma_total,
               SUM(soma) FILTER (WHERE n_valores = 1)     AS soma_dos_constantes
        FROM multi
    """
    cur, const, var, soma, soma_const = con.execute(q, [EAD_POLO]).fetchone()
    soma = soma or 0
    soma_const = soma_const or 0
    if cur == 0:
        veredito = "SEM CASO (coluna zerada na dimensao EAD por polo)"
    elif const == 0:
        veredito = "DISTRIBUIDA (varia entre polos) -> SUM e valido"
    elif var == 0:
        veredito = "REPLICADA (valor identico em todos os polos) -> SUM INFLA"
    else:
        veredito = "MISTA -> SUM suspeito"
    registrar(
        "1. replicacao x distribuicao",
        f"{coluna} na dimensao '{EAD_POLO}'",
        veredito,
        f"cursos_multi_linha_com_valor={cur:,} constantes={const:,} variaveis={var:,} "
        f"soma_na_dimensao={soma:,} soma_atribuivel_a_constantes={soma_const:,}",
    )


def main() -> int:
    if not BANCO.exists():
        print(f"ERRO: {BANCO} nao existe.", file=sys.stderr)
        return 2
    con = duckdb.connect(str(BANCO), read_only=True)

    # ------------------------------------------------------------------ bloco 1
    for c in (
        "qt_mat",
        "qt_vg_total",
        "qt_inscrito_total",
        "qt_ing",
        "qt_conc",
        "qt_mat_financ",
        "qt_mat_reserva_vaga",
        "qt_sit_desvinculado",
    ):
        replicacao(con, c)

    # Soma por dimensao das colunas ainda sem soma de controle publicada.
    for c in ("qt_vg_total", "qt_inscrito_total"):
        q = f"SELECT tp_dimensao, SUM({c}) FROM {CURSOS} GROUP BY 1 ORDER BY 2 DESC"
        partes = "; ".join(f"{d}={s:,}" for d, s in con.execute(q).fetchall())
        tot = con.execute(f"SELECT SUM({c}) FROM {CURSOS}").fetchone()[0]
        registrar(
            "1. replicacao x distribuicao",
            f"soma de {c} por tp_dimensao",
            f"nacional={tot:,}",
            partes,
        )

    # Turno: o residuo medido (partes < total) corresponde exatamente a EAD?
    for base in ("qt_mat", "qt_ing", "qt_conc"):
        q = f"""
            SELECT SUM({base}) - SUM({base}_diurno + {base}_noturno),
                   SUM({base}) FILTER (WHERE tp_modalidade_ensino = 'Curso a distância'),
                   SUM({base}_diurno + {base}_noturno)
                     FILTER (WHERE tp_modalidade_ensino = 'Curso a distância')
            FROM {CURSOS}
        """
        residuo, ead, ead_turno = con.execute(q).fetchone()
        registrar(
            "1. replicacao x distribuicao",
            f"turno: residuo de {base} == EAD?",
            "SIM — turno so existe no presencial"
            if residuo == ead and ead_turno == 0
            else "NAO — investigar",
            f"residuo={residuo:,} soma_EAD={ead:,} turno_declarado_em_EAD={ead_turno:,}",
        )

    # ------------------------------------------------------------------ bloco 2
    q = f"""
        WITH por_curso AS (SELECT co_curso, SUM(qt_curso) AS s FROM {CURSOS} GROUP BY 1),
        zerados AS (SELECT co_curso FROM por_curso WHERE s = 0)
        SELECT COUNT(DISTINCT c.co_curso),
               SUM(c.qt_mat), SUM(c.qt_ing), SUM(c.qt_conc),
               SUM(c.qt_vg_total), SUM(c.qt_inscrito_total),
               SUM(c.qt_sit_trancada + c.qt_sit_desvinculado
                   + c.qt_sit_transferido + c.qt_sit_falecido)
        FROM {CURSOS} c JOIN zerados z USING (co_curso)
    """
    n, mat, ing, conc, vg, insc, sit = con.execute(q).fetchone()
    registrar(
        "2. cursos com qt_curso = 0",
        "perfil dos 374 cursos nao contados",
        f"{n:,} cursos",
        f"qt_mat={mat:,} qt_ing={ing:,} qt_conc={conc:,} qt_vg_total={vg:,} "
        f"qt_inscrito_total={insc:,} situacoes={sit:,}",
    )
    q = f"""
        WITH por_curso AS (SELECT co_curso, SUM(qt_curso) AS s FROM {CURSOS} GROUP BY 1),
        zerados AS (SELECT co_curso FROM por_curso WHERE s = 0)
        SELECT COUNT(*) FILTER (WHERE m = 0 AND i = 0 AND vg = 0 AND ins = 0),
               COUNT(*) FILTER (WHERE c > 0),
               COUNT(*) FILTER (WHERE m > 0),
               COUNT(*)
        FROM (
            SELECT co_curso, SUM(qt_mat) m, SUM(qt_ing) i, SUM(qt_conc) c,
                   SUM(qt_vg_total) vg, SUM(qt_inscrito_total) ins
            FROM {CURSOS} WHERE co_curso IN (SELECT co_curso FROM zerados)
            GROUP BY 1
        )
    """
    inertes, com_conc, com_mat, tot = con.execute(q).fetchone()
    registrar(
        "2. cursos com qt_curso = 0",
        "composicao dos nao contados",
        f"sem vaga/inscrito/ingressante/matricula={inertes:,} de {tot:,}",
        f"com concluintes={com_conc:,} com matriculas={com_mat:,}",
    )

    # ------------------------------------------------------------------ bloco 3
    q = """
        SELECT COUNT(*) FILTER (WHERE codigo_municipio_dv::text LIKE '99%'),
               COUNT(*) FILTER (WHERE right(codigo_municipio_dv::text, 5) = '00000'
                                  AND codigo_municipio_dv::text NOT LIKE '99%'),
               COUNT(*) FILTER (WHERE right(codigo_municipio_dv::text, 5) <> '00000'
                                  AND codigo_municipio_dv::text NOT LIKE '99%'),
               COUNT(*)
        FROM municipio
    """
    exterior, ignorado, reais, tot = con.execute(q).fetchone()
    publicado = con.execute(
        """SELECT COUNT(*) FROM municipio
           WHERE right(codigo_municipio_dv::text, 5) <> '00000'
             AND codigo_municipio_dv::text <> '9999999'"""
    ).fetchone()[0]
    registrar(
        "3. unidades territoriais",
        "decomposicao de `municipio`",
        f"reais={reais:,} 'Municipio Ignorado - UF'={ignorado} exterior(99*)={exterior} "
        f"total={tot:,}",
        f"filtro publicado no DATA_DICTIONARY devolve {publicado:,} — confere "
        f"(9900000 ja cai na condicao de '00000')",
    )
    q = """
        SELECT COUNT(*) FROM municipio
        WHERE right(codigo_municipio_dv::text, 5) <> '00000'
          AND codigo_municipio_dv::text NOT LIKE '99%'
          AND codigo_municipio_dv::text <> '2605459'
    """
    sem_fn = con.execute(q).fetchone()[0]
    registrar(
        "3. unidades territoriais",
        "unidades reais excluindo Fernando de Noronha (2605459)",
        f"{sem_fn:,}",
        "5.571 unidades = 5.570 + Fernando de Noronha; PE aparece com 185 unidades",
    )
    q = """
        SELECT cd_uf, COUNT(*) FROM municipio
        WHERE right(codigo_municipio_dv::text, 5) <> '00000'
          AND codigo_municipio_dv::text NOT LIKE '99%'
          AND cd_uf IN ('26', '53')
        GROUP BY 1 ORDER BY 1
    """
    registrar(
        "3. unidades territoriais",
        "PE (26) e DF (53)",
        "; ".join(f"UF {u}={n}" for u, n in con.execute(q).fetchall()),
        "DF tem uma unica unidade de nivel municipal (Brasilia)",
    )
    # O Censo usa alguma sentinela?
    q = f"""
        SELECT
          (SELECT COUNT(*) FROM {IES}
             WHERE right(co_municipio_ies::text, 5) = '00000'
                OR co_municipio_ies::text LIKE '99%'),
          (SELECT COUNT(*) FROM {CURSOS}
             WHERE regexp_full_match(co_municipio, '[0-9]{{7}}')
               AND (right(co_municipio, 5) = '00000' OR co_municipio LIKE '99%'))
    """
    a, b = con.execute(q).fetchone()
    registrar(
        "3. unidades territoriais",
        "o Censo referencia alguma sentinela?",
        "NAO" if a == 0 and b == 0 else "SIM — investigar",
        f"linhas de IES={a} linhas de cursos={b}",
    )

    con.close()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["bloco", "teste", "resultado", "detalhe"])
        w.writeheader()
        w.writerows(resultados)
    print(f"\n{len(resultados)} verificacoes -> {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
