"""Matriculas e Fluxo (Fase 9) contra os numeros de controle.

Constantes medidas no DuckDB local em 2026-10-07 (scripts/analise/auditar_fluxo.py) e coincidentes
com as fichas IND-R-07 a IND-R-11 de INDICADORES.md.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.indicadores import AREA_CINE, PERFIS, RAZOES, TIPOS_INGRESSO, Eixo

pytestmark = pytest.mark.dados

COM_BASE = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_exterior"
TERRITORIAIS = "dimensao=presencial&dimensao=ead_polo"
TOTAIS = {"matriculas": 10_227_266, "ingressantes": 5_010_613, "concluintes": 1_333_988}
EIXOS_PERFIL = [str(e) for e in PERFIS]


def _get(cliente: TestClient, caminho: str) -> dict[str, Any]:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def _recusa(cliente: TestClient, caminho: str, trecho: str) -> None:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 422, r.text
    assert trecho in r.json()["erro"]["mensagem"]


def _linhas(corpo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {linha["codigo"]: linha for linha in corpo["linhas"]}


def _fecha_com_geral(corpo: dict[str, Any]) -> None:
    """As linhas repartem exatamente o numerador e o denominador do valor geral."""
    assert not corpo["truncado"]
    for termo in ("numerador", "denominador"):
        assert sum(linha[termo] for linha in corpo["linhas"]) == corpo["geral"][termo]


# --- Perfil (IND-R-07) e tipo de vaga do ingresso -----------------------------------------------


@pytest.mark.parametrize("slug", list(TOTAIS))
@pytest.mark.parametrize("eixo", EIXOS_PERFIL)
def test_perfil_e_particao_exata(cliente: TestClient, slug: str, eixo: str) -> None:
    corpo = _get(cliente, f"indicadores/{slug}/composicao?por={eixo}&recorte=oferta&{COM_BASE}")
    assert corpo["ficha"] == "IND-R-07"
    assert corpo["total"] == TOTAIS[slug]
    assert sum(linha["valor"] for linha in corpo["linhas"]) == TOTAIS[slug]
    assert sum(linha["participacao"] for linha in corpo["linhas"]) == pytest.approx(100)
    # Ordem natural do catalogo, nao por valor (faixa etaria).
    assert [linha["codigo"] for linha in corpo["linhas"]] == [s for s, _, _ in PERFIS[Eixo(eixo)]]


def test_perfil_valores_de_controle(cliente: TestClient) -> None:
    sexo = _linhas(
        _get(cliente, f"indicadores/matriculas/composicao?por=sexo&recorte=oferta&{COM_BASE}")
    )
    assert sexo["feminino"]["valor"] == 6_088_602
    assert sexo["masculino"]["valor"] == 4_138_664
    # A categoria de informacao ausente e devolvida, nao escondida.
    cor = _get(cliente, f"indicadores/matriculas/composicao?por=cor_raca&recorte=oferta&{COM_BASE}")
    assert "nao_declarada" in _linhas(cor)
    assert any("ausência de informação" in nota for nota in cor["notas"])


def test_perfil_fecha_com_o_indicador_direto_em_uma_uf(cliente: TestClient) -> None:
    direto = _get(cliente, f"indicadores/concluintes?nivel=uf&recorte=oferta&{TERRITORIAIS}&uf=DF")
    for eixo in EIXOS_PERFIL:
        corpo = _get(
            cliente,
            f"indicadores/concluintes/composicao?por={eixo}&recorte=oferta&{TERRITORIAIS}&uf=DF",
        )
        assert corpo["total"] == direto["total"]


def test_perfil_recusado_no_municipio_e_fora_das_tres_bases(cliente: TestClient) -> None:
    _recusa(
        cliente,
        f"indicadores/matriculas/composicao?por=cor_raca&recorte=oferta&{TERRITORIAIS}"
        "&uf=DF&municipio=5300108",
        "piso de supressão",
    )
    _recusa(
        cliente,
        "indicadores/vagas/composicao?por=sexo&recorte=oferta&dimensao=presencial",
        "não admite composição",
    )
    _recusa(cliente, "indicadores/docentes/composicao?por=sexo&recorte=sede", "não admite")


def test_tipo_de_vaga_do_ingresso(cliente: TestClient) -> None:
    corpo = _get(
        cliente, f"indicadores/ingressantes/composicao?por=tipo_ingresso&recorte=oferta&{COM_BASE}"
    )
    assert corpo["ficha"] is None
    assert {c: linha["valor"] for c, linha in _linhas(corpo).items()} == {
        "vaga_nova": 4_349_243,
        "vaga_remanescente": 645_281,
        "programa_especial": 9_877,
        "outra_forma": 6_212,
    }
    assert corpo["total"] == TOTAIS["ingressantes"]
    assert len(corpo["linhas"]) == len(TIPOS_INGRESSO)
    _recusa(
        cliente,
        f"indicadores/matriculas/composicao?por=tipo_ingresso&recorte=oferta&{COM_BASE}",
        "não admite composição",
    )


# --- Razoes --------------------------------------------------------------------------------------


def test_catalogo_de_razoes(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/razoes")
    assert r.status_code == 200
    catalogo = {item["slug"]: item for item in r.json()}
    assert set(catalogo) == set(RAZOES)
    assert {item["codigo"] for item in catalogo.values()} == {
        "IND-R-08",
        "IND-R-09",
        "IND-R-10",
        "IND-R-11",
    }
    assert catalogo["ingressantes_por_vaga"]["dimensoes"] == ["presencial"]
    assert all(item["recorte"] == "oferta" for item in catalogo.values())
    assert cliente.get("/api/v1/razoes/taxa_de_conclusao?recorte=oferta").status_code == 404


def test_nenhum_nome_vedado_no_catalogo(cliente: TestClient) -> None:
    """IND-Q-01/02/04: os nomes vedados nao aparecem como nome de indicador nem de eixo."""
    nomes = [item["nome"].lower() for item in cliente.get("/api/v1/razoes").json()]
    nomes += [item["nome"].lower() for item in cliente.get("/api/v1/indicadores").json()]
    for vedado in ("taxa", "evas", "evolu", "tend", "cresc", "sucesso", "eficiência", "candidat"):
        assert not [n for n in nomes if vedado in n], vedado


@pytest.mark.parametrize(
    ("slug", "base", "numerador", "percentual"),
    [
        ("financiamento", "matriculas", 3_071_136, 30.03),
        ("financiamento", "ingressantes", 1_673_188, 33.39),
        ("financiamento", "concluintes", 347_889, 26.08),
        ("reserva_vagas", "matriculas", 648_225, 6.34),
        ("reserva_vagas", "ingressantes", 171_335, 3.42),
        ("reserva_vagas", "concluintes", 72_157, 5.41),
    ],
)
def test_participacoes_de_controle(
    cliente: TestClient, slug: str, base: str, numerador: int, percentual: float
) -> None:
    corpo = _get(cliente, f"razoes/{slug}?recorte=oferta&{COM_BASE}&base={base}&por=rede")
    assert corpo["base"] == base
    assert corpo["geral"]["numerador"] == numerador
    assert corpo["geral"]["denominador"] == TOTAIS[base]
    assert corpo["geral"]["valor"] == pytest.approx(percentual, abs=5e-3)
    _fecha_com_geral(corpo)
    # Contencao (0 violacoes por linha): nenhum grupo passa de 100%.
    assert all(0 <= linha["valor"] <= 100 for linha in corpo["linhas"])
    assert set(_linhas(corpo)) == {"publica", "privada"}


def test_ingressantes_por_vaga(cliente: TestClient) -> None:
    base = "razoes/ingressantes_por_vaga?recorte=oferta&dimensao=presencial"
    corpo = _get(cliente, f"{base}&por=regiao")
    assert corpo["indicador"]["codigo"] == "IND-R-10"
    assert corpo["geral"] == {
        "numerador": 1_663_040,
        "denominador": 5_075_146,
        "valor": pytest.approx(0.3277, abs=1e-4),
    }
    assert corpo["filtros"]["dimensoes"] == ["Cursos presenciais ofertados no Brasil"]
    assert len(corpo["linhas"]) == 5
    _fecha_com_geral(corpo)
    assert any("taxa de ocupação" in lim for lim in corpo["indicador"]["limitacoes"])

    rede = _linhas(_get(cliente, f"{base}&por=rede"))
    assert rede["privada"]["valor"] == pytest.approx(0.2768, abs=1e-4)
    assert rede["publica"]["valor"] == pytest.approx(0.5911, abs=1e-4)

    # Fecha com os indicadores diretos no mesmo recorte.
    for por in ("uf", "organizacao", "categoria", "grau", "area"):
        _fecha_com_geral(_get(cliente, f"{base}&por={por}"))
    df = _get(cliente, f"{base}&uf=DF")
    ing = _get(
        cliente, "indicadores/ingressantes?nivel=uf&recorte=oferta&dimensao=presencial&uf=DF"
    )
    vagas = _get(cliente, "indicadores/vagas?nivel=uf&recorte=oferta&dimensao=presencial&uf=DF")
    assert (df["geral"]["numerador"], df["geral"]["denominador"]) == (ing["total"], vagas["total"])
    assert df["linhas"] == [] and df["por"] is None


def test_ingressantes_por_vaga_so_no_presencial(cliente: TestClient) -> None:
    base = "razoes/ingressantes_por_vaga?recorte=oferta"
    for dimensao in ("ead_polo", "ead_nacional", "ead_exterior"):
        _recusa(cliente, f"{base}&dimensao={dimensao}", "não é definido nas dimensões")
    _recusa(cliente, base, "exige 'dimensao' declarada")
    _recusa(cliente, f"{base}&dimensao=presencial&por=dimensao", "não admite comparação")
    _recusa(cliente, f"{base}&dimensao=presencial&base=matriculas", "não usa 'base'")
    _recusa(
        cliente, "razoes/ingressantes_por_vaga?recorte=sede&dimensao=presencial", "recorte 'oferta'"
    )


def test_razao_sem_denominador_e_nula_e_nao_zero(cliente: TestClient) -> None:
    """60 municipios tem curso presencial e nenhuma vaga (medido): a razao nao se aplica."""
    corpo = _get(
        cliente, "razoes/ingressantes_por_vaga?recorte=oferta&dimensao=presencial&por=municipio"
    )
    assert corpo["unidades"] == 1_121
    sem_vaga = [linha for linha in corpo["linhas"] if linha["denominador"] == 0]
    assert len(sem_vaga) == 60
    assert all(linha["valor"] is None for linha in sem_vaga)
    assert all(linha["valor"] is not None for linha in corpo["linhas"] if linha["denominador"] > 0)
    _fecha_com_geral(corpo)


def test_inscricoes_por_vaga_nunca_soma_as_duas_dimensoes(cliente: TestClient) -> None:
    base = "razoes/inscricoes_por_vaga?recorte=oferta"
    presencial = _get(cliente, f"{base}&dimensao=presencial&por=uf")
    assert presencial["geral"]["numerador"] == 8_658_561
    assert presencial["geral"]["valor"] == pytest.approx(1.7061, abs=1e-4)
    assert len(presencial["linhas"]) == 27
    _fecha_com_geral(presencial)

    nacional = _get(cliente, f"{base}&dimensao=ead_nacional")
    assert nacional["geral"] == {
        "numerador": 7_060_934,
        "denominador": 18_583_348,
        "valor": pytest.approx(0.3800, abs=1e-4),
    }
    _recusa(cliente, f"{base}&dimensao=presencial&dimensao=ead_nacional", "única dimensão")
    # A dimensao sem territorio nao desce de nivel.
    _recusa(cliente, f"{base}&dimensao=ead_nacional&por=uf", "não é territorializável")
    _recusa(cliente, f"{base}&dimensao=ead_nacional&uf=SP", "não é territorializável")
    _recusa(cliente, f"{base}&dimensao=ead_polo", "não é definido nas dimensões")


def test_participacoes_recusam_municipio_e_dimensao_sem_base(cliente: TestClient) -> None:
    base = "razoes/financiamento?recorte=oferta&base=matriculas"
    _recusa(cliente, f"{base}&{TERRITORIAIS}&por=municipio&uf=DF", "nível municipal")
    _recusa(cliente, f"{base}&{TERRITORIAIS}&uf=DF&municipio=5300108", "nível municipal")
    _recusa(cliente, f"{base}&dimensao=ead_nacional", "não é definido nas dimensões")
    _recusa(cliente, f"razoes/financiamento?recorte=oferta&{COM_BASE}", "exige 'base'")
    _recusa(cliente, f"{base}&{TERRITORIAIS}&por=regiao&uf=DF", "filtro 'uf'")
    r = cliente.get(f"/api/v1/{base}&{COM_BASE}&base=evadidos")
    assert r.status_code == 422


def test_comparacao_territorial_declara_o_que_fica_fora(cliente: TestClient) -> None:
    corpo = _get(
        cliente, f"razoes/financiamento?recorte=oferta&base=matriculas&{TERRITORIAIS}&por=uf"
    )
    assert len(corpo["linhas"]) == 27
    # As 41 matriculas de polo sem municipio ficam no geral e fora das linhas (regra 8).
    assert corpo["geral"]["denominador"] - sum(x["denominador"] for x in corpo["linhas"]) == 41
    assert any("sem município" in nota for nota in corpo["notas"])
    # Com filtro territorial, geral e linhas descrevem o mesmo conjunto.
    sul = _get(
        cliente,
        f"razoes/financiamento?recorte=oferta&base=matriculas&{TERRITORIAIS}&por=uf&regiao=sul",
    )
    assert len(sul["linhas"]) == 3
    _fecha_com_geral(sul)


def test_valores_pontuais_por_agrupamento(cliente: TestClient) -> None:
    """Fechar a soma nao basta: um agrupamento pela coluna errada tambem fecharia."""
    base = "razoes/ingressantes_por_vaga?recorte=oferta&dimensao=presencial"
    categoria = _linhas(_get(cliente, f"{base}&por=categoria"))
    assert categoria["publica_estadual"]["nome"] == "Pública Estadual"
    assert categoria["publica_estadual"]["valor"] == pytest.approx(0.6385, abs=1e-4)
    uf = {linha["uf"]: linha for linha in _get(cliente, f"{base}&por=uf")["linhas"]}
    assert uf["MS"]["nome"] == "Mato Grosso do Sul"
    assert uf["MS"]["valor"] == pytest.approx(0.4817, abs=1e-4)
    area = _get(cliente, f"{base}&por=area")
    assert {linha["nome"] for linha in area["linhas"]} <= {nome for _, nome in AREA_CINE.values()}
    assert any("Sem filtro de rede" in nota for nota in area["notas"])

    fin = "razoes/financiamento?recorte=oferta&base=matriculas"
    privada = _get(cliente, f"{fin}&{COM_BASE}&rede=privada&por=categoria")
    assert privada["geral"]["valor"] == pytest.approx(37.50, abs=5e-3)
    assert set(_linhas(privada)) == {"privada_com_fins_lucrativos", "privada_sem_fins_lucrativos"}
    assert _linhas(privada)["privada_com_fins_lucrativos"]["valor"] == pytest.approx(
        40.28, abs=5e-3
    )
    publica = _get(cliente, f"{fin}&{COM_BASE}&rede=publica")
    assert any("28 IES" in nota for nota in publica["notas"])
    assert (
        _linhas(_get(cliente, f"{fin}&{COM_BASE}&por=categoria"))["publica_federal"]["numerador"]
        == 0
    )


def test_limite_trunca_as_linhas_e_preserva_o_geral(cliente: TestClient) -> None:
    base = "razoes/ingressantes_por_vaga?recorte=oferta&dimensao=presencial&por=municipio&uf=SP"
    inteiro = _get(cliente, base)
    cortado = _get(cliente, f"{base}&limite=20")
    assert cortado["truncado"] and len(cortado["linhas"]) == 20
    assert cortado["geral"] == inteiro["geral"]
    assert cortado["unidades"] == inteiro["unidades"] == len(inteiro["linhas"])
    assert cortado["linhas"] == inteiro["linhas"][:20]


def test_geral_nulo_em_municipio_sem_vaga(cliente: TestClient) -> None:
    base = "razoes/ingressantes_por_vaga?recorte=oferta&dimensao=presencial"
    todos = _get(cliente, f"{base}&por=municipio")["linhas"]
    sem_vaga = next(linha for linha in todos if linha["denominador"] == 0)
    corpo = _get(cliente, f"{base}&uf={sem_vaga['uf']}&municipio={sem_vaga['codigo']}")
    assert corpo["geral"] == {"numerador": 0, "denominador": 0, "valor": None}
