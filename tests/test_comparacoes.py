"""Comparacoes (Fase 11) contra os numeros de controle.

Constantes medidas no DuckDB local em 2026-10-07 (scripts/analise/auditar_comparacoes.py) e
coincidentes com as fichas de INDICADORES.md.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.comparacoes import _razao

REGIOES = "unidade=norte&unidade=nordeste&unidade=sudeste&unidade=sul&unidade=centro_oeste"
MATRICULAS_COM_TERRITORIO = 10_224_686
POPULACAO_2024 = 212_583_750
# (slug, total nacional) dos valores absolutos que as cinco regioes tem de somar.
ABSOLUTOS = {
    "ies": 2_561,
    "docentes": 374_501,
    "cursos": 34_479,
    "matriculas": MATRICULAS_COM_TERRITORIO,
    "ingressantes": 5_009_116,
    "concluintes": 1_333_515,
}


def _get(cliente: TestClient, consulta: str) -> dict[str, Any]:
    r = cliente.get(f"/api/v1/comparacoes?{consulta}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def _recusa(cliente: TestClient, consulta: str, trecho: str) -> None:
    r = cliente.get(f"/api/v1/comparacoes?{consulta}")
    assert r.status_code == 422, r.text
    assert trecho in r.json()["erro"]["mensagem"]


def _por_slug(corpo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["slug"]: i for i in corpo["indicadores"]}


# --- calculo --------------------------------------------------------------------------------------


def test_razao_sem_denominador_e_nula_nao_zero() -> None:
    assert _razao(5, 0, 100).valor is None
    assert _razao(5, None, 100).valor is None
    assert _razao(None, 10, 100).valor is None
    # Numerador zero com denominador positivo e zero real.
    assert _razao(0, 10, 100).valor == 0
    assert _razao(1, 4, 100).valor == 25


# --- mesmas definicoes: as regioes fecham com a referencia ----------------------------------------


@pytest.mark.dados
def test_cinco_regioes_somam_a_referencia_nacional(cliente: TestClient) -> None:
    corpo = _get(cliente, f"nivel=regiao&{REGIOES}")
    assert (corpo["ano_censo"], corpo["ano_populacao"], corpo["nivel"]) == (
        "2024",
        "2024",
        "regiao",
    )
    assert sum(u["populacao"] for u in corpo["unidades"]) == POPULACAO_2024
    assert corpo["referencia"] == {
        "codigo": "BR",
        "nome": "Brasil",
        "uf": None,
        "populacao": POPULACAO_2024,
    }
    ind = _por_slug(corpo)
    for slug, total in ABSOLUTOS.items():
        assert ind[slug]["tipo"] == "absoluto"
        assert sum(v["valor"] for v in ind[slug]["valores"]) == total
        assert ind[slug]["referencia"]["valor"] == total
    # Relativos: o numerador e o denominador das regioes somam os do Brasil — a referencia e a
    # razao das somas, nunca a media das razoes.
    relativos = [i for i in corpo["indicadores"] if i["tipo"] == "relativo"]
    assert [i["codigo"] for i in relativos] == ["IND-R-01", "IND-R-03", "IND-R-04", "IND-R-12"]
    for i in relativos:
        for campo in ("numerador", "denominador"):
            assert sum(v[campo] for v in i["valores"]) == i["referencia"][campo], i["slug"]


@pytest.mark.dados
def test_referencia_nacional_bate_com_as_fichas(cliente: TestClient) -> None:
    ind = _por_slug(_get(cliente, "nivel=uf&unidade=SP&unidade=DF"))
    assert ind["matriculas_por_100_mil_habitantes"]["referencia"] == {
        "numerador": MATRICULAS_COM_TERRITORIO,
        "denominador": POPULACAO_2024,
        "valor": pytest.approx(4809.72, abs=0.01),
    }
    assert ind["participacao_privada"]["referencia"]["valor"] == pytest.approx(79.80, abs=0.01)
    assert ind["participacao_ead"]["referencia"]["valor"] == pytest.approx(50.73, abs=0.01)
    assert ind["docentes_doutorado"]["referencia"]["valor"] == pytest.approx(53.01, abs=0.01)
    # Maior razao entre as UFs (ficha de IND-R-01).
    assert ind["matriculas_por_100_mil_habitantes"]["valores"][1]["valor"] == pytest.approx(
        8325.4, abs=0.1
    )


@pytest.mark.dados
def test_cada_linha_declara_recorte_e_dimensoes(cliente: TestClient) -> None:
    ind = _por_slug(_get(cliente, "nivel=uf&unidade=SP&unidade=DF"))
    assert {s: i["recorte"] for s, i in ind.items()} == {
        "ies": "sede",
        "docentes": "sede",
        "cursos": "oferta",
        "matriculas": "oferta",
        "ingressantes": "oferta",
        "concluintes": "oferta",
        "matriculas_por_100_mil_habitantes": "oferta",
        "participacao_privada": "oferta",
        "participacao_ead": "oferta",
        "docentes_doutorado": "sede",
    }
    assert ind["ies"]["dimensoes"] == []
    # Contagem de cursos so existe territorializada no presencial.
    assert ind["cursos"]["dimensoes"] == ["Cursos presenciais ofertados no Brasil"]
    assert len(ind["matriculas"]["dimensoes"]) == 2
    assert all(i["limitacoes"] for i in ind.values())


@pytest.mark.dados
def test_ordem_pedida_e_preservada(cliente: TestClient) -> None:
    # RR tem 71 vezes menos matriculas que SP: a API nao reordena por valor.
    corpo = _get(cliente, "nivel=uf&unidade=RR&unidade=SP&unidade=DF")
    assert [u["codigo"] for u in corpo["unidades"]] == ["RR", "SP", "DF"]
    assert [v["valor"] for v in _por_slug(corpo)["matriculas"]["valores"]] == [
        34_171,
        2_441_033,
        248_333,
    ]
    assert any("64 vezes" in nota for nota in corpo["notas"])


# --- filtros compativeis --------------------------------------------------------------------------


@pytest.mark.dados
def test_rede_vale_para_todas_as_unidades_e_particiona(cliente: TestClient) -> None:
    geral = _por_slug(_get(cliente, f"nivel=regiao&{REGIOES}"))
    redes = {
        r: _por_slug(_get(cliente, f"nivel=regiao&{REGIOES}&rede={r}"))
        for r in ("publica", "privada")
    }
    for slug in ABSOLUTOS:
        for k, v in enumerate(geral[slug]["valores"]):
            assert (
                redes["publica"][slug]["valores"][k]["valor"]
                + redes["privada"][slug]["valores"][k]["valor"]
                == v["valor"]
            ), slug
    publica = redes["publica"]
    # Com a rede fixada a participacao da privada nao se aplica — nao vira 0%.
    assert publica["participacao_privada"]["nao_se_aplica"]
    assert all(v["valor"] is None for v in publica["participacao_privada"]["valores"])
    assert publica["participacao_privada"]["referencia"]["valor"] is None
    # O denominador de IND-R-01 continua sendo a populacao total.
    assert (
        publica["matriculas_por_100_mil_habitantes"]["referencia"]["denominador"] == POPULACAO_2024
    )
    assert publica["participacao_ead"]["referencia"]["valor"] == pytest.approx(10.4, abs=0.1)
    assert publica["docentes_doutorado"]["referencia"]["valor"] == pytest.approx(72.4, abs=0.1)


# --- municipio: ausencia nao e zero ---------------------------------------------------------------


@pytest.mark.dados
def test_municipio_sem_sede_tem_zero_ies_e_docentes_nulos(cliente: TestClient) -> None:
    # Alta Floresta D'Oeste (RO): polo EAD, nenhuma IES com sede, nenhum curso presencial.
    corpo = _get(cliente, "nivel=municipio&unidade=1100015&unidade=5300108")
    assert [(u["nome"], u["uf"]) for u in corpo["unidades"]] == [
        ("Alta Floresta D'Oeste", "RO"),
        ("Brasília", "DF"),
    ]
    ind = _por_slug(corpo)
    sem_sede = {s: i["valores"][0] for s, i in ind.items()}
    assert sem_sede["ies"]["valor"] == 0
    assert sem_sede["docentes"]["valor"] is None
    assert sem_sede["docentes_doutorado"]["valor"] is None
    assert sem_sede["cursos"]["valor"] is None
    assert sem_sede["matriculas"]["valor"] == 296
    assert sem_sede["participacao_ead"]["valor"] == 100
    assert any("Célula vazia não é zero" in nota for nota in corpo["notas"])
    # Brasilia e o unico municipio do DF: a coluna municipal coincide com a da UF.
    df = _por_slug(_get(cliente, "nivel=uf&unidade=DF&unidade=SP"))
    for slug, i in ind.items():
        assert i["valores"][1] == df[slug]["valores"][0], slug


@pytest.mark.dados
def test_rede_fixada_sem_registro_e_nulo_e_a_nota_nao_diz_sem_oferta(cliente: TestClient) -> None:
    # 1101807 e 1101484 (RO) tem oferta, mas so da rede privada.
    corpo = _get(cliente, "nivel=municipio&unidade=1101807&unidade=1101484&rede=publica")
    ind = _por_slug(corpo)
    for slug in ("matriculas", "ingressantes", "concluintes", "matriculas_por_100_mil_habitantes"):
        assert [v["valor"] for v in ind[slug]["valores"]] == [None, None], slug
    assert [v["valor"] for v in ind["ies"]["valores"]] == [0, 0]
    assert any("pode haver oferta da outra rede" in nota for nota in corpo["notas"])


@pytest.mark.dados
def test_zero_matricula_e_zero_real_e_participacao_nao_se_aplica(cliente: TestClient) -> None:
    # 1101807 tem linha de oferta com zero matricula; 1101484 tem 4 matriculas, todas EAD privada.
    corpo = _get(cliente, "nivel=municipio&unidade=1101807&unidade=1101484")
    ind = _por_slug(corpo)
    assert [v["valor"] for v in ind["matriculas"]["valores"]] == [0, 4]
    assert ind["matriculas_por_100_mil_habitantes"]["valores"][0]["valor"] == 0
    assert ind["participacao_ead"]["valores"][0] == {
        "valor": None,
        "numerador": 0,
        "denominador": 0,
    }
    assert ind["participacao_ead"]["valores"][1]["valor"] == 100
    notas = " ".join(corpo["notas"])
    # Avisa da base pequena (so a unidade com 1 a 99 matriculas conta), sem suprimir o valor.
    assert "menos de 100 matrículas: 1." in notas
    assert "menos de 10.000 habitantes" in notas


@pytest.mark.dados
def test_notas_fixas_declaram_dimensoes_perda_e_coortes(cliente: TestClient) -> None:
    corpo = _get(cliente, "nivel=uf&unidade=SP&unidade=DF")
    notas = " ".join(corpo["notas"])
    assert "2.580 de 10.227.266" in notas and "34.479 de 45.776" in notas
    assert "não se dividem um pelo outro" in notas
    assert corpo["dimensoes"] == [
        "Cursos presenciais ofertados no Brasil",
        "Cursos a distância ofertados no Brasil",
    ]
    # Pires do Rio (GO) tem 12 docentes: a proporcao de doutores vem com aviso.
    pequeno = _get(cliente, "nivel=municipio&unidade=5217401&unidade=5300108")
    assert any("menos de 100 docentes: 1." in nota for nota in pequeno["notas"])


# --- a ordem absoluta nao e a ordem relativa ------------------------------------------------------


@pytest.mark.dados
def test_ordem_das_ufs_por_matriculas_difere_da_ordem_pela_razao(cliente: TestClient) -> None:
    # Sustenta o texto de /comparar ("SP e a 1a em matriculas e a 8a na razao; o DF, a 1a na
    # razao e a 12a em matriculas") e a decisao de nao classificar as unidades.
    r = cliente.get(
        "/api/v1/mapa/coropletico?nivel=uf&recorte=oferta&dimensao=presencial&dimensao=ead_polo"
    )
    assert r.status_code == 200, r.text
    linhas = r.json()["linhas"]
    absoluta = [li["uf"] for li in sorted(linhas, key=lambda li: -li["numerador"])]
    relativa = [li["uf"] for li in sorted(linhas, key=lambda li: -li["valor"])]
    assert (absoluta[0], relativa.index("SP") + 1) == ("SP", 8)
    assert (relativa[0], absoluta.index("DF") + 1) == ("DF", 12)
    assert sum(1 for uf in absoluta if abs(absoluta.index(uf) - relativa.index(uf)) >= 5) == 15


# --- recusas --------------------------------------------------------------------------------------


@pytest.mark.dados
@pytest.mark.parametrize(
    ("consulta", "trecho"),
    [
        ("nivel=uf&unidade=SP", "at least 2"),
        ("nivel=uf&unidade=SP&unidade=RJ&unidade=MG&unidade=ES&unidade=DF&unidade=GO", "at most 5"),
        ("nivel=uf&unidade=SP&unidade=SP", "mais de uma vez"),
        # Niveis nao se misturam: regiao ou municipio num pedido de UFs.
        ("nivel=uf&unidade=SP&unidade=norte", "sigla da UF"),
        ("nivel=uf&unidade=SP&unidade=3550308", "sigla da UF"),
        ("nivel=regiao&unidade=norte&unidade=SP", "slug da região"),
        ("nivel=municipio&unidade=3550308&unidade=SP", "7 dígitos"),
        # Sentinela de `municipio` ('Município Ignorado - DF') e codigo inexistente.
        ("nivel=municipio&unidade=3550308&unidade=5300000", "não é uma unidade territorial"),
        ("nivel=municipio&unidade=3550308&unidade=9999999", "não é uma unidade territorial"),
        ("nivel=brasil&unidade=SP&unidade=RJ", "nivel"),
        ("nivel=uf&unidade=SP&unidade=RJ&rede=federal", "rede"),
        ("nivel=uf&unidade=SP&unidade=RJ'--", "pattern"),
    ],
)
def test_recusas(cliente: TestClient, consulta: str, trecho: str) -> None:
    _recusa(cliente, consulta, trecho)
