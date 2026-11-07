#!/usr/bin/env python3
"""Auditoria da Fase 9 (Matriculas e Fluxo): o que as razoes e os perfis exigem do dado.

Le SOMENTE o DuckDB local (ADR-0003).

Perguntas, todas previas a servir IND-R-07/08/09/10/11 pela API:

1. INVENTARIO. Quais colunas de fluxo existem de fato em `cursos`, por familia.
2. PERFIL (IND-R-07). As cinco decomposicoes continuam particao exata de qt_mat/qt_ing/qt_conc,
   linha a linha? (Particao por linha vale em qualquer agregacao.)
3. CONTENCAO (IND-R-08/09). qt_*_financ e qt_*_reserva_vaga <= coluna-total em toda linha?
4. RAZOES POR VAGA (IND-R-10/11). No presencial: numerador e denominador coexistem na linha?
   Quanto do numerador vem de linhas com vaga zero? Quantas linhas excedem 1?
5. CELULAS PEQUENAS. Quantas unidades tem denominador pequeno em cada nivel.
6. FORMA DE INGRESSO (pendencia de IND-D-04). Alguma hipotese de decomposicao fecha?
7. SITUACOES (IND-Q-02). qt_sit_* continua sem denominador valido?
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics" / "2026-10-07_fluxo.csv"

CURSOS = "inep_educacao_superior_cursos"
PRESENCIAL = "Cursos presenciais ofertados no Brasil"
EAD_NACIONAL = "Cursos a distância com dimensão de dados somente a nível Brasil"
COM_TERRITORIO = "regexp_full_match(co_municipio, '[0-9]{7}')"
BASES = ("mat", "ing", "conc")

PERFIS: dict[str, tuple[str, ...]] = {
    "sexo": ("fem", "masc"),
    "cor_raca": ("branca", "preta", "parda", "amarela", "indigena", "cornd"),
    "faixa_etaria": ("0_17", "18_24", "25_29", "30_34", "35_39", "40_49", "50_59", "60_mais"),
    "nacionalidade": ("nacbras", "nacestrang"),
    "procedencia_escolar": ("procescpublica", "procescprivada", "procnaoinformada"),
}

# Hipoteses de decomposicao de qt_ing. Nenhuma e assumida: so vale a que fechar.
HIPOTESES_INGRESSO: dict[str, tuple[str, ...]] = {
    "tipo de vaga (vg_nova + vg_remanesc + vg_prog_especial)": (
        "qt_ing_vg_nova",
        "qt_ing_vg_remanesc",
        "qt_ing_vg_prog_especial",
    ),
    "tipo de vaga + outra_forma": (
        "qt_ing_vg_nova",
        "qt_ing_vg_remanesc",
        "qt_ing_vg_prog_especial",
        "qt_ing_outra_forma",
    ),
    "proc_seletivo + outra_forma": ("qt_ing_proc_seletivo", "qt_ing_outra_forma"),
    "tipo de vaga + proc_seletivo + outra_forma": (
        "qt_ing_vg_nova",
        "qt_ing_proc_seletivo",
        "qt_ing_vg_remanesc",
        "qt_ing_vg_prog_especial",
        "qt_ing_outra_forma",
    ),
    "tipos de selecao (6 colunas) = qt_ing": (
        "qt_ing_vestibular",
        "qt_ing_enem",
        "qt_ing_avaliacao_seriada",
        "qt_ing_selecao_simplifica",
        "qt_ing_egr",
        "qt_ing_outro_tipo_selecao",
    ),
}
SELECAO = HIPOTESES_INGRESSO["tipos de selecao (6 colunas) = qt_ing"]

resultados: list[dict[str, str]] = []


def registrar(bloco: str, teste: str, resultado: str, detalhe: str = "") -> None:
    resultados.append({"bloco": bloco, "teste": teste, "resultado": resultado, "detalhe": detalhe})
    print(f"[{bloco}] {teste}\n    -> {resultado}" + (f"  ({detalhe})" if detalhe else ""))


def n(valor: int | None) -> str:
    return f"{int(valor or 0):,}".replace(",", ".")


def fechamento(
    con, bloco: str, teste: str, total: str, partes: tuple[str, ...], onde: str = "TRUE"
) -> None:
    soma = " + ".join(partes)
    acima, abaixo, s_total, s_partes = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE {soma} > {total}),
                   COUNT(*) FILTER (WHERE {soma} < {total}),
                   SUM({total}), SUM({soma})
            FROM {CURSOS} WHERE {onde}"""
    ).fetchone()
    veredito = "PARTICAO EXATA" if acima == 0 and abaixo == 0 else "NAO FECHA"
    registrar(
        bloco,
        teste,
        veredito,
        f"total={n(s_total)} partes={n(s_partes)} linhas acima={n(acima)} abaixo={n(abaixo)}",
    )


def main() -> int:
    if not BANCO.is_file():
        print(f"Camada analitica ausente: {BANCO}", file=sys.stderr)
        return 1
    con = duckdb.connect(str(BANCO), read_only=True)

    # 1. Inventario
    colunas = [
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "ORDER BY ordinal_position",
            [CURSOS],
        ).fetchall()
    ]
    familias: dict[str, int] = {}
    for c in colunas:
        m = re.match(r"qt_(mat|ing|conc|vg|inscrito|insc|sit|curso)", c)
        if m:
            familias[m.group(1)] = familias.get(m.group(1), 0) + 1
    registrar(
        "inventario", "colunas por familia", str(familias), f"{len(colunas)} colunas no total"
    )
    anos = con.execute(f"SELECT DISTINCT nu_ano_censo FROM {CURSOS}").fetchall()
    registrar("inventario", "anos presentes", str([a[0] for a in anos]))

    # 2. Perfil
    for base in BASES:
        for perfil, sufixos in PERFIS.items():
            fechamento(
                con,
                "perfil",
                f"qt_{base} por {perfil}",
                f"qt_{base}",
                tuple(f"qt_{base}_{s}" for s in sufixos),
            )

    # 3. Contencao
    for base in BASES:
        for sub in ("financ", "reserva_vaga"):
            viol, parte, total = con.execute(
                f"""SELECT COUNT(*) FILTER (WHERE qt_{base}_{sub} > qt_{base}),
                           SUM(qt_{base}_{sub}), SUM(qt_{base}) FROM {CURSOS}"""
            ).fetchone()
            registrar(
                "contencao",
                f"qt_{base}_{sub} <= qt_{base}",
                f"{n(viol)} violacoes",
                f"{n(parte)} de {n(total)} = {parte / total * 100:.2f}%",
            )

    # 4. Razoes por vaga, no presencial
    for nome, num in (
        ("IND-R-10 ingressos/vaga", "qt_ing"),
        ("IND-R-11 inscricoes/vaga", "qt_inscrito_total"),
    ):
        r = con.execute(
            f"""SELECT COUNT(*), SUM({num}), SUM(qt_vg_total),
                       COUNT(*) FILTER (WHERE qt_vg_total = 0 AND {num} > 0),
                       SUM({num}) FILTER (WHERE qt_vg_total = 0),
                       COUNT(*) FILTER (WHERE qt_vg_total > 0 AND {num} > qt_vg_total),
                       COUNT(*) FILTER (WHERE qt_vg_total > 0),
                       COUNT(*) FILTER (WHERE NOT {COM_TERRITORIO})
                FROM {CURSOS} WHERE tp_dimensao = ?""",
            [PRESENCIAL],
        ).fetchone()
        registrar(
            "razao",
            f"{nome} — presencial",
            f"{n(r[1])} / {n(r[2])} = {r[1] / r[2]:.4f}",
            f"{n(r[0])} linhas; sem territorio={n(r[7])}; vaga=0 com numerador>0: {n(r[3])} linhas "
            f"somando {n(r[4])} ({(r[4] or 0) / r[1] * 100:.2f}% do numerador); "
            f"numerador>vaga em {n(r[5])} de {n(r[6])} linhas com vaga",
        )
    r = con.execute(
        f"SELECT SUM(qt_inscrito_total), SUM(qt_vg_total), SUM(qt_ing) FROM {CURSOS} WHERE tp_dimensao = ?",
        [EAD_NACIONAL],
    ).fetchone()
    registrar(
        "razao",
        "IND-R-11 — EAD somente a nivel Brasil",
        f"{n(r[0])} / {n(r[1])} = {r[0] / r[1]:.4f}",
        f"qt_ing nessa dimensao = {n(r[2])}",
    )
    for rede, ing, vg, insc in con.execute(
        f"""SELECT tp_rede, SUM(qt_ing), SUM(qt_vg_total), SUM(qt_inscrito_total)
            FROM {CURSOS} WHERE tp_dimensao = ? GROUP BY 1 ORDER BY 1""",
        [PRESENCIAL],
    ).fetchall():
        registrar(
            "razao",
            f"presencial, rede {rede}",
            f"ing/vaga={ing / vg:.4f} insc/vaga={insc / vg:.4f}",
            f"ing={n(ing)} vagas={n(vg)} inscricoes={n(insc)}",
        )

    # 5. Celulas pequenas
    for nivel, col in (("uf", "sg_uf"), ("municipio", "co_municipio")):
        for base in BASES:
            r = con.execute(
                f"""WITH a AS (SELECT {col} AS k, SUM(qt_{base}) AS d FROM {CURSOS}
                               WHERE {COM_TERRITORIO} GROUP BY 1)
                    SELECT COUNT(*), MIN(d), COUNT(*) FILTER (WHERE d = 0),
                           COUNT(*) FILTER (WHERE d BETWEEN 1 AND 9),
                           COUNT(*) FILTER (WHERE d BETWEEN 10 AND 29) FROM a"""
            ).fetchone()
            registrar(
                "celulas",
                f"denominador qt_{base} por {nivel} (presencial + polo)",
                f"{n(r[0])} unidades; minimo {n(r[1])}",
                f"zero={n(r[2])} 1-9={n(r[3])} 10-29={n(r[4])}",
            )
        r = con.execute(
            f"""WITH a AS (SELECT {col} AS k, SUM(qt_vg_total) AS d, SUM(qt_ing) AS i FROM {CURSOS}
                           WHERE tp_dimensao = ? AND {COM_TERRITORIO} GROUP BY 1)
                SELECT COUNT(*), COUNT(*) FILTER (WHERE d = 0),
                       COUNT(*) FILTER (WHERE d = 0 AND i > 0),
                       COUNT(*) FILTER (WHERE d BETWEEN 1 AND 29),
                       COUNT(*) FILTER (WHERE d > 0 AND i > d) FROM a""",
            [PRESENCIAL],
        ).fetchone()
        registrar(
            "celulas",
            f"vagas presenciais por {nivel}",
            f"{n(r[0])} unidades",
            f"vaga=0: {n(r[1])} (com ingresso: {n(r[2])}); vagas 1-29: {n(r[3])}; ingressos>vagas: {n(r[4])}",
        )

    # 6. Forma de ingresso
    for nome, partes in HIPOTESES_INGRESSO.items():
        fechamento(con, "ingresso", f"qt_ing = {nome}", "qt_ing", partes)
    fechamento(
        con, "ingresso", "qt_ing_vg_nova = tipos de selecao (6 colunas)", "qt_ing_vg_nova", SELECAO
    )
    fechamento(
        con,
        "ingresso",
        "qt_ing_proc_seletivo = tipos de selecao (6 colunas)",
        "qt_ing_proc_seletivo",
        SELECAO,
    )
    somas = con.execute(
        "SELECT "
        + ", ".join(
            f"SUM({c})"
            for c in sorted({c for p in HIPOTESES_INGRESSO.values() for c in p} | {"qt_ing"})
        )
        + f" FROM {CURSOS}"
    ).fetchone()
    nomes = sorted({c for p in HIPOTESES_INGRESSO.values() for c in p} | {"qt_ing"})
    registrar(
        "ingresso",
        "somas nacionais",
        "; ".join(f"{c}={n(v)}" for c, v in zip(nomes, somas, strict=True)),
    )

    # 7. Situacoes
    sit = "qt_sit_trancada + qt_sit_desvinculado + qt_sit_transferido + qt_sit_falecido"
    r = con.execute(
        f"""SELECT SUM({sit}), SUM(qt_mat), COUNT(*) FILTER (WHERE {sit} > qt_mat),
                   SUM(qt_sit_trancada), SUM(qt_sit_desvinculado), SUM(qt_sit_transferido),
                   SUM(qt_sit_falecido) FROM {CURSOS}"""
    ).fetchone()
    registrar(
        "situacoes",
        "soma de qt_sit_* contra qt_mat",
        f"{n(r[0])} contra {n(r[1])}; excede em {n(r[2])} linhas",
        f"trancada={n(r[3])} desvinculado={n(r[4])} transferido={n(r[5])} falecido={n(r[6])}",
    )

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bloco", "teste", "resultado", "detalhe"])
        w.writeheader()
        w.writerows(resultados)
    print(f"\n{len(resultados)} testes gravados em {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
