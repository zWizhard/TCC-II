#!/usr/bin/env python3
"""Auditoria da Fase 11 (Comparacoes): o que comparar territorios lado a lado exige do dado.

Le SOMENTE o DuckDB local (ADR-0003).

Perguntas, todas previas a servir qualquer comparacao:

1. FECHAMENTO. As metricas comparadas, agregadas por regiao e por UF, somam o total nacional
   territorializavel? A populacao reagregada por UF fecha com a de 2024?
2. REFERENCIA. Quais sao os valores do Brasil nas mesmas definicoes (a coluna de referencia)?
3. PORTE. Quao diferentes sao as unidades de um mesmo nivel — e, portanto, o quanto um valor
   absoluto so mede tamanho?
4. ORDEM. A ordem das UFs por matriculas coincide com a ordem por matriculas por 100 mil
   habitantes? Se nao, uma lista ordenada por valor absoluto induz a leitura errada.
5. MUNICIPIO. Quantas unidades tem oferta sem sede de IES, e quantas tem base pequena demais
   para uma proporcao estavel?
6. REDE. As proporcoes comparadas dependem da rede?
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics" / "2026-10-07_comparacoes.csv"

CURSOS = "inep_educacao_superior_cursos"
IES = "inep_educacao_superior_ies"
PRESENCIAL = "Cursos presenciais ofertados no Brasil"
POLO = "Cursos a distância ofertados no Brasil"
# Universo da comparacao: as duas dimensoes com municipio, so linhas com territorio.
UNIVERSO = (
    f"nu_ano_censo = '2024' AND tp_dimensao IN ('{PRESENCIAL}', '{POLO}') "
    "AND regexp_full_match(co_municipio, '[0-9]{7}')"
)
REAL = "right(m.codigo_municipio_dv, 5) <> '00000' AND m.codigo_municipio_dv <> '9999999'"
POPULACAO = f"""
    SELECT m.codigo_municipio_dv AS codigo, m.cd_uf, CAST(p.populacao AS BIGINT) AS populacao
    FROM municipio m
    JOIN ibge_populacao_estimada p ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024'
    WHERE {REAL}
"""
METRICAS = f"""
    CAST(SUM(qt_mat) AS BIGINT) AS mat,
    CAST(SUM(qt_ing) AS BIGINT) AS ing,
    CAST(SUM(qt_conc) AS BIGINT) AS conc,
    CAST(coalesce(SUM(qt_curso) FILTER (WHERE tp_dimensao = '{PRESENCIAL}'), 0) AS BIGINT) AS cur,
    CAST(coalesce(SUM(qt_mat) FILTER (WHERE tp_rede = 'Privada'), 0) AS BIGINT) AS priv,
    CAST(coalesce(SUM(qt_mat) FILTER (WHERE tp_dimensao = '{POLO}'), 0) AS BIGINT) AS ead
"""

resultados: list[dict[str, str]] = []


def registrar(bloco: str, teste: str, resultado: str, detalhe: str = "") -> None:
    resultados.append({"bloco": bloco, "teste": teste, "resultado": resultado, "detalhe": detalhe})
    print(f"[{bloco}] {teste}\n    -> {resultado}" + (f"  ({detalhe})" if detalhe else ""))


def n(valor: float | None) -> str:
    return f"{int(valor or 0):,}".replace(",", ".")


def d(valor: float | None, casas: int = 1) -> str:
    return (
        "nulo"
        if valor is None
        else f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )


def main() -> int:
    if not BANCO.is_file():
        print(f"Camada analitica ausente: {BANCO}", file=sys.stderr)
        return 1
    con = duckdb.connect(str(BANCO), read_only=True)

    # ------------------------------------------------------------------ 1. fechamento
    brasil = con.execute(f"SELECT {METRICAS} FROM {CURSOS} WHERE {UNIVERSO}").fetchone()
    for rotulo, coluna, esperado in (("regiao", "co_regiao", 5), ("UF", "sg_uf", 27)):
        grupos = con.execute(
            f"SELECT {coluna}, {METRICAS} FROM {CURSOS} WHERE {UNIVERSO} GROUP BY 1"
        ).fetchall()
        somas = tuple(sum(g[i] for g in grupos) for i in range(1, 7))
        registrar(
            "fechamento",
            f"cursos por {rotulo}: grupos e somas contra o total territorializavel",
            "FECHA" if (len(grupos), somas) == (esperado, tuple(brasil)) else "NAO FECHA",
            f"grupos={len(grupos)} mat={n(somas[0])} ing={n(somas[1])} conc={n(somas[2])} "
            f"cursos presenciais={n(somas[3])} mat privada={n(somas[4])} mat polo EAD={n(somas[5])}",
        )

    ies_br = con.execute(
        f"""SELECT COUNT(*), CAST(SUM(qt_doc_total) AS BIGINT), CAST(SUM(qt_doc_ex_dout) AS BIGINT)
            FROM {IES} WHERE nu_ano_censo = '2024'"""
    ).fetchone()
    for rotulo, coluna, esperado in (("regiao", "co_regiao_ies", 5), ("UF", "sg_uf_ies", 27)):
        grupos = con.execute(
            f"""SELECT {coluna}, COUNT(*), CAST(SUM(qt_doc_total) AS BIGINT),
                       CAST(SUM(qt_doc_ex_dout) AS BIGINT)
                FROM {IES} WHERE nu_ano_censo = '2024' GROUP BY 1"""
        ).fetchall()
        somas = tuple(sum(g[i] for g in grupos) for i in range(1, 4))
        registrar(
            "fechamento",
            f"ies por {rotulo} (sede): grupos e somas contra o total",
            "FECHA" if (len(grupos), somas) == (esperado, tuple(ies_br)) else "NAO FECHA",
            f"grupos={len(grupos)} ies={n(somas[0])} docentes={n(somas[1])} doutores={n(somas[2])}",
        )

    pop_unidades, pop_codigos, pop_total, pop_ufs = con.execute(
        f"""SELECT COUNT(*), COUNT(DISTINCT codigo), SUM(populacao), COUNT(DISTINCT cd_uf)
            FROM ({POPULACAO})"""
    ).fetchone()
    registrar(
        "fechamento",
        "populacao 2024 pela ponte `municipio`: 1 linha por unidade real",
        "FECHA" if pop_unidades == pop_codigos == 5571 and pop_ufs == 27 else "NAO FECHA",
        f"linhas={n(pop_unidades)} codigos distintos={n(pop_codigos)} UFs={pop_ufs} "
        f"populacao={n(pop_total)}",
    )
    codigos_divergentes = con.execute(
        f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT co_uf, sg_uf, co_regiao FROM {CURSOS} WHERE {UNIVERSO}
            ) c
            LEFT JOIN (
                SELECT DISTINCT co_uf_ies, sg_uf_ies, CAST(co_regiao_ies AS VARCHAR) AS reg
                FROM {IES} WHERE nu_ano_censo = '2024'
            ) i ON i.sg_uf_ies = c.sg_uf
            LEFT JOIN (SELECT DISTINCT cd_uf FROM municipio m WHERE {REAL}) m ON m.cd_uf = c.co_uf
            WHERE i.sg_uf_ies IS NULL OR m.cd_uf IS NULL
               OR CAST(i.co_uf_ies AS VARCHAR) <> c.co_uf OR i.reg <> c.co_regiao"""
    ).fetchone()[0]
    registrar(
        "fechamento",
        "codigo de UF e de regiao identicos em cursos, ies e municipio",
        "IDENTICOS" if codigos_divergentes == 0 else "DIVERGEM",
        f"UFs divergentes={codigos_divergentes}",
    )

    # ------------------------------------------------------------------ 2. referencia
    mat, _ing, _conc, _cur, priv, ead = brasil
    registrar(
        "referencia",
        "Brasil, nas definicoes da comparacao (presencial + polo EAD, com municipio)",
        f"mat/100 mil hab={d(mat / pop_total * 100000)} privada={d(priv / mat * 100, 2)}% "
        f"EAD={d(ead / mat * 100, 2)}% doutores={d(ies_br[2] / ies_br[1] * 100, 2)}%",
        f"mat={n(mat)} privada={n(priv)} polo EAD={n(ead)} populacao={n(pop_total)} "
        f"docentes={n(ies_br[1])} doutores={n(ies_br[2])}",
    )

    # ------------------------------------------------------------------ 3. porte
    por_uf = con.execute(
        f"""WITH c AS (SELECT co_uf AS cd_uf, any_value(sg_uf) AS uf, {METRICAS}
                       FROM {CURSOS} WHERE {UNIVERSO} GROUP BY 1),
                 p AS (SELECT cd_uf, SUM(populacao) AS pop FROM ({POPULACAO}) GROUP BY 1)
            SELECT c.uf, c.mat, p.pop, c.mat / p.pop * 100000, c.priv / c.mat * 100,
                   c.ead / c.mat * 100
            FROM c JOIN p USING (cd_uf)"""
    ).fetchall()
    pops = sorted(r[2] for r in por_uf)
    mats = sorted(r[1] for r in por_uf)
    registrar(
        "porte",
        "UF: razao entre a maior e a menor",
        f"populacao {d(pops[-1] / pops[0])}x; matriculas {d(mats[-1] / mats[0])}x",
        f"populacao de {n(pops[0])} a {n(pops[-1])}; matriculas de {n(mats[0])} a {n(mats[-1])}",
    )
    menor, mediana, maior, pequenas = con.execute(
        f"""WITH c AS (SELECT co_municipio AS codigo FROM {CURSOS} WHERE {UNIVERSO} GROUP BY 1)
            SELECT MIN(populacao), MEDIAN(populacao), MAX(populacao),
                   COUNT(*) FILTER (WHERE populacao < 10000)
            FROM c JOIN ({POPULACAO}) p USING (codigo)"""
    ).fetchone()
    registrar(
        "porte",
        "municipio com oferta: populacao",
        f"de {n(menor)} a {n(maior)} habitantes ({d(maior / menor, 0)}x); mediana {n(mediana)}",
        f"com menos de 10 mil habitantes={n(pequenas)}",
    )

    # ------------------------------------------------------------------ 4. ordem
    abs_ord = [r[0] for r in sorted(por_uf, key=lambda r: -r[1])]
    rel_ord = [r[0] for r in sorted(por_uf, key=lambda r: -r[3])]
    desloc = {uf: abs(abs_ord.index(uf) - rel_ord.index(uf)) for uf in abs_ord}
    k = len(abs_ord)
    spearman = 1 - 6 * sum(v * v for v in desloc.values()) / (k * (k * k - 1))
    registrar(
        "ordem",
        "UF: ordem por matriculas x ordem por matriculas por 100 mil habitantes",
        f"correlacao de postos (Spearman) = {d(spearman, 2)}",
        f"UFs que mudam 5 ou mais posicoes={sum(1 for v in desloc.values() if v >= 5)} de {k}; "
        f"maior deslocamento={max(desloc.values())} posicoes; "
        f"1a em valor absoluto={abs_ord[0]} ({rel_ord.index(abs_ord[0]) + 1}a na razao); "
        f"1a na razao={rel_ord[0]} ({abs_ord.index(rel_ord[0]) + 1}a em valor absoluto)",
    )
    for rotulo, i in (("participacao da rede privada", 4), ("participacao da EAD", 5)):
        valores = sorted((r[i], r[0]) for r in por_uf)
        registrar(
            "ordem",
            f"UF: amplitude da {rotulo} nas matriculas",
            f"de {d(valores[0][0])}% ({valores[0][1]}) a {d(valores[-1][0])}% ({valores[-1][1]})",
        )

    # ------------------------------------------------------------------ 5. municipio
    oferta, sem_sede, zero, ate9, ate99 = con.execute(
        f"""WITH c AS (SELECT co_municipio AS codigo, SUM(qt_mat) AS mat
                       FROM {CURSOS} WHERE {UNIVERSO} GROUP BY 1),
                 s AS (SELECT DISTINCT co_municipio_ies AS codigo FROM {IES}
                       WHERE nu_ano_censo = '2024')
            SELECT COUNT(*), COUNT(*) FILTER (WHERE s.codigo IS NULL),
                   COUNT(*) FILTER (WHERE c.mat = 0),
                   COUNT(*) FILTER (WHERE c.mat BETWEEN 1 AND 9),
                   COUNT(*) FILTER (WHERE c.mat BETWEEN 1 AND 99)
            FROM c LEFT JOIN s USING (codigo)"""
    ).fetchone()
    registrar(
        "municipio",
        "unidades com oferta e sem sede de IES (IES = 0 real; docentes nao se aplicam)",
        f"{n(sem_sede)} de {n(oferta)}",
    )
    registrar(
        "municipio",
        "unidades com oferta e base pequena para proporcao de matriculas",
        f"0 matriculas={n(zero)}; 1 a 9={n(ate9)}; 1 a 99={n(ate99)}",
        "com 0 matriculas a proporcao nao se aplica (denominador zero)",
    )
    sede_sem_oferta = con.execute(
        f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_municipio_ies AS codigo FROM {IES}
                                  WHERE nu_ano_censo = '2024') s
            LEFT JOIN (SELECT DISTINCT co_municipio AS codigo FROM {CURSOS} WHERE {UNIVERSO}) c
              USING (codigo) WHERE c.codigo IS NULL"""
    ).fetchone()[0]
    registrar("municipio", "unidades com sede de IES e sem linha de oferta", n(sede_sem_oferta))
    sem_docente = con.execute(
        f"""SELECT COUNT(*) FROM (SELECT co_municipio_ies FROM {IES} WHERE nu_ano_censo = '2024'
            GROUP BY 1 HAVING SUM(qt_doc_total) = 0)"""
    ).fetchone()[0]
    registrar(
        "municipio",
        "unidades de sede com zero docente declarado (proporcao de doutores nao se aplica)",
        n(sem_docente),
    )

    # ------------------------------------------------------------------ 6. rede
    for rede, doc, dout in con.execute(
        f"""SELECT ds_rede, CAST(SUM(qt_doc_total) AS BIGINT), CAST(SUM(qt_doc_ex_dout) AS BIGINT)
            FROM {IES} WHERE nu_ano_censo = '2024' GROUP BY 1 ORDER BY 1"""
    ).fetchall():
        registrar(
            "rede",
            f"docentes com doutorado na rede {rede}",
            f"{d(dout / doc * 100)}%",
            f"doutores={n(dout)} docentes={n(doc)}",
        )
    for rede, m_rede, e_rede in con.execute(
        f"""SELECT tp_rede, CAST(SUM(qt_mat) AS BIGINT),
                   CAST(SUM(qt_mat) FILTER (WHERE tp_dimensao = '{POLO}') AS BIGINT)
            FROM {CURSOS} WHERE {UNIVERSO} GROUP BY 1 ORDER BY 1"""
    ).fetchall():
        registrar(
            "rede",
            f"participacao da EAD nas matriculas da rede {rede}",
            f"{d(e_rede / m_rede * 100)}%",
            f"polo EAD={n(e_rede)} matriculas={n(m_rede)}",
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
