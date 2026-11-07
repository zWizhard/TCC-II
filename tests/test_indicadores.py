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


# Particoes medidas direto no DuckDB em 2026-10-06 (GROUP BY na coluna, sem a API).
IES_POR_CATEGORIA = {
    "publica_federal": 122,
    "publica_estadual": 139,
    "publica_municipal": 28,
    "privada_com_fins_lucrativos": 1_486,
    "privada_sem_fins_lucrativos": 758,
    "especial": 28,
}
MATRICULAS_POR_CATEGORIA = {
    "publica_federal": 1_317_548,
    "publica_estadual": 666_980,
    "publica_municipal": 35_139,
    "privada_com_fins_lucrativos": 6_372_474,
    "privada_sem_fins_lucrativos": 1_789_725,
    "especial": 45_400,
}
IES_POR_ORGANIZACAO = {
    "universidade": 206,
    "centro_universitario": 417,
    "faculdade": 1_897,
    "instituto_federal": 39,
    "cefet": 2,
}
MATRICULAS_POR_ORGANIZACAO = {
    "universidade": 5_420_049,
    "centro_universitario": 3_447_461,
    "faculdade": 1_124_240,
    "instituto_federal": 221_327,
    "cefet": 14_189,
}
IES_POR_REGIAO = {"norte": 196, "nordeste": 604, "sudeste": 1_076, "sul": 389, "centro_oeste": 296}
MATRICULAS_POR_REGIAO = {
    "norte": 863_969,
    "nordeste": 2_186_521,
    "sudeste": 4_518_942,
    "sul": 1_750_161,
    "centro_oeste": 905_093,
}


def test_filtros_institucionais_particionam_o_total(cliente: TestClient) -> None:
    for parametro, ies, mat in (
        ("categoria", IES_POR_CATEGORIA, MATRICULAS_POR_CATEGORIA),
        ("organizacao", IES_POR_ORGANIZACAO, MATRICULAS_POR_ORGANIZACAO),
    ):
        assert sum(ies.values()) == 2_561
        assert sum(mat.values()) == 10_227_266
        for slug, esperado in ies.items():
            corpo = _get(cliente, "ies", f"nivel=brasil&recorte=sede&{parametro}={slug}")
            assert corpo["total"] == esperado
            assert corpo["filtros"][parametro]  # rotulo literal aplicado, declarado na resposta
        for slug, esperado in mat.items():
            corpo = _get(
                cliente, "matriculas", f"nivel=brasil&recorte=oferta&{TODAS}&{parametro}={slug}"
            )
            assert corpo["total"] == esperado
    # A parcela sem municipio obedece aos mesmos filtros institucionais (regra 8).
    sem = _get(
        cliente,
        "matriculas",
        f"nivel=brasil&recorte=oferta&{TODAS}&categoria=privada_com_fins_lucrativos",
    )
    assert sem["valor_sem_territorio"] == 2_209
    sem = _get(cliente, "vagas", f"nivel=brasil&recorte=oferta&{TODAS}&categoria=publica_federal")
    assert sem["valor_sem_territorio"] == 54_581
    # Categoria refina a rede: as tres publicas + Especial somam a rede Publica (regra 7).
    publica = _get(cliente, "ies", "nivel=brasil&recorte=sede&rede=publica&categoria=especial")
    assert publica["total"] == 28
    # Filtros combinam por conjuncao: universidades federais.
    assert (
        _get(
            cliente,
            "ies",
            "nivel=brasil&recorte=sede&categoria=publica_federal&organizacao=universidade",
        )["total"]
        == 69
    )


@pytest.mark.parametrize("regiao", list(IES_POR_REGIAO))
def test_filtro_de_regiao_fecha_com_a_distribuicao(cliente: TestClient, regiao: str) -> None:
    for slug, qs, esperado in (
        ("ies", "recorte=sede", IES_POR_REGIAO[regiao]),
        ("matriculas", f"recorte=oferta&{TERRITORIAIS}", MATRICULAS_POR_REGIAO[regiao]),
    ):
        uma = _get(cliente, slug, f"nivel=regiao&{qs}&regiao={regiao}")
        assert (uma["unidades"], uma["total"]) == (1, esperado)
        assert uma["valor_sem_territorio"] is None
        # A regiao, as suas UFs e os seus municipios somam o mesmo valor.
        ufs = _get(cliente, slug, f"nivel=uf&{qs}&regiao={regiao}")
        municipios = _get(cliente, slug, f"nivel=municipio&{qs}&regiao={regiao}")
        assert ufs["total"] == municipios["total"] == esperado
        assert sum(li["valor"] for li in ufs["linhas"]) == esperado


def test_filtros_de_uf_e_municipio(cliente: TestClient) -> None:
    assert sum(IES_POR_REGIAO.values()) == 2_561
    assert sum(MATRICULAS_POR_REGIAO.values()) == 10_224_686
    sp = _get(cliente, "ies", "nivel=uf&recorte=sede&uf=SP")
    assert (sp["unidades"], sp["total"], sp["linhas"][0]["uf"]) == (1, 580, "SP")
    assert sp["filtros"]["uf"] == "SP"
    mat_uf = _get(cliente, "matriculas", f"nivel=uf&recorte=oferta&{TERRITORIAIS}&uf=SP")
    mat_mun = _get(cliente, "matriculas", f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&uf=SP")
    assert mat_uf["total"] == mat_mun["total"] == sum(li["valor"] for li in mat_mun["linhas"])
    capital = _get(
        cliente,
        "matriculas",
        f"nivel=municipio&recorte=oferta&{TERRITORIAIS}&municipio=3550308",
    )
    assert (capital["unidades"], capital["total"]) == (1, 470_626 + 388_400)
    assert capital["filtros"]["municipio"] == "3550308"
    assert capital["valor_sem_territorio"] is None
    # Codigo de municipio de outra UF: vazio, nunca os numeros dele sob a UF errada.
    trocado = _get(cliente, "ies", "nivel=municipio&recorte=sede&uf=SP&municipio=5300108")
    assert (trocado["unidades"], trocado["linhas"]) == (0, [])
    # Municipio sem sede de IES: nenhuma linha, e nao um zero inventado.
    vazio = _get(cliente, "ies", "nivel=municipio&recorte=sede&municipio=9999999")
    assert (vazio["unidades"], vazio["total"], vazio["linhas"]) == (0, 0, [])


def test_lista_de_municipios_da_uf(cliente: TestClient) -> None:
    df = cliente.get("/api/v1/territorios/municipios?uf=DF").json()
    assert df["municipios"] == [
        {"codigo": "5300108", "nome": "Brasília", "sede": True, "oferta": True}
    ]
    total, com_sede, com_oferta = 0, 0, 0
    for uf in (u["sigla"] for u in cliente.get("/api/v1/metadados").json()["ufs"]):
        municipios = cliente.get(f"/api/v1/territorios/municipios?uf={uf}").json()["municipios"]
        assert len({m["codigo"] for m in municipios}) == len(municipios)
        total += len(municipios)
        com_sede += sum(m["sede"] for m in municipios)
        com_oferta += sum(m["oferta"] for m in municipios)
    # IND-D-10 = 698 e IND-D-11 = 3.551; nenhuma sede fora das unidades com oferta.
    assert (total, com_sede, com_oferta) == (3_551, 698, 3_551)
    assert cliente.get("/api/v1/territorios/municipios").status_code == 422
    assert cliente.get("/api/v1/territorios/municipios?uf=XX").status_code == 422


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
        ("ies?nivel=brasil&recorte=sede&uf=DF", 422, "'uf'"),
        ("ies?nivel=regiao&recorte=sede&uf=DF", 422, "'uf'"),
        ("ies?nivel=brasil&recorte=sede&regiao=sul", 422, "'regiao'"),
        ("ies?nivel=uf&recorte=sede&municipio=5300108", 422, "'municipio'"),
        ("ies?nivel=municipio&recorte=sede&municipio=530010", 422, "municipio"),
        ("ies?nivel=municipio&recorte=sede&municipio=5300108' OR 1=1 --", 422, "municipio"),
        ("ies?nivel=uf&recorte=sede&uf=DF&regiao=sul", 422, "Centro-Oeste"),
        ("ies?nivel=brasil&recorte=sede&rede=privada&categoria=publica_federal", 422, "rede"),
        ("ies?nivel=brasil&recorte=sede&categoria=Pública Federal", 422, "categoria"),
        ("ies?nivel=brasil&recorte=sede&organizacao=universidades", 422, "organizacao"),
        ("ies?nivel=regiao&recorte=sede&regiao=Sul", 422, "regiao"),
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
    assert {d["slug"] for d in meta["dimensoes_oferta"] if d["modalidade"] == "Presencial"} == {
        "presencial"
    }
    assert len(meta["regioes"]) == 5
    assert len(meta["ufs"]) == 27
    assert len(meta["categorias"]) == 6
    assert len(meta["organizacoes"]) == 5
