"""Analises de Instituicoes e Cursos (Fase 8) contra os numeros de controle.

Constantes medidas no DuckDB local em 2026-10-06 (auditoria do JOIN cursos x IES e das dimensoes
grau, area CINE e titulacao). Toda composicao tem de fechar com o indicador direto correspondente.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.indicadores import AREA_CINE, ROTULO_GRAU, TITULACOES

pytestmark = pytest.mark.dados

TODAS = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_nacional&dimensao=ead_exterior"
TERRITORIAIS = "dimensao=presencial&dimensao=ead_polo"


def _get(cliente: TestClient, caminho: str) -> dict[str, Any]:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def _composicao(cliente: TestClient, slug: str, qs: str) -> dict[str, Any]:
    return _get(cliente, f"indicadores/{slug}/composicao?{qs}")


def _valores(corpo: dict[str, Any]) -> dict[str, int]:
    return {linha["codigo"]: linha["valor"] for linha in corpo["linhas"]}


def _fecha(corpo: dict[str, Any]) -> None:
    """Sem truncamento: as linhas somam o total e as participacoes somam 100%."""
    assert not corpo["truncado"]
    assert corpo["categorias"] == len(corpo["linhas"])
    assert sum(linha["valor"] for linha in corpo["linhas"]) == corpo["total"]
    assert sum(linha["participacao"] for linha in corpo["linhas"]) == pytest.approx(100)


# --- Cursos -----------------------------------------------------------------------------------


def test_composicao_por_grau(cliente: TestClient) -> None:
    corpo = _composicao(cliente, "matriculas", f"por=grau&recorte=oferta&{TODAS}")
    assert corpo["ficha"] == "IND-R-05"
    assert corpo["nivel"] == "brasil"
    assert _valores(corpo) == {
        "bacharelado": 6_392_793,
        "tecnologico": 2_054_437,
        "licenciatura": 1_718_590,
        "nao_aplicavel": 61_446,
    }
    assert corpo["total"] == 10_227_266
    _fecha(corpo)
    assert corpo["linhas"][0]["participacao"] == pytest.approx(62.507, abs=1e-3)

    cursos = _composicao(cliente, "cursos", f"por=grau&recorte=oferta&{TODAS}")
    assert _valores(cursos) == {
        "bacharelado": 27_453,
        "tecnologico": 10_530,
        "licenciatura": 7_789,
        "nao_aplicavel": 4,
    }
    assert cursos["total"] == 45_776


def test_composicao_por_area_cine(cliente: TestClient) -> None:
    corpo = _composicao(cliente, "matriculas", f"por=area&recorte=oferta&{TODAS}")
    assert corpo["ficha"] == "IND-R-06"
    # Os literais do catalogo sao exatamente os pares (codigo, nome) do dado.
    assert {(int(linha["codigo"]), linha["nome"]) for linha in corpo["linhas"]} == set(
        AREA_CINE.values()
    )
    assert corpo["total"] == 10_227_266
    _fecha(corpo)
    valores = _valores(corpo)
    assert valores["4"] == 2_755_740
    assert valores["9"] == 2_345_749

    # 'Programas basicos' (ABI): matriculas sem marcador de curso — os 374 de IND-D-02.
    assert valores["0"] == 61_053
    cursos = _composicao(cliente, "cursos", f"por=area&recorte=oferta&{TODAS}")
    assert _valores(cursos)["0"] == 0
    assert cursos["total"] == 45_776
    assert any("Programas básicos" in nota for nota in cursos["notas"])


def test_filtros_de_area_e_de_grau_particionam_o_total(cliente: TestClient) -> None:
    base = f"por=dimensao&recorte=oferta&{TODAS}"
    por_area = [_composicao(cliente, "matriculas", f"{base}&area={a}")["total"] for a in AREA_CINE]
    assert sum(por_area) == 10_227_266
    assert all(total > 0 for total in por_area)
    por_grau = [
        _composicao(cliente, "matriculas", f"{base}&grau={g}")["total"] for g in ROTULO_GRAU
    ]
    assert sum(por_grau) == 10_227_266
    assert all(total > 0 for total in por_grau)

    cruzado = _composicao(
        cliente, "matriculas", f"por=grau&recorte=oferta&{TODAS}&area=educacao&grau=licenciatura"
    )
    assert cruzado["filtros"]["area"] == "Educação"
    assert cruzado["filtros"]["grau"] == "Licenciatura"
    assert [linha["codigo"] for linha in cruzado["linhas"]] == ["licenciatura"]


def test_composicao_por_dimensao_de_oferta(cliente: TestClient) -> None:
    corpo = _composicao(cliente, "matriculas", f"por=dimensao&recorte=oferta&{TODAS}")
    assert corpo["ficha"] == "IND-R-04"
    assert _valores(corpo) == {
        "ead_polo": 5_186_852,
        "presencial": 5_037_875,
        "ead_exterior": 2_539,
        "ead_nacional": 0,
    }
    _fecha(corpo)
    vagas = _composicao(cliente, "vagas", f"por=dimensao&recorte=oferta&{TODAS}")
    assert _valores(vagas)["ead_nacional"] == 18_583_348
    assert vagas["total"] == 23_665_419


def test_ranking_por_rotulo_cine(cliente: TestClient) -> None:
    corpo = _composicao(cliente, "matriculas", f"por=rotulo_cine&recorte=oferta&{TODAS}&limite=5")
    assert corpo["categorias"] == 353
    assert corpo["truncado"]
    assert corpo["total"] == 10_227_266  # total e participacao consideram os 353 rotulos
    primeira = corpo["linhas"][0]
    assert (primeira["codigo"], primeira["nome"], primeira["grupo"], primeira["valor"]) == (
        "0113P01",
        "Pedagogia",
        "Educação",
        887_695,
    )
    assert primeira["participacao"] == pytest.approx(887_695 / 10_227_266 * 100)
    assert [linha["nome"] for linha in corpo["linhas"][1:3]] == ["Administração", "Direito"]

    inteira = _composicao(cliente, "matriculas", f"por=rotulo_cine&recorte=oferta&{TODAS}")
    assert len(inteira["linhas"]) == 353
    _fecha(inteira)


@pytest.mark.parametrize(
    ("filtro", "nivel"),
    [("uf=DF", "uf"), ("regiao=sul", "regiao"), ("municipio=5300108", "municipio")],
)
@pytest.mark.parametrize("slug", ["matriculas", "ingressantes", "concluintes"])
def test_composicao_fecha_com_o_indicador_do_territorio(
    cliente: TestClient, slug: str, filtro: str, nivel: str
) -> None:
    direto = _get(
        cliente, f"indicadores/{slug}?nivel={nivel}&recorte=oferta&{TERRITORIAIS}&{filtro}"
    )
    for eixo in ("grau", "dimensao", "rede", "categoria", "organizacao"):
        corpo = _composicao(cliente, slug, f"por={eixo}&recorte=oferta&{TERRITORIAIS}&{filtro}")
        assert corpo["nivel"] == nivel
        assert corpo["total"] == direto["total"], eixo
        _fecha(corpo)


# --- Instituicoes -----------------------------------------------------------------------------


def test_composicao_de_ies_por_categoria_e_organizacao(cliente: TestClient) -> None:
    categoria = _composicao(cliente, "ies", "por=categoria&recorte=sede")
    assert _valores(categoria) == {
        "privada_com_fins_lucrativos": 1_486,
        "privada_sem_fins_lucrativos": 758,
        "publica_estadual": 139,
        "publica_federal": 122,
        "publica_municipal": 28,
        "especial": 28,
    }
    _fecha(categoria)
    organizacao = _composicao(cliente, "ies", "por=organizacao&recorte=sede")
    assert _valores(organizacao) == {
        "faculdade": 1_897,
        "centro_universitario": 417,
        "universidade": 206,
        "instituto_federal": 39,
        "cefet": 2,
    }
    rede = _composicao(cliente, "ies", "por=rede&recorte=sede")
    assert _valores(rede) == {"privada": 2_244, "publica": 317}
    sp = _composicao(cliente, "ies", "por=organizacao&recorte=sede&uf=SP")
    assert sp["total"] == _get(cliente, "indicadores/ies?nivel=uf&recorte=sede&uf=SP")["total"]


def test_titulacao_docente_particiona_o_total(cliente: TestClient) -> None:
    corpo = _composicao(cliente, "docentes", "por=titulacao&recorte=sede")
    assert corpo["ficha"] == "IND-R-12"
    # Ordem natural da titulacao, nao por valor.
    assert [linha["codigo"] for linha in corpo["linhas"]] == [t[0] for t in TITULACOES]
    assert _valores(corpo) == {
        "sem_graduacao": 73,
        "graduacao": 2_148,
        "especializacao": 52_107,
        "mestrado": 121_654,
        "doutorado": 198_519,
    }
    assert corpo["total"] == 374_501
    _fecha(corpo)

    # Fecha com IND-D-08 em toda UF: a decomposicao e particao exata tambem por territorio.
    ufs = _get(cliente, "indicadores/docentes?nivel=uf&recorte=sede")["linhas"]
    assert len(ufs) == 27
    for linha in ufs:
        uf = _composicao(cliente, "docentes", f"por=titulacao&recorte=sede&uf={linha['uf']}")
        assert uf["total"] == linha["valor"], linha["uf"]


def test_tabela_de_instituicoes_preserva_as_somas_de_controle(cliente: TestClient) -> None:
    corpo = _get(cliente, f"instituicoes?{TODAS}")
    assert corpo["recorte"] == "sede"
    assert corpo["totais"] == {
        "ies": 2_561,
        "ies_com_oferta": 2_561,
        "docentes": 374_501,
        "tecnicos": 350_752,
        "cursos": 45_776,
        "matriculas": 10_227_266,
        "ingressantes": 5_010_613,
        "concluintes": 1_333_988,
    }
    assert corpo["ordem"] == "matriculas"
    assert (corpo["pagina"], corpo["limite"], corpo["paginas"]) == (1, 25, 103)
    primeira = corpo["linhas"][0]
    assert (primeira["co_ies"], primeira["sigla"], primeira["matriculas"]) == (
        298,
        "Unopar",
        843_645,
    )
    assert (primeira["uf"], primeira["municipio_codigo"]) == ("PR", "4113700")
    assert any("IND-Q-03" in nota for nota in corpo["notas"])


def test_join_cursos_ies_nao_duplica_nem_perde_linhas(cliente: TestClient) -> None:
    """Percorre todas as paginas: 2.561 IES distintas, e as colunas somam os totais nacionais."""
    linhas: list[dict[str, Any]] = []
    for pagina in range(1, 27):
        corpo = _get(cliente, f"instituicoes?{TODAS}&limite=100&pagina={pagina}&ordem=nome")
        linhas += corpo["linhas"]
    assert corpo["paginas"] == 26
    assert len(linhas) == 2_561
    assert len({linha["co_ies"] for linha in linhas}) == 2_561
    for coluna, total in [
        ("docentes", 374_501),
        ("tecnicos", 350_752),
        ("cursos", 45_776),
        ("matriculas", 10_227_266),
        ("ingressantes", 5_010_613),
        ("concluintes", 1_333_988),
    ]:
        assert sum(linha[coluna] for linha in linhas) == total, coluna
    assert sum(1 for linha in linhas if linha["sigla"] is None) == 459
    assert sum(1 for linha in linhas if linha["matriculas"] == 0) == 15
    assert _get(cliente, f"instituicoes?{TODAS}&limite=100&pagina=27")["linhas"] == []


def test_instituicoes_sem_oferta_na_dimensao_ficam_nulas(cliente: TestClient) -> None:
    presencial = _get(cliente, "instituicoes?dimensao=presencial")["totais"]
    assert (presencial["ies"], presencial["ies_com_oferta"]) == (2_561, 2_444)
    assert (presencial["cursos"], presencial["matriculas"]) == (34_479, 5_037_875)
    # Pessoal vem da tabela de IES e nao depende da dimensao de oferta.
    assert (presencial["docentes"], presencial["tecnicos"]) == (374_501, 350_752)

    exterior = _get(cliente, "instituicoes?dimensao=ead_exterior&limite=100")
    assert exterior["totais"]["ies_com_oferta"] == 27
    assert exterior["totais"]["matriculas"] == 2_539
    com_oferta = [linha for linha in exterior["linhas"] if linha["matriculas"] is not None]
    assert len(com_oferta) == 27
    # Ausencia de oferta na dimensao e nula (nao zero) e fica no fim da ordenacao.
    assert exterior["linhas"][:27] == com_oferta
    assert exterior["linhas"][27]["cursos"] is None


def test_instituicoes_filtram_pela_sede(cliente: TestClient) -> None:
    df = _get(cliente, f"instituicoes?{TODAS}&uf=DF&ordem=docentes&limite=100")
    # Com territorio, a oferta somada das IES nao e publicada como total: so as 100 maiores IES
    # com sede no PR somam mais de 3 vezes as 711.466 matriculas ofertadas no PR (IND-D-03).
    pr = _get(cliente, f"instituicoes?{TODAS}&uf=PR&limite=100")
    assert sum(linha["matriculas"] for linha in pr["linhas"]) > 3 * 711_466
    oferta_pr = _get(
        cliente, f"indicadores/matriculas?nivel=uf&recorte=oferta&{TERRITORIAIS}&uf=PR"
    )
    assert oferta_pr["total"] == 711_466
    for coluna in ("cursos", "matriculas", "ingressantes", "concluintes"):
        assert pr["totais"][coluna] is None
        assert df["totais"][coluna] is None
    assert (
        df["totais"]["ies"] == _get(cliente, "indicadores/ies?nivel=uf&recorte=sede&uf=DF")["total"]
    )
    assert (
        df["totais"]["docentes"]
        == _get(cliente, "indicadores/docentes?nivel=uf&recorte=sede&uf=DF")["total"]
    )
    assert {linha["uf"] for linha in df["linhas"]} == {"DF"}
    docentes = [linha["docentes"] for linha in df["linhas"]]
    assert docentes == sorted(docentes, reverse=True)

    federais = _get(cliente, f"instituicoes?{TODAS}&categoria=publica_federal&rede=publica")
    assert federais["totais"]["ies"] == 122
    assert any("Especial" in nota for nota in federais["notas"])
    nomes = [linha["nome"] for linha in _get(cliente, f"instituicoes?{TODAS}&ordem=nome")["linhas"]]
    assert nomes[0].startswith("ABEU")


@pytest.mark.parametrize(
    ("caminho", "trecho"),
    [
        # eixo incompativel com a tabela ou com o indicador
        ("indicadores/ies/composicao?por=grau&recorte=sede", "composição"),
        ("indicadores/ies/composicao?por=titulacao&recorte=sede", "composição"),
        (f"indicadores/matriculas/composicao?por=titulacao&recorte=oferta&{TODAS}", "composição"),
        ("indicadores/docentes/composicao?por=rede&recorte=sede&area=saude", "área CINE"),
        ("indicadores/ies/composicao?por=rede&recorte=sede&grau=bacharelado", "grau"),
        # as mesmas regras do indicador direto
        ("indicadores/matriculas/composicao?por=grau&recorte=oferta", "dimensao"),
        ("indicadores/matriculas/composicao?por=grau&recorte=sede&dimensao=presencial", "recorte"),
        (
            "indicadores/cursos/composicao?por=grau&recorte=oferta&dimensao=ead_nacional&uf=DF",
            "territorializ",
        ),
        ("indicadores/ies/composicao?por=rede&recorte=sede&uf=DF&regiao=sul", "Centro-Oeste"),
        # CINE no nivel municipal: piso de supressao pendente
        (
            "indicadores/matriculas/composicao?por=area&recorte=oferta&dimensao=presencial&municipio=5300108",
            "supressão",
        ),
        (
            "indicadores/matriculas/composicao?por=rotulo_cine&recorte=oferta&dimensao=presencial&municipio=5300108",
            "supressão",
        ),
        (
            "indicadores/matriculas/composicao?por=grau&recorte=oferta&dimensao=presencial&municipio=5300108&area=saude",
            "supressão",
        ),
        # parametros fechados
        ("indicadores/ies/composicao?recorte=sede", "por"),
        ("indicadores/ies/composicao?por=turno&recorte=sede", "por"),
        (f"indicadores/matriculas/composicao?por=grau&recorte=oferta&{TODAS}&area=Saúde", "area"),
        (
            f"indicadores/matriculas/composicao?por=grau&recorte=oferta&{TODAS}&grau=x' OR 1=1 --",
            "grau",
        ),
        (f"indicadores/matriculas/composicao?por=grau&recorte=oferta&{TODAS}&limite=401", "limite"),
        ("instituicoes", "dimensao"),
        (f"instituicoes?{TODAS}&ordem=no_ies", "ordem"),
        (f"instituicoes?{TODAS}&ordem=nome; DROP TABLE x", "ordem"),
        (f"instituicoes?{TODAS}&limite=101", "limite"),
        (f"instituicoes?{TODAS}&pagina=0", "pagina"),
        (f"instituicoes?{TODAS}&uf=DF&regiao=sul", "Centro-Oeste"),
        (f"instituicoes?{TODAS}&rede=privada&categoria=publica_federal", "rede"),
    ],
)
def test_combinacoes_recusadas(cliente: TestClient, caminho: str, trecho: str) -> None:
    r = cliente.get(f"/api/v1/{caminho}")
    assert r.status_code == 422, r.text
    erro = r.json()["erro"]
    assert trecho in erro["mensagem"]
    assert "SELECT" not in erro["mensagem"]


def test_composicao_de_slug_desconhecido(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/indicadores/qt_mat/composicao?por=grau&recorte=oferta")
    assert r.status_code == 404
    assert "qt_mat" not in r.text


def test_metadados_publicam_areas_e_graus(cliente: TestClient) -> None:
    meta = _get(cliente, "metadados")
    assert [(a["slug"], a["codigo"], a["nome"]) for a in meta["areas_cine"]] == [
        (str(slug), codigo, nome) for slug, (codigo, nome) in AREA_CINE.items()
    ]
    assert {g["slug"]: g["rotulo"] for g in meta["graus"]} == {
        str(g): r for g, r in ROTULO_GRAU.items()
    }


def test_instituicoes_por_rede_fecham_com_cursos(cliente: TestClient) -> None:
    """Ponte ds_rede <-> tp_rede: a oferta das IES de uma rede e a oferta dessa rede em cursos."""
    for rede in ("publica", "privada"):
        ies = _get(cliente, f"instituicoes?{TODAS}&rede={rede}")["totais"]
        for slug in ("cursos", "matriculas", "ingressantes", "concluintes"):
            direto = _get(
                cliente, f"indicadores/{slug}?nivel=brasil&recorte=oferta&{TODAS}&rede={rede}"
            )
            assert ies[slug] == direto["total"], (rede, slug)


@pytest.mark.parametrize(
    "ordem", ["matriculas", "cursos", "ingressantes", "concluintes", "tecnicos"]
)
def test_paginacao_sem_duplicatas_com_nulos_e_empates(cliente: TestClient, ordem: str) -> None:
    vistos: list[int] = []
    for pagina in range(1, 27):
        corpo = _get(
            cliente, f"instituicoes?dimensao=ead_polo&limite=100&pagina={pagina}&ordem={ordem}"
        )
        vistos += [linha["co_ies"] for linha in corpo["linhas"]]
    assert len(vistos) == len(set(vistos)) == 2_561


def test_zeros_estruturais_sao_declarados(cliente: TestClient) -> None:
    polo = _get(cliente, "instituicoes?dimensao=ead_polo")
    assert polo["totais"]["cursos"] == 0
    assert any("marcador de curso" in nota for nota in polo["notas"])
    nacional = _get(cliente, "instituicoes?dimensao=ead_nacional")
    assert nacional["totais"]["matriculas"] == 0
    assert any("não registra matrículas" in nota for nota in nacional["notas"])
    todas = _get(cliente, f"instituicoes?{TODAS}")
    assert not any("estrutura da base" in nota or "marcador" in nota for nota in todas["notas"])


def test_eixo_dimensao_so_e_ind_r_04_com_as_dimensoes_inteiras(cliente: TestClient) -> None:
    inteira = _composicao(
        cliente, "matriculas", f"por=dimensao&recorte=oferta&{TERRITORIAIS}&uf=DF"
    )
    assert inteira["ficha"] == "IND-R-04"
    filtrada = _composicao(cliente, "matriculas", "por=dimensao&recorte=oferta&dimensao=presencial")
    assert filtrada["ficha"] is None
    assert any("IND-R-04" in nota for nota in filtrada["notas"])
    # Vagas so existem territorializadas no presencial: 100% por construcao, nao e IND-R-04.
    vagas = _composicao(cliente, "vagas", "por=dimensao&recorte=oferta&dimensao=presencial&uf=DF")
    assert vagas["ficha"] is None
    assert [linha["codigo"] for linha in vagas["linhas"]] == ["presencial"]


@pytest.mark.parametrize("slug", ["cursos", "vagas", "inscricoes"])
def test_composicao_so_presencial_fecha_com_o_indicador(cliente: TestClient, slug: str) -> None:
    direto = _get(cliente, f"indicadores/{slug}?nivel=uf&recorte=oferta&dimensao=presencial&uf=SP")
    for eixo in ("grau", "area", "rede"):
        corpo = _composicao(cliente, slug, f"por={eixo}&recorte=oferta&dimensao=presencial&uf=SP")
        assert corpo["total"] == direto["total"], eixo
        _fecha(corpo)


def test_titulacao_truncada_e_com_total_zero(cliente: TestClient) -> None:
    truncada = _composicao(cliente, "docentes", "por=titulacao&recorte=sede&limite=2")
    assert truncada["truncado"]
    assert (len(truncada["linhas"]), truncada["categorias"], truncada["total"]) == (2, 5, 374_501)


def test_bloqueio_cine_municipal_e_provisorio_e_por_nivel(cliente: TestClient) -> None:
    """Registra o limite conhecido: o DF tem um unico municipio de oferta, e a UF nao e bloqueada."""
    r = cliente.get(
        "/api/v1/indicadores/matriculas/composicao"
        f"?por=area&recorte=oferta&{TERRITORIAIS}&municipio=5300108"
    )
    assert r.status_code == 422
    assert "provisório" in r.json()["erro"]["mensagem"]
    df = _composicao(cliente, "matriculas", f"por=area&recorte=oferta&{TERRITORIAIS}&uf=DF")
    assert df["total"] == 248_333
