"""Mapa (Fase 10) contra os numeros de controle.

Constantes medidas no DuckDB local em 2026-10-07 (scripts/analise/auditar_mapas.py) e coincidentes
com a ficha IND-R-01 de INDICADORES.md.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.db import BaseAnalitica
from api.indicadores import CODIGO_UF, UF, UF_INFO
from api.main import create_app
from api.mapas import _classificar
from api.schemas import LinhaCoropletico

TERRITORIAIS = "dimensao=presencial&dimensao=ead_polo"
MATRICULAS_COM_TERRITORIO = 10_224_686
POPULACAO_2024 = 212_583_750
UNIDADES = 5_571
COM_OFERTA = 3_551
MALHA = Settings().malha_dir

com_malha = pytest.mark.skipif(
    not (MALHA / "municipios.geojson").is_file(),
    reason=f"{MALHA} ausente; rode scripts/etl/baixar_malha_ibge.py",
)


def _get(cliente: TestClient, caminho: str) -> dict[str, Any]:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def _recusa(cliente: TestClient, caminho: str, trecho: str) -> None:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 422, r.text
    assert trecho in r.json()["erro"]["mensagem"]


def _coropletico(cliente: TestClient, nivel: str, extra: str = "") -> dict[str, Any]:
    return _get(cliente, f"mapa/coropletico?nivel={nivel}&recorte=oferta&{TERRITORIAIS}{extra}")


# --- IND-R-01: universo, JOIN com a populacao e fechamento --------------------------------------


@pytest.mark.dados
def test_municipal_cobre_as_5571_unidades_e_preserva_as_somas(cliente: TestClient) -> None:
    corpo = _coropletico(cliente, "municipio")
    linhas = corpo["linhas"]
    # Universo = unidades reais de `municipio`, nao as unidades com oferta; sem duplicata.
    assert corpo["unidades"] == len(linhas) == len({li["codigo"] for li in linhas}) == UNIDADES
    assert (corpo["com_registro"], corpo["sem_registro"]) == (COM_OFERTA, UNIDADES - COM_OFERTA)
    # Os dois JOINs nao multiplicam nem perdem: numerador = IND-D-03 territorializavel,
    # denominador = populacao de 2024 inteira.
    assert sum(li["numerador"] or 0 for li in linhas) == MATRICULAS_COM_TERRITORIO
    assert sum(li["denominador"] for li in linhas) == POPULACAO_2024
    assert corpo["geral"] == {
        "numerador": MATRICULAS_COM_TERRITORIO,
        "denominador": POPULACAO_2024,
        "valor": pytest.approx(4809.72, abs=0.01),
    }
    assert (corpo["ano_censo"], corpo["ano_populacao"], corpo["recorte"]) == (
        "2024",
        "2024",
        "oferta",
    )
    assert corpo["indicador"]["codigo"] == "IND-R-01"
    # Nenhuma sentinela de `municipio` (codigo terminado em 00000, exterior).
    assert not [li for li in linhas if li["codigo"].endswith("00000") or li["codigo"][0] == "9"]


@pytest.mark.dados
def test_ausencia_nao_e_zero(cliente: TestClient) -> None:
    linhas = _coropletico(cliente, "municipio")["linhas"]
    sem_registro = [li for li in linhas if li["numerador"] is None]
    zero_real = [li for li in linhas if li["numerador"] == 0]
    assert len(sem_registro) == UNIDADES - COM_OFERTA
    assert all(li["valor"] is None and li["classe"] is None for li in sem_registro)
    # 135 unidades tem linha de oferta com zero matricula: valor 0, classe atribuida.
    assert len(zero_real) == 135
    assert all(li["valor"] == 0 and li["classe"] == 0 for li in zero_real)
    assert all(li["denominador"] > 0 for li in linhas)


@pytest.mark.dados
def test_valores_de_controle_municipais(cliente: TestClient) -> None:
    por_codigo = {li["codigo"]: li for li in _coropletico(cliente, "municipio")["linhas"]}
    urutai = por_codigo["5221809"]
    assert (urutai["nome"], urutai["uf"]) == ("Urutaí", "GO")
    assert (urutai["numerador"], urutai["denominador"]) == (1_104, 3_667)
    assert urutai["valor"] == pytest.approx(30106.35, abs=0.01)
    # Confere o numerador contra o indicador direto, municipio a municipio.
    direto = _get(cliente, f"indicadores/matriculas?nivel=municipio&recorte=oferta&{TERRITORIAIS}")
    assert not direto["truncado"]
    assert {li["codigo"]: li["valor"] for li in direto["linhas"]} == {
        c: li["numerador"] for c, li in por_codigo.items() if li["numerador"] is not None
    }


@pytest.mark.dados
def test_uf_reagrega_o_denominador(cliente: TestClient) -> None:
    municipal = _coropletico(cliente, "municipio")["linhas"]
    corpo = _coropletico(cliente, "uf")
    assert corpo["unidades"] == corpo["com_registro"] == 27
    assert corpo["geral"]["numerador"] == MATRICULAS_COM_TERRITORIO
    assert corpo["geral"]["denominador"] == POPULACAO_2024
    for linha in corpo["linhas"]:
        da_uf = [m for m in municipal if m["uf"] == linha["uf"]]
        # Populacao de TODAS as unidades da UF, inclusive as sem oferta — nao a media das razoes.
        assert linha["denominador"] == sum(m["denominador"] for m in da_uf)
        assert linha["numerador"] == sum(m["numerador"] or 0 for m in da_uf)
        assert linha["valor"] == pytest.approx(linha["numerador"] / linha["denominador"] * 100_000)
        assert linha["codigo"] == CODIGO_UF[UF(linha["uf"])]
    valores = {li["uf"]: li["valor"] for li in corpo["linhas"]}
    assert min(valores, key=valores.__getitem__) == "MA"
    assert max(valores, key=valores.__getitem__) == "DF"
    assert valores["MA"] == pytest.approx(3305.38, abs=0.01)
    assert valores["DF"] == pytest.approx(8325.45, abs=0.01)


@pytest.mark.dados
@pytest.mark.parametrize("regiao", ["norte", "nordeste", "sudeste", "sul", "centro_oeste"])
def test_filtro_territorial_restringe_numerador_e_denominador(
    cliente: TestClient, regiao: str
) -> None:
    nacional = _coropletico(cliente, "uf")["linhas"]
    ufs = {str(u) for u, (_, r) in UF_INFO.items() if r == regiao}
    corpo = _coropletico(cliente, "uf", f"&regiao={regiao}")
    assert {li["uf"] for li in corpo["linhas"]} == ufs
    for termo in ("numerador", "denominador"):
        assert corpo["geral"][termo] == sum(li[termo] for li in nacional if li["uf"] in ufs)
    municipal = _coropletico(cliente, "municipio", f"&regiao={regiao}")
    assert municipal["geral"] == corpo["geral"]
    assert {li["uf"] for li in municipal["linhas"]} == ufs


@pytest.mark.dados
def test_filtro_institucional_so_muda_o_numerador(cliente: TestClient) -> None:
    total = _coropletico(cliente, "uf")
    partes = [_coropletico(cliente, "uf", f"&rede={r}") for r in ("publica", "privada")]
    assert sum(p["geral"]["numerador"] for p in partes) == total["geral"]["numerador"]
    assert all(p["geral"]["denominador"] == POPULACAO_2024 for p in partes)
    assert any("denominador continua" in n for n in partes[0]["notas"])
    assert any("28 IES" in n for n in partes[0]["notas"])
    assert not any("denominador continua" in n for n in total["notas"])


@pytest.mark.dados
def test_municipio_unico_e_uf_de_um_municipio(cliente: TestClient) -> None:
    brasilia = _coropletico(cliente, "municipio", "&uf=DF&municipio=5300108")
    df = _coropletico(cliente, "uf", "&uf=DF")
    assert len(brasilia["linhas"]) == len(df["linhas"]) == 1
    assert brasilia["geral"] == df["geral"]
    assert brasilia["geral"]["numerador"] == 248_333
    assert len(brasilia["classes"]) == 1


@pytest.mark.dados
def test_notas_trazem_numeros_do_proprio_recorte(cliente: TestClient) -> None:
    def notas(extra: str, dims: str = TERRITORIAIS) -> str:
        url = f"mapa/coropletico?nivel=municipio&recorte=oferta&{dims}{extra}"
        return " ".join(_get(cliente, url)["notas"])

    padrao = notas("")
    assert "757 das unidades" in padrao and "41 matrículas de polo EAD" in padrao
    # Os mesmos textos com outro recorte mentiriam: 26 no presencial, 0 sem municipio na publica.
    assert "26 das unidades" in notas("", "dimensao=presencial")
    assert "sem município identificado" not in notas("", "dimensao=presencial")
    assert "sem município identificado" not in notas("&rede=publica", "dimensao=ead_polo")
    assert "757" not in notas("&uf=RR") and "sem município identificado" not in notas("&uf=RR")


@pytest.mark.dados
def test_territorio_sem_registro_e_ausencia_tambem_no_valor_geral(cliente: TestClient) -> None:
    # A categoria Especial nao tem matricula em Roraima: nem zero, nem classe.
    for nivel in ("uf", "municipio"):
        corpo = _coropletico(cliente, nivel, "&categoria=especial&uf=RR")
        assert corpo["com_registro"] == 0 and corpo["classes"] == []
        assert corpo["geral"]["numerador"] is None and corpo["geral"]["valor"] is None
        assert corpo["geral"]["denominador"] > 0
    # No pais, as UFs sem a categoria saem nulas e as demais fecham com o indicador direto.
    corpo = _coropletico(cliente, "uf", "&categoria=especial")
    direto = _get(
        cliente,
        f"indicadores/matriculas?nivel=uf&recorte=oferta&{TERRITORIAIS}&categoria=especial",
    )
    assert corpo["com_registro"] == direto["unidades"] == 11
    assert corpo["sem_registro"] == 16
    assert {li["uf"]: li["numerador"] for li in corpo["linhas"] if li["numerador"] is not None} == {
        li["uf"]: li["valor"] for li in direto["linhas"]
    }
    assert corpo["geral"]["numerador"] == direto["total"]


@pytest.mark.dados
def test_codigo_do_municipio_e_coerente_com_uf_nas_tres_tabelas() -> None:
    """Sustenta o filtro territorial aplicado dos dois lados do JOIN (cursos e municipio)."""
    base = BaseAnalitica(Settings().analytics_duckdb_path, timeout_s=5)
    try:
        divergentes = base.consultar(
            """SELECT
                 (SELECT COUNT(*) FROM inep_educacao_superior_cursos
                   WHERE regexp_full_match(co_municipio, '[0-9]{7}')
                     AND left(co_municipio, 2) <> CAST(co_uf AS VARCHAR)),
                 (SELECT COUNT(*) FROM municipio
                   WHERE left(codigo_municipio_dv, 2) <> cd_uf
                     AND right(codigo_municipio_dv, 5) <> '00000'
                     AND codigo_municipio_dv <> '9999999')""",
            {},
        )[0]
    finally:
        base.fechar()
    assert tuple(divergentes) == (0, 0)


# --- Classes da legenda -------------------------------------------------------------------------


@pytest.mark.dados
@pytest.mark.parametrize("quantidade", [3, 5, 7])
def test_classes_sao_quantis_ordenados_e_particionam(cliente: TestClient, quantidade: int) -> None:
    corpo = _coropletico(cliente, "municipio", f"&classes={quantidade}")
    classes = corpo["classes"]
    assert corpo["metodo_classes"] == "quantis"
    assert [c["indice"] for c in classes] == list(range(quantidade))
    assert sum(c["unidades"] for c in classes) == corpo["com_registro"]
    # Tamanhos parecidos e faixas que nao se sobrepoem.
    assert max(c["unidades"] for c in classes) - min(c["unidades"] for c in classes) <= 1
    for anterior, seguinte in zip(classes, classes[1:], strict=False):
        assert anterior["maximo"] < seguinte["minimo"]
    for linha in corpo["linhas"]:
        if linha["valor"] is not None:
            classe = classes[linha["classe"]]
            assert classe["minimo"] <= linha["valor"] <= classe["maximo"]


def _linha(valor: float | None) -> LinhaCoropletico:
    return LinhaCoropletico(
        codigo="0", nome="x", uf="DF", numerador=None, denominador=1, valor=valor, classe=None
    )


def test_empates_fundem_classes_em_vez_de_separar_valores_iguais() -> None:
    linhas, classes = _classificar([_linha(v) for v in (0, 0, 0, 0, 0, 0, 0, 3, 5, None)], 5)
    # Sete zeros nao podem cair em classes diferentes: sobram menos classes que as pedidas.
    assert {li.classe for li in linhas if li.valor == 0} == {0}
    assert [li.classe for li in linhas][-1] is None
    assert len(classes) < 5
    assert sum(c.unidades for c in classes) == 9
    assert [c.indice for c in classes] == list(range(len(classes)))


def test_sem_valor_algum_nao_ha_classe() -> None:
    assert _classificar([_linha(None)], 5)[1] == []


@pytest.mark.parametrize(
    ("valores", "esperadas"),
    [
        ((7.0,), [0]),  # um valor
        ((1.0, 2.0), [0, 1]),  # menos unidades que classes: uma classe por unidade
        ((1.0, 2.0, 3.0), [0, 1, 2]),
        ((4.0, 4.0, 4.0, 4.0, 4.0, 4.0), [0] * 6),  # todos iguais
        ((0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0), [0] * 10),  # corte = maximo
    ],
)
def test_classes_nos_casos_de_borda(valores: tuple[float, ...], esperadas: list[int]) -> None:
    linhas, classes = _classificar([_linha(v) for v in valores], 5)
    assert [li.classe for li in linhas] == esperadas
    assert [c.indice for c in classes] == sorted(set(esperadas))
    assert sum(c.unidades for c in classes) == len(valores)


# --- Recusas ------------------------------------------------------------------------------------


@pytest.mark.dados
@pytest.mark.parametrize(
    ("caminho", "trecho"),
    [
        (f"nivel=uf&recorte=sede&{TERRITORIAIS}", "só é definido no recorte 'oferta'"),
        ("nivel=uf&recorte=oferta", "exige 'dimensao'"),
        ("nivel=uf&recorte=oferta&dimensao=ead_nacional", "não é territorializável"),
        ("nivel=municipio&recorte=oferta&dimensao=ead_exterior", "não é territorializável"),
        (f"nivel=uf&recorte=oferta&{TERRITORIAIS}&municipio=5300108", "filtro 'municipio'"),
        (f"nivel=uf&recorte=oferta&{TERRITORIAIS}&uf=SP&regiao=sul", "pertence à região"),
        # O universo usa o filtro mais fino e o numerador todos: tem de ser o mesmo territorio.
        (f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&uf=SP&municipio=5300108", "pertence à UF"),
        (
            f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&regiao=sul&municipio=5300108",
            "pertence à região",
        ),
        (f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&municipio=0000000", "nenhuma UF"),
        # Sentinela de `municipio` e codigo inexistente: nao sao unidade territorial.
        (f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&municipio=5300000", "unidade territorial"),
        (f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&municipio=5399999", "unidade territorial"),
        (f"nivel=brasil&recorte=oferta&{TERRITORIAIS}", "nivel"),
        (f"nivel=regiao&recorte=oferta&{TERRITORIAIS}", "nivel"),
        (f"nivel=uf&recorte=oferta&{TERRITORIAIS}&classes=2", "classes"),
        (f"nivel=uf&recorte=oferta&{TERRITORIAIS}&municipio=53001", "municipio"),
        (f"nivel=uf&{TERRITORIAIS}", "recorte"),
    ],
)
def test_combinacoes_recusadas(cliente: TestClient, caminho: str, trecho: str) -> None:
    _recusa(cliente, f"mapa/coropletico?{caminho}", trecho)


# --- Codigos de UF e malha ----------------------------------------------------------------------


@pytest.mark.dados
def test_codigos_de_uf_do_catalogo_existem_no_dado() -> None:
    base = BaseAnalitica(Settings().analytics_duckdb_path, timeout_s=5)
    esperado = {(str(u), c) for u, c in CODIGO_UF.items()}
    assert set(CODIGO_UF) == set(UF)
    try:
        for sql in (
            "SELECT DISTINCT sg_uf_ies, co_uf_ies FROM inep_educacao_superior_ies",
            "SELECT DISTINCT sg_uf, co_uf FROM inep_educacao_superior_cursos "
            "WHERE regexp_full_match(co_municipio, '[0-9]{7}')",
        ):
            assert {(r[0], str(r[1])) for r in base.consultar(sql, {})} == esperado
        # `municipio.cd_uf` usa os mesmos 27 codigos.
        assert {r[0] for r in base.consultar("SELECT DISTINCT cd_uf FROM municipio", {})} >= {
            c for _, c in esperado
        }
    finally:
        base.fechar()


@com_malha
@pytest.mark.dados
def test_malha_casa_1_para_1_com_as_linhas_do_coropletico(cliente: TestClient) -> None:
    for nivel, digitos in (("municipio", 7), ("uf", 2)):
        r = cliente.get(f"/api/v1/mapa/malha/{nivel}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/geo+json")
        assert "max-age" in r.headers["cache-control"]
        feicoes = r.json()["features"]
        codigos = [f["properties"]["codarea"] for f in feicoes]
        assert all(isinstance(c, str) and len(c) == digitos for c in codigos)
        assert {f["geometry"]["type"] for f in feicoes} <= {"Polygon", "MultiPolygon"}
        linhas = _coropletico(cliente, nivel)["linhas"]
        # Chave por codigo, texto, sem nome: nenhum poligono sem dado, nenhum dado sem poligono.
        assert sorted(codigos) == sorted(li["codigo"] for li in linhas)


@com_malha
def test_malha_confere_com_o_manifesto() -> None:
    import hashlib

    manifesto = json.loads((MALHA / "MANIFEST.json").read_text("utf-8"))
    for arquivo in manifesto["arquivos"]:
        corpo = (MALHA / arquivo["arquivo"]).read_bytes()
        assert hashlib.sha256(corpo).hexdigest() == arquivo["sha256"]
        assert len(json.loads(corpo)["features"]) == arquivo["feicoes"]


@com_malha
def test_malha_e_servida_comprimida(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/mapa/malha/uf", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"


@pytest.mark.parametrize("nivel", ["brasil", "regiao", "municipios.geojson", "..%2F..%2Fpyproject"])
def test_malha_so_aceita_nivel_enumerado(cliente: TestClient, nivel: str) -> None:
    r = cliente.get(f"/api/v1/mapa/malha/{nivel}")
    assert r.status_code in (404, 422)
    assert "erro" in r.json()


def test_malha_ausente_devolve_503_sem_caminho(tmp_path: Path) -> None:
    settings = Settings(malha_dir=tmp_path / "sem-malha")
    with TestClient(create_app(settings)) as c:
        r = c.get("/api/v1/mapa/malha/municipio")
    assert r.status_code == 503
    erro = r.json()["erro"]
    assert erro["codigo"] == "malha_indisponivel"
    assert str(tmp_path) not in erro["mensagem"]
