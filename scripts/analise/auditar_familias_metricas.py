#!/usr/bin/env python3
"""Auditoria das familias de metricas ainda nao verificadas (Fase 4 - indicadores).

Le SOMENTE o DuckDB local (ADR-0003). Nao toca o PostgreSQL institucional.

Motivo: as familias qt_vg_*, qt_inscrito_*, qt_doc_ex_*, qt_*_financ*, qt_*_rv* e qt_sit_*
nunca tiveram soma de controle nem prova de fechamento. Um indicador derivado dessas colunas
seria uma razao entre numerador e denominador de semantica desconhecida.

O teste central e o de FECHAMENTO: as subcolunas somam exatamente a coluna-total?
- soma_partes == total em TODAS as linhas -> particao (subcategorias mutuamente exclusivas)
- soma_partes  > total em alguma linha    -> SOBREPOSICAO (a mesma pessoa em duas colunas)
- soma_partes  < total em alguma linha    -> RESIDUO nao coberto pelas subcolunas

Uso:
    .venv/Scripts/python.exe scripts/analise/auditar_familias_metricas.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics" / "2026-09-19_familias_metricas.csv"

CURSOS = "inep_educacao_superior_cursos"
IES = "inep_educacao_superior_ies"

resultados: list[dict[str, str]] = []


def registrar(familia: str, teste: str, resultado: str, detalhe: str = "") -> None:
    resultados.append(
        {"familia": familia, "teste": teste, "resultado": resultado, "detalhe": detalhe}
    )
    print(f"[{familia}] {teste}\n    -> {resultado}" + (f"  ({detalhe})" if detalhe else ""))


def fechamento(con, familia: str, tabela: str, total: str, partes: list[str], rotulo: str) -> None:
    """Testa se as `partes` fecham com o `total`, linha a linha e no agregado."""
    soma_partes = " + ".join(partes)
    q = f"""
        SELECT
            COUNT(*)                                            AS linhas,
            SUM({total})                                        AS total_nac,
            SUM({soma_partes})                                  AS partes_nac,
            COUNT(*) FILTER (WHERE ({soma_partes}) <> {total})  AS linhas_divergentes,
            COUNT(*) FILTER (WHERE ({soma_partes})  > {total})  AS linhas_partes_maior,
            COUNT(*) FILTER (WHERE ({soma_partes})  < {total})  AS linhas_partes_menor,
            MAX(ABS(({soma_partes}) - {total}))                 AS max_dif_abs
        FROM {tabela}
    """
    linhas, tot, par, div, maior, menor, maxdif = con.execute(q).fetchone()
    if div == 0:
        veredito = "FECHA (particao exata)"
    elif maior > 0 and menor == 0:
        veredito = "SOBREPOSICAO (partes > total)"
    elif menor > 0 and maior == 0:
        veredito = "RESIDUO (partes < total)"
    else:
        veredito = "NAO FECHA (nos dois sentidos)"
    registrar(
        familia,
        f"{rotulo}: {total} vs {' + '.join(partes)}",
        veredito,
        f"total={tot:,} partes={par:,} dif={par - tot:+,} "
        f"linhas_div={div:,}/{linhas:,} (maior={maior:,} menor={menor:,}) max_dif={maxdif:,}",
    )


def contencao(con, familia: str, tabela: str, parte: str, total: str, rotulo: str) -> None:
    """Testa se `parte` nunca excede `total` (subconjunto)."""
    q = f"""
        SELECT SUM({parte}), SUM({total}),
               COUNT(*) FILTER (WHERE {parte} > {total}),
               MAX({parte} - {total})
        FROM {tabela}
    """
    sp, st, viol, maxexc = con.execute(q).fetchone()
    veredito = "CONTIDO" if viol == 0 else "EXCEDE O TOTAL"
    registrar(
        familia,
        f"{rotulo}: {parte} <= {total}",
        veredito,
        f"parte={sp:,} total={st:,} violacoes={viol:,} max_excesso={maxexc:,}",
    )


def dominio(con, familia: str, tabela: str, coluna: str) -> None:
    """Minimo, maximo, negativos e zeros. 'Nao ha NULL' ja esta provado no schema."""
    q = f"""
        SELECT MIN({coluna}), MAX({coluna}), SUM({coluna}),
               COUNT(*) FILTER (WHERE {coluna} < 0),
               COUNT(*) FILTER (WHERE {coluna} = 0),
               COUNT(*) FILTER (WHERE {coluna} IS NULL)
        FROM {tabela}
    """
    mn, mx, sm, neg, zer, nul = con.execute(q).fetchone()
    registrar(
        familia,
        f"dominio de {coluna}",
        "NEGATIVOS PRESENTES" if neg else ("OK" if nul == 0 else "NULL PRESENTE"),
        f"min={mn:,} max={mx:,} soma={sm:,} negativos={neg:,} zeros={zer:,} nulos={nul:,}",
    )


def semantica_qt_curso(con) -> None:
    """IND-D-02: SUM(qt_curso)=45.776 e COUNT(DISTINCT co_curso)=46.150 sao conceitos diferentes."""
    vals = con.execute(f"SELECT qt_curso, COUNT(*) FROM {CURSOS} GROUP BY 1 ORDER BY 1").fetchall()
    registrar(
        "qt_curso",
        "valores distintos de qt_curso e frequencia",
        "; ".join(f"{v}={n:,}" for v, n in vals),
    )
    q = f"""
        WITH por_curso AS (
            SELECT co_curso, SUM(qt_curso) AS s FROM {CURSOS} GROUP BY 1
        )
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE s = 0),
               COUNT(*) FILTER (WHERE s = 1),
               COUNT(*) FILTER (WHERE s > 1),
               MAX(s)
        FROM por_curso
    """
    n, zero, um, mais, mx = con.execute(q).fetchone()
    registrar(
        "qt_curso",
        "SUM(qt_curso) agrupado por co_curso",
        f"{n:,} cursos distintos; soma=0 em {zero:,}; soma=1 em {um:,}; soma>1 em {mais:,}",
        f"max_soma_por_curso={mx}",
    )
    q = f"""
        SELECT tp_dimensao,
               COUNT(DISTINCT co_curso) FILTER (WHERE qt_curso > 0) AS cursos_marcados,
               SUM(qt_curso) AS soma
        FROM {CURSOS} GROUP BY 1 ORDER BY 3 DESC
    """
    for dim, marc, soma in con.execute(q).fetchall():
        registrar(
            "qt_curso",
            f"por tp_dimensao: {dim}",
            f"cursos_com_marca={marc:,} SUM(qt_curso)={soma:,}",
        )
    # Os 374 cursos da diferenca aparecem em qual dimensao?
    q = f"""
        WITH por_curso AS (
            SELECT co_curso, SUM(qt_curso) AS s FROM {CURSOS} GROUP BY 1
        )
        SELECT c.tp_dimensao, COUNT(DISTINCT c.co_curso)
        FROM {CURSOS} c JOIN por_curso p USING (co_curso)
        WHERE p.s = 0
        GROUP BY 1 ORDER BY 2 DESC
    """
    for dim, n in con.execute(q).fetchall():
        registrar("qt_curso", f"cursos com SUM(qt_curso)=0 presentes em: {dim}", f"{n:,} cursos")


def unidades_territoriais(con) -> None:
    """IND-R-02: natureza real das 5.599 linhas de `municipio` e denominacao correta."""
    # Os grupos precisam ser MUTUAMENTE EXCLUSIVOS: 9900000 termina em '00000' E e sentinela
    # de exterior, entao contar "termina em 00000" + "exterior" o soma duas vezes e devolve
    # 5.570 em vez de 5.571.
    q = """
        SELECT COUNT(*),
               COUNT(DISTINCT codigo_municipio_dv),
               COUNT(*) FILTER (WHERE right(codigo_municipio_dv::text, 5) = '00000'
                                  AND codigo_municipio_dv::text NOT LIKE '99%'),
               COUNT(*) FILTER (WHERE codigo_municipio_dv::text LIKE '99%'),
               COUNT(*) FILTER (WHERE right(codigo_municipio_dv::text, 5) <> '00000'
                                  AND codigo_municipio_dv::text NOT LIKE '99%')
        FROM municipio
    """
    tot, dist, ign, ext, reais = con.execute(q).fetchone()
    registrar(
        "municipio",
        "composicao da tabela",
        f"linhas={tot:,} codigos_distintos={dist:,} sentinelas_ignorado={ign} exterior={ext}",
        f"unidades_reais={reais:,} (grupos mutuamente exclusivos: {ign} + {ext} + {reais} = {tot:,})",
    )
    q = """
        SELECT cd_uf, COUNT(*) FROM municipio
        WHERE right(codigo_municipio_dv::text, 5) <> '00000'
          AND codigo_municipio_dv::text NOT IN ('9900000', '9999999')
        GROUP BY 1 ORDER BY 1
    """
    linhas = con.execute(q).fetchall()
    registrar(
        "municipio",
        "unidades reais por UF",
        f"{len(linhas)} UFs; total={sum(n for _, n in linhas):,}",
        "; ".join(f"{u}={n}" for u, n in linhas),
    )
    # Unidades que NAO sao municipio no sentido estrito.
    for cod, rotulo in (
        ("2605459", "Fernando de Noronha (distrito estadual de PE)"),
        ("5300108", "Brasilia / Distrito Federal"),
    ):
        r = con.execute(
            "SELECT nome_municipio, cd_uf FROM municipio WHERE codigo_municipio_dv::text = ?",
            [cod],
        ).fetchall()
        registrar(
            "municipio",
            f"unidade especial {cod} - {rotulo}",
            "PRESENTE" if r else "AUSENTE",
            str(r),
        )
    # Cobertura do Censo sobre essas unidades.
    q = f"""
        SELECT
          (SELECT COUNT(DISTINCT co_municipio_ies) FROM {IES}),
          (SELECT COUNT(DISTINCT co_municipio) FROM {CURSOS}
             WHERE regexp_full_match(co_municipio, '[0-9]{{7}}'))
    """
    sede, oferta = con.execute(q).fetchone()
    registrar(
        "municipio",
        "cobertura do Censo sobre as unidades territoriais",
        f"sede_de_IES={sede:,} local_de_oferta={oferta:,}",
    )


def main() -> int:
    if not BANCO.exists():
        print(f"ERRO: {BANCO} nao existe. Rode o ETL antes.", file=sys.stderr)
        return 2
    con = duckdb.connect(str(BANCO), read_only=True)

    # ------------------------------------------------------------------ qt_vg_*
    dominio(con, "qt_vg_*", CURSOS, "qt_vg_total")
    fechamento(
        con,
        "qt_vg_*",
        CURSOS,
        "qt_vg_total",
        ["qt_vg_total_diurno", "qt_vg_total_noturno", "qt_vg_total_ead"],
        "turno/modalidade",
    )
    fechamento(
        con,
        "qt_vg_*",
        CURSOS,
        "qt_vg_total",
        ["qt_vg_nova", "qt_vg_proc_seletivo", "qt_vg_remanesc", "qt_vg_prog_especial"],
        "tipo de vaga",
    )
    fechamento(
        con,
        "qt_vg_*",
        CURSOS,
        "qt_vg_nova",
        ["qt_vg_proc_seletivo", "qt_vg_remanesc", "qt_vg_prog_especial"],
        "hip.: nova = soma dos tipos",
    )

    # ------------------------------------------------------------- qt_inscrito_*
    dominio(con, "qt_inscrito_*", CURSOS, "qt_inscrito_total")
    fechamento(
        con,
        "qt_inscrito_*",
        CURSOS,
        "qt_inscrito_total",
        ["qt_inscrito_total_diurno", "qt_inscrito_total_noturno", "qt_inscrito_total_ead"],
        "turno/modalidade",
    )
    fechamento(
        con,
        "qt_inscrito_*",
        CURSOS,
        "qt_inscrito_total",
        [
            "qt_insc_vg_nova",
            "qt_insc_proc_seletivo",
            "qt_insc_vg_remanesc",
            "qt_insc_vg_prog_especial",
        ],
        "tipo de vaga",
    )
    fechamento(
        con,
        "qt_inscrito_*",
        CURSOS,
        "qt_insc_vg_nova",
        ["qt_insc_proc_seletivo", "qt_insc_vg_remanesc", "qt_insc_vg_prog_especial"],
        "hip.: insc_vg_nova = soma dos tipos",
    )

    # ------------------------------------------------------- qt_doc_ex_* (grain IES)
    dominio(con, "qt_doc_ex_*", IES, "qt_doc_total")
    fechamento(con, "qt_doc_ex_*", IES, "qt_doc_total", ["qt_doc_exe"], "qt_doc_exe identica?")
    fechamento(
        con, "qt_doc_ex_*", IES, "qt_doc_total", ["qt_doc_ex_femi", "qt_doc_ex_masc"], "sexo"
    )
    fechamento(
        con,
        "qt_doc_ex_*",
        IES,
        "qt_doc_total",
        [
            "qt_doc_ex_sem_grad",
            "qt_doc_ex_grad",
            "qt_doc_ex_esp",
            "qt_doc_ex_mest",
            "qt_doc_ex_dout",
        ],
        "titulacao",
    )
    fechamento(
        con,
        "qt_doc_ex_*",
        IES,
        "qt_doc_total",
        ["qt_doc_ex_int", "qt_doc_ex_parc", "qt_doc_ex_hor"],
        "regime de trabalho",
    )
    fechamento(
        con,
        "qt_doc_ex_*",
        IES,
        "qt_doc_ex_int",
        ["qt_doc_ex_int_de", "qt_doc_ex_int_sem_de"],
        "integral = DE + sem DE",
    )
    fechamento(
        con,
        "qt_doc_ex_*",
        IES,
        "qt_doc_total",
        [
            "qt_doc_ex_0_29",
            "qt_doc_ex_30_34",
            "qt_doc_ex_35_39",
            "qt_doc_ex_40_44",
            "qt_doc_ex_45_49",
            "qt_doc_ex_50_54",
            "qt_doc_ex_55_59",
            "qt_doc_ex_60_mais",
        ],
        "faixa etaria",
    )
    fechamento(
        con,
        "qt_doc_ex_*",
        IES,
        "qt_doc_total",
        [
            "qt_doc_ex_branca",
            "qt_doc_ex_preta",
            "qt_doc_ex_parda",
            "qt_doc_ex_amarela",
            "qt_doc_ex_indigena",
            "qt_doc_ex_cor_nd",
        ],
        "cor/raca",
    )
    fechamento(
        con, "qt_doc_ex_*", IES, "qt_doc_total", ["qt_doc_ex_bra", "qt_doc_ex_est"], "nacionalidade"
    )
    contencao(con, "qt_doc_ex_*", IES, "qt_doc_ex_com_deficiencia", "qt_doc_total", "deficiencia")

    # --------------------------------------------------------- qt_tec_* (grain IES)
    dominio(con, "qt_tec_*", IES, "qt_tec_total")
    fechamento(
        con,
        "qt_tec_*",
        IES,
        "qt_tec_total",
        [
            "qt_tec_fundamental_incomp_fem",
            "qt_tec_fundamental_incomp_masc",
            "qt_tec_fundamental_comp_fem",
            "qt_tec_fundamental_comp_masc",
            "qt_tec_medio_fem",
            "qt_tec_medio_masc",
            "qt_tec_superior_fem",
            "qt_tec_superior_masc",
            "qt_tec_especializacao_fem",
            "qt_tec_especializacao_masc",
            "qt_tec_mestrado_fem",
            "qt_tec_mestrado_masc",
            "qt_tec_doutorado_fem",
            "qt_tec_doutorado_masc",
        ],
        "escolaridade x sexo",
    )

    # ------------------------------------------------------------------ qt_*_financ*
    for base in ("ing", "mat", "conc"):
        fam = f"qt_{base}_financ*"
        contencao(con, fam, CURSOS, f"qt_{base}_financ", f"qt_{base}", "financiado <= total")
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}_financ",
            [f"qt_{base}_financ_reemb", f"qt_{base}_financ_nreemb"],
            "financ = reembolsavel + nao reembolsavel",
        )
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}_financ_reemb",
            [f"qt_{base}_fies", f"qt_{base}_financ_reemb_outros"],
            "hip.: reemb = fies + outros",
        )
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}_financ_reemb",
            [f"qt_{base}_fies", f"qt_{base}_rpfies", f"qt_{base}_financ_reemb_outros"],
            "hip.: reemb = fies + rpfies + outros",
        )
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}_financ_nreemb",
            [
                f"qt_{base}_prounii",
                f"qt_{base}_prounip",
                f"qt_{base}_nrpfies",
                f"qt_{base}_financ_nreemb_outros",
            ],
            "hip.: nreemb = prouni_int + prouni_parc + nrpfies + outros",
        )

    # ---------------------------------------------------------------------- qt_*_rv*
    RV = [
        "rvredepublica",
        "rvppi",
        "rvquilo",
        "rvrefu",
        "rvpovt",
        "rvpdef",
        "rvsocial_rf",
        "rvidoso",
        "rvintern",
        "rvmedal",
        "rvtrans",
        "rvoutros",
    ]
    for base in ("ing", "mat", "conc"):
        fam = f"qt_{base}_rv*"
        contencao(con, fam, CURSOS, f"qt_{base}_reserva_vaga", f"qt_{base}", "reserva <= total")
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}_reserva_vaga",
            [f"qt_{base}_{s}" for s in RV],
            "reserva = soma dos 12 subtipos",
        )

    # ---------------------------------------------------------------------- qt_sit_*
    for c in ("qt_sit_trancada", "qt_sit_desvinculado", "qt_sit_transferido", "qt_sit_falecido"):
        dominio(con, "qt_sit_*", CURSOS, c)
    fechamento(
        con,
        "qt_sit_*",
        CURSOS,
        "qt_mat",
        ["qt_sit_trancada", "qt_sit_desvinculado", "qt_sit_transferido", "qt_sit_falecido"],
        "hip.: situacoes fecham com qt_mat",
    )
    contencao(
        con,
        "qt_sit_*",
        CURSOS,
        "(qt_sit_trancada + qt_sit_desvinculado + qt_sit_transferido + qt_sit_falecido)",
        "qt_mat",
        "situacoes <= matriculas",
    )

    # ------------------------- EXTRA (fora da lista autorizada, necessario ao IND-R-07)
    for base in ("ing", "mat", "conc"):
        fam = f"qt_{base}_* (perfil)"
        fechamento(con, fam, CURSOS, f"qt_{base}", [f"qt_{base}_fem", f"qt_{base}_masc"], "sexo")
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}",
            [
                f"qt_{base}_branca",
                f"qt_{base}_preta",
                f"qt_{base}_parda",
                f"qt_{base}_amarela",
                f"qt_{base}_indigena",
                f"qt_{base}_cornd",
            ],
            "cor/raca",
        )
        faixas = ["0_17", "18_24", "25_29", "30_34", "35_39", "40_49", "50_59", "60_mais"]
        fechamento(
            con, fam, CURSOS, f"qt_{base}", [f"qt_{base}_{f}" for f in faixas], "faixa etaria"
        )
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}",
            [f"qt_{base}_nacbras", f"qt_{base}_nacestrang"],
            "nacionalidade",
        )
        fechamento(
            con, fam, CURSOS, f"qt_{base}", [f"qt_{base}_diurno", f"qt_{base}_noturno"], "turno"
        )
        fechamento(
            con,
            fam,
            CURSOS,
            f"qt_{base}",
            [
                f"qt_{base}_procescpublica",
                f"qt_{base}_procescprivada",
                f"qt_{base}_procnaoinformada",
            ],
            "procedencia escolar",
        )

    # ------------------------------------------------ semantica de qt_curso e do territorio
    semantica_qt_curso(con)
    unidades_territoriais(con)

    con.close()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["familia", "teste", "resultado", "detalhe"])
        w.writeheader()
        w.writerows(resultados)
    print(f"\n{len(resultados)} verificacoes -> {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
