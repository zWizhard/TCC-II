"""Indicadores servidos pela API contra os numeros de controle.

Constantes de docs/tcc/methodology/INDICADORES.md (Fase 4) e do relatorio do data-engineer
(Fase 5, 2026-09-26), medidas no DuckDB local. Divergencia aqui e numero errado na tela.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.dados

TODAS = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_nacional&dimensao=ead_exterior"
TERRITORIAIS = "dimensao=presencial&dimensao=ead_polo"


def _get(cliente: TestClient, slug: str, qs: str) -> dict[str, Any]:
    r = cliente.get(f"/api/v1/indicadores/{slug}?{qs}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


@pytest.mark.parametrize(
    ("slug", "recorte", "dims", "esperado"),
    [
        ("ies", "sede", "", 2_561),
        ("docentes", "sede", "", 374_501),
        ("tecnicos", "sede", "", 350_752),
        ("cursos", "oferta", TODAS, 45_776),
        ("matriculas", "oferta", TODAS, 10_227_266),
        ("ingressantes", "oferta", TODAS, 5_010_613),
        ("concluintes", "oferta", TODAS, 1_333_988),
        ("vagas", "oferta", TODAS, 23_665_419),
        ("inscricoes", "oferta", TODAS, 15_723_085),
    ],
)
def test_somas_de_controle_nacionais(
    cliente: TestClient, slug: str, recorte: str, dims: str, esperado: int
) -> None:
    corpo = _get(cliente, slug, f"nivel=brasil&recorte={recorte}&{dims}")
    assert corpo["total"] == esperado
    assert corpo["linhas"] == [
        {
            "codigo": "BR",
            "nome": "Brasil",
            "uf": None,
            "valor": esperado,
            "latitude": None,
            "longitude": None,
        }
    ]


@pytest.mark.parametrize(
    ("slug", "dims", "territorial"),
    [
        ("matriculas", TERRITORIAIS, 10_224_686),
        ("ingressantes", TERRITORIAIS, 5_009_116),
        ("concluintes", TERRITORIAIS, 1_333_515),
        ("cursos", "dimensao=presencial", 34_479),
        ("vagas", "dimensao=presencial", 5_075_146),
        ("inscricoes", "dimensao=presencial", 8_658_561),
    ],
)
@pytest.mark.parametrize(("nivel", "unidades"), [("regiao", 5), ("uf", 27)])
def test_niveis_territoriais_fecham(
    cliente: TestClient,
    slug: str,
    dims: str,
    territorial: int,
    nivel: str,
    unidades: int,
) -> None:
    corpo = _get(cliente, slug, f"nivel={nivel}&recorte=oferta&{dims}")
    assert corpo["unidades"] == unidades
    assert corpo["total"] == territorial == sum(li["valor"] for li in corpo["linhas"])


@pytest.mark.parametrize(
    ("slug", "esperado"), [("ies", 2_561), ("docentes", 374_501), ("tecnicos", 350_752)]
)
@pytest.mark.parametrize(("nivel", "unidades"), [("regiao", 5), ("uf", 27), ("municipio", 698)])
def test_indicadores_de_ies_fecham_por_nivel(
    cliente: TestClient, slug: str, esperado: int, nivel: str, unidades: int
) -> None:
    corpo = _get(cliente, slug, f"nivel={nivel}&recorte=sede")
    assert corpo["unidades"] == unidades
    assert corpo["total"] == esperado == sum(li["valor"] for li in corpo["linhas"])
    # co_regiao_ies e SMALLINT: a chave sai como texto, uniforme com cursos.
    assert all(isinstance(li["codigo"], str) and li["nome"] for li in corpo["linhas"])


def test_perda_territorial_e_declarada(cliente: TestClient) -> None:
    # Regra 8: o total nacional inclui 2.580 matriculas sem municipio (41 de polo + 2.539 do exterior).
    brasil = _get(cliente, "matriculas", f"nivel=brasil&recorte=oferta&{TODAS}")
    assert brasil["valor_sem_territorio"] == 2_580
    # Nas dimensoes com territorio, so os 41 do polo sem municipio ficam de fora.
    uf = _get(cliente, "matriculas", f"nivel=uf&recorte=oferta&{TERRITORIAIS}")
    assert uf["valor_sem_territorio"] == 41
    assert uf["total"] + uf["valor_sem_territorio"] == 5_037_875 + 5_186_852


def test_mapa_municipal_de_oferta(cliente: TestClient) -> None:
    corpo = _get(cliente, "matriculas", f"nivel=municipio&recorte=oferta&{TERRITORIAIS}")
    # JOIN N:1 com municipio auditado: 3.551 antes e depois, soma preservada, 0 orfaos.
    assert corpo["unidades"] == 3_551 == len(corpo["linhas"])
    assert corpo["total"] == 10_224_686
    assert not corpo["truncado"]
    assert len({li["codigo"] for li in corpo["linhas"]}) == 3_551
    assert all(li["latitude"] is not None and li["longitude"] is not None for li in corpo["linhas"])
    sp = next(li for li in corpo["linhas"] if li["codigo"] == "3550308")
    assert sp["valor"] == 470_626 + 388_400
    assert sp["uf"] == "SP"
    assert -24 < sp["latitude"] < -23


def test_mapa_municipal_de_sede(cliente: TestClient) -> None:
    corpo = _get(cliente, "ies", "nivel=municipio&recorte=sede")
    assert corpo["unidades"] == 698
    assert corpo["total"] == 2_561
    assert corpo["valor_sem_territorio"] == 0
    assert all(li["latitude"] is not None and li["longitude"] is not None for li in corpo["linhas"])
    bsb = next(li for li in corpo["linhas"] if li["codigo"] == "5300108")
    assert bsb["valor"] == 63


def test_filtros_de_rede_e_uf(cliente: TestClient) -> None:
    assert _get(cliente, "ies", "nivel=brasil&recorte=sede&rede=publica")["total"] == 317
    assert _get(cliente, "ies", "nivel=brasil&recorte=sede&rede=privada")["total"] == 2_244
    df = _get(cliente, "ies", "nivel=municipio&recorte=sede&uf=DF&rede=publica")
    assert (df["total"], df["filtros"]["rede"], df["valor_sem_territorio"]) == (5, "Pública", None)
    assert "Especial" in df["notas"][0]  # regra 7 / ADR-0007
    assert _get(cliente, "ies", "nivel=brasil&recorte=sede&rede=privada")["notas"] == []
    mat = _get(
        cliente,
        "matriculas",
        "nivel=municipio&recorte=oferta&dimensao=presencial&uf=DF&rede=publica",
    )
    assert mat["total"] == 44_532


def test_limite_trunca_e_declara(cliente: TestClient) -> None:
    corpo = _get(cliente, "matriculas", f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&limite=2")
    assert len(corpo["linhas"]) == 2
    assert corpo["truncado"] and corpo["unidades"] == 3_551
    assert corpo["total"] == 10_224_686  # total antes do limite
    assert corpo["linhas"][0]["valor"] >= corpo["linhas"][1]["valor"]


def test_vagas_ead_so_existem_no_nivel_brasil(cliente: TestClient) -> None:
    corpo = _get(cliente, "vagas", "nivel=brasil&recorte=oferta&dimensao=ead_nacional")
    assert corpo["total"] == 18_583_348


@pytest.mark.parametrize(
    ("url", "status", "trecho"),
    [
        # recorte explicito e coerente com a ficha (ADR-0004)
        ("ies?nivel=uf&recorte=oferta", 422, "recorte"),
        ("matriculas?nivel=uf&recorte=sede&dimensao=presencial", 422, "recorte"),
        ("ies?nivel=uf", 422, "recorte"),
        # tp_dimensao obrigatoria em cursos, inexistente em IES
        ("matriculas?nivel=uf&recorte=oferta", 422, "dimensao"),
        ("docentes?nivel=uf&recorte=sede&dimensao=presencial", 422, "tp_dimensao"),
        # dimensoes sem territorio recusadas fora do nivel brasil
        ("vagas?nivel=uf&recorte=oferta&dimensao=ead_polo", 422, "territorializ"),
        ("inscricoes?nivel=municipio&recorte=oferta&dimensao=ead_polo", 422, "territorializ"),
        ("cursos?nivel=regiao&recorte=oferta&dimensao=ead_polo", 422, "territorializ"),
        ("matriculas?nivel=uf&recorte=oferta&dimensao=ead_nacional", 422, "territorializ"),
        ("matriculas?nivel=municipio&recorte=oferta&dimensao=ead_exterior", 422, "territorializ"),
        # filtros fechados
        ("ies?nivel=uf&recorte=sede&uf=DF", 422, "municipio"),
        ("ies?nivel=municipio&recorte=sede&uf=df", 422, "uf"),
        ("ies?nivel=municipio&recorte=sede&uf=DF' OR 1=1 --", 422, "uf"),
        ("ies?nivel=municipio&recorte=sede&rede=Pública", 422, "rede"),
        ("ies?nivel=municipio&recorte=sede&limite=0", 422, "limite"),
        ("ies?nivel=municipio&recorte=sede&limite=6001", 422, "limite"),
        ("ies?nivel=distrito&recorte=sede", 422, "nivel"),
        ("qt_mat?nivel=brasil&recorte=oferta", 404, "catálogo"),
    ],
)
def test_combinacoes_recusadas(cliente: TestClient, url: str, status: int, trecho: str) -> None:
    r = cliente.get(f"/api/v1/indicadores/{url}")
    assert r.status_code == status
    erro = r.json()["erro"]
    assert trecho in erro["mensagem"]
    assert "SELECT" not in erro["mensagem"]


def test_catalogo_e_metadados(cliente: TestClient) -> None:
    catalogo = cliente.get("/api/v1/indicadores").json()
    assert [i["codigo"] for i in catalogo] == [f"IND-D-0{n}" for n in range(1, 10)]
    meta = cliente.get("/api/v1/metadados").json()
    assert meta["ano_censo"] == "2024"
    assert meta["extraido_em"]
    assert {d["slug"] for d in meta["dimensoes_oferta"] if d["territorializavel"]} == {
        "presencial",
        "ead_polo",
    }
