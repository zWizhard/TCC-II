#!/usr/bin/env python3
"""Auditoria da Fase 10 (Distribuicao Territorial e mapas): o que os tres modos exigem do dado.

Le SOMENTE o DuckDB local (ADR-0003) e a malha em data/reference/malha/ (baixar_malha_ibge.py).

Perguntas, todas previas a servir qualquer mapa:

1. COORDENADAS. `municipio.latitude/longitude` servem para pontos e heatmap? Nulos, zeros,
   fora do Brasil, duplicadas. Existe coordenada propria de IES?
2. MALHA. indicadores <-> municipio <-> geometria: a chave `codarea` casa 1:1 com
   `codigo_municipio_dv`? Todo municipio do Censo tem poligono? O ponto cai no seu poligono?
3. POPULACAO (denominador de IND-R-01). A ponte de 6 digitos e unica? 2024 cobre as 5.571
   unidades sem duplicata? O JOIN multiplica ou perde linhas e matriculas?
4. IND-R-01. Como a razao se distribui entre as unidades — e o que isso exige da escala.
5. HEATMAP. Quao concentrado e o peso (matriculas por municipio)?
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
MALHA = RAIZ / "data" / "reference" / "malha"
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics" / "2026-10-07_mapas.csv"

CURSOS = "inep_educacao_superior_cursos"
IES = "inep_educacao_superior_ies"
PRESENCIAL = "Cursos presenciais ofertados no Brasil"
POLO = "Cursos a distância ofertados no Brasil"
COM_TERRITORIO = "regexp_full_match(co_municipio, '[0-9]{7}')"
# As 5.571 unidades de nivel municipal: fora as 28 sentinelas (DATA_DICTIONARY.md).
REAL = "right(codigo_municipio_dv, 5) <> '00000' AND codigo_municipio_dv <> '9999999'"
# Regiao limitrofe do pais segundo os metadados da propria API de malhas do IBGE.
BBOX = "latitude BETWEEN -33.7512 AND 5.2718 AND longitude BETWEEN -73.9904 AND -28.8476"

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


def _no_anel(x: float, y: float, anel: list[list[float]]) -> bool:
    """Ponto dentro de um anel fechado (paridade de cruzamentos de uma semirreta horizontal)."""
    dentro = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:], strict=False):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def contem(geometria: dict, x: float, y: float) -> bool:
    """Ponto dentro de um Polygon ou MultiPolygon: no anel externo e fora dos buracos.

    A caixa envolvente nao serve de teste: aprova o ponto que cai no mar ou no vizinho.
    """
    poligonos = (
        [geometria["coordinates"]] if geometria["type"] == "Polygon" else geometria["coordinates"]
    )
    return any(
        _no_anel(x, y, pol[0]) and not any(_no_anel(x, y, buraco) for buraco in pol[1:])
        for pol in poligonos
    )


def main() -> int:
    if not BANCO.is_file():
        print(f"Camada analitica ausente: {BANCO}", file=sys.stderr)
        return 1
    if not (MALHA / "municipios.geojson").is_file():
        print("Malha ausente: rode scripts/etl/baixar_malha_ibge.py", file=sys.stderr)
        return 1
    con = duckdb.connect(str(BANCO), read_only=True)

    # ------------------------------------------------------------------ 1. coordenadas
    total, nulas, zeros, fora = con.execute(
        f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL),
                   COUNT(*) FILTER (WHERE latitude = 0 OR longitude = 0),
                   COUNT(*) FILTER (WHERE NOT ({BBOX}))
            FROM municipio WHERE {REAL}"""
    ).fetchone()
    registrar(
        "coordenadas",
        "municipio: unidades reais com coordenada valida",
        "VALIDAS" if (nulas, zeros, fora) == (0, 0, 0) else "COM DEFEITO",
        f"unidades={n(total)} nulas={n(nulas)} zero={n(zeros)} fora do Brasil={n(fora)}",
    )
    duplicadas = con.execute(
        f"""SELECT COUNT(*) FROM (SELECT 1 FROM municipio WHERE {REAL}
            GROUP BY latitude, longitude HAVING COUNT(*) > 1)"""
    ).fetchone()[0]
    registrar(
        "coordenadas",
        "municipio: pares (latitude, longitude) repetidos entre unidades",
        "NENHUM" if duplicadas == 0 else "HA REPETICAO",
        f"pares repetidos={n(duplicadas)}",
    )
    sentinelas_fora = con.execute(
        f"SELECT COUNT(*) FROM municipio WHERE NOT ({REAL}) AND NOT ({BBOX})"
    ).fetchone()[0]
    registrar(
        "coordenadas",
        "sentinelas com coordenada fora do Brasil (por isso sao excluidas do mapa)",
        n(sentinelas_fora),
        "28 sentinelas no total; o Censo nao referencia nenhuma",
    )
    for rotulo, tabela, coluna, onde in (
        ("sede de IES", IES, "co_municipio_ies", "TRUE"),
        ("local de oferta", CURSOS, "co_municipio", COM_TERRITORIO),
    ):
        unidades, sem_coord, em_sentinela = con.execute(
            f"""WITH c AS (SELECT DISTINCT {coluna} AS codigo FROM {tabela} WHERE {onde})
                SELECT COUNT(*), COUNT(*) FILTER (WHERE m.latitude IS NULL),
                       COUNT(*) FILTER (WHERE m.codigo_municipio_dv IS NOT NULL AND NOT ({REAL}))
                FROM c LEFT JOIN municipio m ON m.codigo_municipio_dv = c.codigo"""
        ).fetchone()
        registrar(
            "coordenadas",
            f"municipios do Censo ({rotulo}) com coordenada",
            "TODOS" if sem_coord == 0 and em_sentinela == 0 else "FALTAM",
            f"unidades={n(unidades)} sem coordenada={n(sem_coord)} em sentinela={n(em_sentinela)}",
        )
    colunas_ies = [r[0] for r in con.execute(f"DESCRIBE {IES}").fetchall()]
    geo_ies = [c for c in colunas_ies if any(k in c for k in ("lat", "lon", "coord", "geo"))]
    registrar(
        "coordenadas",
        "IES: existe coluna de coordenada propria?",
        "NAO" if not geo_ies else f"SIM: {geo_ies}",
        "so ds_endereco_ies e nu_cep_ies; o ponto de uma IES e o do municipio de sede",
    )
    ies_total, municipios_sede, maior = con.execute(
        f"""SELECT SUM(q), COUNT(*), MAX(q)
            FROM (SELECT COUNT(*) AS q FROM {IES} GROUP BY co_municipio_ies)"""
    ).fetchone()
    registrar(
        "coordenadas",
        "IES por ponto: quantas IES dividem a mesma coordenada",
        f"{n(ies_total)} IES em {n(municipios_sede)} pontos",
        f"maior ponto reune {n(maior)} IES: um ponto por IES seria sobreposicao, nao localizacao",
    )

    # ------------------------------------------------------------------ 2. malha
    feicoes = json.loads((MALHA / "municipios.geojson").read_text("utf-8"))["features"]
    ufs = json.loads((MALHA / "ufs.geojson").read_text("utf-8"))["features"]
    codigos_malha = [f["properties"]["codarea"] for f in feicoes]
    registrar(
        "malha",
        "feicoes municipais e unicidade de codarea",
        f"{n(len(feicoes))} feicoes, {n(len(set(codigos_malha)))} codigos distintos",
        f"tipo={type(codigos_malha[0]).__name__}, {len(codigos_malha[0])} digitos; UFs={len(ufs)}",
    )
    pontos = {
        r[0]: (float(r[1]), float(r[2]), r[3])
        for r in con.execute(
            f"SELECT codigo_municipio_dv, longitude, latitude, nome_municipio FROM municipio WHERE {REAL}"
        ).fetchall()
    }
    malha = set(codigos_malha)
    sem_poligono = sorted(set(pontos) - malha)
    sem_municipio = sorted(malha - set(pontos))
    registrar(
        "malha",
        "municipio <-> malha pela chave de 7 digitos (texto, sem nome)",
        "1:1" if not sem_poligono and not sem_municipio else "NAO CASA",
        f"municipio sem poligono={sem_poligono} poligono sem municipio={sem_municipio}",
    )
    for rotulo, tabela, coluna, onde in (
        ("sede de IES", IES, "co_municipio_ies", "TRUE"),
        ("local de oferta", CURSOS, "co_municipio", COM_TERRITORIO),
    ):
        censo = {
            r[0]
            for r in con.execute(f"SELECT DISTINCT {coluna} FROM {tabela} WHERE {onde}").fetchall()
        }
        registrar(
            "malha",
            f"municipios do Censo ({rotulo}) sem poligono",
            n(len(censo - malha)),
            f"de {n(len(censo))} unidades",
        )
    fora = {
        f["properties"]["codarea"]
        for f in feicoes
        if (ponto := pontos.get(f["properties"]["codarea"])) is not None
        and not contem(f["geometry"], ponto[0], ponto[1])
    }
    sedes = {r[0] for r in con.execute(f"SELECT DISTINCT co_municipio_ies FROM {IES}").fetchall()}
    registrar(
        "malha",
        "coordenada de `municipio` dentro do proprio poligono (ponto-em-poligono)",
        f"{n(len(pontos) - len(fora))} de {n(len(pontos))}; {n(len(fora))} fora",
        f"fora e sede de IES={sorted(pontos[c][2] for c in fora & sedes)}; ponto e poligono "
        "vem de fontes diferentes e a malha e simplificada",
    )
    siglas_uf = {
        r[0] for r in con.execute(f"SELECT DISTINCT cd_uf FROM municipio WHERE {REAL}").fetchall()
    }
    registrar(
        "malha",
        "UFs: codarea (2 digitos) <-> municipio.cd_uf",
        "1:1" if siglas_uf == {f["properties"]["codarea"] for f in ufs} else "NAO CASA",
        f"{len(siglas_uf)} UFs",
    )

    # ------------------------------------------------------------------ 3. populacao
    linhas, distintos, soma, minimo, nao_positiva = con.execute(
        """SELECT COUNT(*), COUNT(DISTINCT cod_municipio), CAST(SUM(populacao) AS BIGINT),
                  CAST(MIN(populacao) AS BIGINT), COUNT(*) FILTER (WHERE populacao IS NULL OR populacao <= 0)
           FROM ibge_populacao_estimada WHERE ano = '2024'"""
    ).fetchone()
    registrar(
        "populacao",
        "ibge_populacao_estimada, ano = '2024' (texto): linhas x municipios distintos",
        "SEM DUPLICATA" if linhas == distintos else "DUPLICADA",
        f"linhas={n(linhas)} distintos={n(distintos)} soma={n(soma)} menor={n(minimo)} nula ou <= 0={n(nao_positiva)}",
    )
    reais, ponte_distinta, ponte_divergente = con.execute(
        f"""SELECT COUNT(*), COUNT(DISTINCT codigo_municipio),
                   COUNT(*) FILTER (WHERE codigo_municipio <> left(codigo_municipio_dv, 6))
            FROM municipio WHERE {REAL}"""
    ).fetchone()
    registrar(
        "populacao",
        "ponte municipio.codigo_municipio (6 digitos): unica entre as unidades reais",
        "UNICA" if reais == ponte_distinta else "AMBIGUA",
        f"unidades={n(reais)} codigos de 6 digitos={n(ponte_distinta)} diferentes do prefixo do codigo de 7={n(ponte_divergente)}",
    )
    sem_pop, pop_sem_mun = con.execute(
        f"""SELECT
              (SELECT COUNT(*) FROM municipio m
                 LEFT JOIN ibge_populacao_estimada p
                   ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024'
                WHERE {REAL} AND p.cod_municipio IS NULL),
              (SELECT COUNT(*) FROM ibge_populacao_estimada p
                 LEFT JOIN (SELECT codigo_municipio FROM municipio WHERE {REAL}) m
                   ON m.codigo_municipio = p.cod_municipio
                WHERE p.ano = '2024' AND m.codigo_municipio IS NULL)"""
    ).fetchone()
    registrar(
        "populacao",
        "municipio <-> populacao 2024: orfaos nos dois sentidos",
        "1:1" if (sem_pop, pop_sem_mun) == (0, 0) else "COM ORFAOS",
        f"unidade sem populacao={n(sem_pop)} populacao sem unidade={n(pop_sem_mun)}",
    )
    antes, mat_antes, depois, mat_depois, pop_coberta = con.execute(
        f"""WITH agg AS (
                SELECT co_municipio AS codigo, SUM(qt_mat) AS mat FROM {CURSOS}
                WHERE nu_ano_censo = '2024' AND list_contains(['{PRESENCIAL}', '{POLO}'], tp_dimensao)
                  AND {COM_TERRITORIO}
                GROUP BY 1
            ), j AS (
                SELECT a.codigo, a.mat, p.populacao FROM agg a
                JOIN municipio m ON m.codigo_municipio_dv = a.codigo
                JOIN ibge_populacao_estimada p
                  ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024'
            )
            SELECT (SELECT COUNT(*) FROM agg), (SELECT CAST(SUM(mat) AS BIGINT) FROM agg),
                   COUNT(*), CAST(SUM(mat) AS BIGINT), CAST(SUM(populacao) AS BIGINT)
            FROM j"""
    ).fetchone()
    registrar(
        "populacao",
        "JOIN agregado de cursos -> municipio -> populacao 2024 (presencial + polo)",
        "PRESERVA" if (antes, mat_antes) == (depois, mat_depois) else "ALTERA",
        f"linhas {n(antes)} -> {n(depois)}; matriculas {n(mat_antes)} -> {n(mat_depois)}; "
        f"populacao das unidades com oferta={n(pop_coberta)} de {n(soma)}",
    )

    # ------------------------------------------------------------------ 4. IND-R-01
    con.execute(
        f"""CREATE TEMP TABLE r01 AS
            WITH agg AS (
                SELECT co_municipio AS codigo,
                       SUM(qt_mat) AS mat,
                       SUM(qt_mat) FILTER (WHERE tp_dimensao = '{PRESENCIAL}') AS mat_pres,
                       SUM(qt_mat) FILTER (WHERE tp_dimensao = '{POLO}') AS mat_polo
                FROM {CURSOS}
                WHERE nu_ano_censo = '2024' AND list_contains(['{PRESENCIAL}', '{POLO}'], tp_dimensao)
                  AND {COM_TERRITORIO}
                GROUP BY 1
            )
            SELECT m.codigo_municipio_dv AS codigo, m.nome_municipio AS nome, m.cd_uf,
                   CAST(p.populacao AS BIGINT) AS pop, a.mat, a.mat_pres, a.mat_polo
            FROM municipio m
            JOIN ibge_populacao_estimada p ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024'
            LEFT JOIN agg a ON a.codigo = m.codigo_municipio_dv
            WHERE {REAL}"""
    )
    unidades, com_oferta, zero, mat, pop = con.execute(
        """SELECT COUNT(*), COUNT(mat), COUNT(*) FILTER (WHERE mat = 0),
                  CAST(SUM(mat) AS BIGINT), SUM(pop) FROM r01"""
    ).fetchone()
    registrar(
        "ind_r_01",
        "universo: unidades com e sem registro de oferta (ausente != zero)",
        f"{n(com_oferta)} com registro, {n(unidades - com_oferta)} sem",
        f"de {n(unidades)}; com registro e 0 matriculas={n(zero)}",
    )
    registrar(
        "ind_r_01",
        "Brasil, presencial + polo: matriculas territorializaveis / populacao 2024 x 100 mil",
        d(mat / pop * 100_000),
        f"numerador={n(mat)} denominador={n(pop)}",
    )
    por_uf = con.execute(
        """SELECT cd_uf, SUM(mat) / SUM(pop) * 100000 AS v FROM r01 GROUP BY 1 ORDER BY v"""
    ).fetchall()
    registrar(
        "ind_r_01",
        "UF: denominador reagregado (populacao de TODAS as unidades da UF)",
        f"de {d(por_uf[0][1])} (UF {por_uf[0][0]}) a {d(por_uf[-1][1])} (UF {por_uf[-1][0]})",
        f"{len(por_uf)} UFs",
    )
    for rotulo, coluna in (
        ("presencial + polo", "mat"),
        ("so presencial", "mat_pres"),
        ("so polo EAD", "mat_polo"),
    ):
        q = con.execute(
            f"""SELECT COUNT(*), MIN(v), quantile_cont(v, [0.2, 0.4, 0.5, 0.6, 0.8, 0.95, 0.99]), MAX(v)
                FROM (SELECT {coluna} / pop * 100000 AS v FROM r01 WHERE {coluna} IS NOT NULL)"""
        ).fetchone()
        registrar(
            "ind_r_01",
            f"municipio, {rotulo}: distribuicao da razao entre unidades com registro",
            f"mediana {d(q[2][2])}; maximo {d(q[3])}",
            f"unidades={n(q[0])} min={d(q[1])} p20={d(q[2][0])} p40={d(q[2][1])} p60={d(q[2][3])} "
            f"p80={d(q[2][4])} p95={d(q[2][5])} p99={d(q[2][6])}",
        )
    extremos = con.execute(
        """SELECT nome, cd_uf, pop, mat, mat / pop * 100000 FROM r01
           WHERE mat IS NOT NULL ORDER BY 5 DESC LIMIT 5"""
    ).fetchall()
    registrar(
        "ind_r_01",
        "cinco maiores razoes municipais (presencial + polo)",
        "; ".join(f"{e[0]} ({e[1]}) {d(e[4])}" for e in extremos),
        "; ".join(f"{e[0]}: {n(e[3])} matriculas / {n(e[2])} hab." for e in extremos),
    )
    pequenos, pequenos_oferta, acima = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE pop < 10000),
                   COUNT(*) FILTER (WHERE pop < 10000 AND mat IS NOT NULL),
                   COUNT(*) FILTER (WHERE mat / pop * 100000 > {mat / pop * 100_000})
            FROM r01"""
    ).fetchone()
    registrar(
        "ind_r_01",
        "denominador pequeno: unidades com menos de 10 mil habitantes",
        f"{n(pequenos)} unidades, {n(pequenos_oferta)} com registro de oferta",
        f"unidades com razao acima do valor nacional={n(acima)} de {n(com_oferta)}",
    )

    # ------------------------------------------------------------------ 5. heatmap
    for rotulo, sql in (
        (
            "matriculas por local de oferta (presencial + polo)",
            "SELECT mat AS v FROM r01 WHERE mat IS NOT NULL",
        ),
        ("IES por municipio de sede", f"SELECT COUNT(*) AS v FROM {IES} GROUP BY co_municipio_ies"),
    ):
        pontos_h, soma_h, maximo, top10 = con.execute(
            f"""WITH t AS ({sql}), o AS (SELECT v, row_number() OVER (ORDER BY v DESC) AS rn FROM t)
                SELECT COUNT(*), SUM(v), MAX(v), SUM(v) FILTER (WHERE rn <= 10) FROM o"""
        ).fetchone()
        registrar(
            "heatmap",
            f"concentracao do peso: {rotulo}",
            f"{d(top10 / soma_h * 100)}% do total nos 10 maiores pontos",
            f"pontos={n(pontos_h)} total={n(soma_h)} maior={n(maximo)} ({d(maximo / soma_h * 100)}%)",
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
