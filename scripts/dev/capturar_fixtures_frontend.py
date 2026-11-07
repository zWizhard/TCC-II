"""Recaptura as fixtures de teste do frontend a partir da API real.

As fixtures de `frontend/src/test/fixtures/` sao respostas reais, nunca escritas a mao. Este
script sobe a API em processo (TestClient) sobre o DuckDB local e grava as respostas das
consultas que os testes do frontend fazem. Rodar sempre que o contrato da API mudar:

    .venv/Scripts/python.exe scripts/dev/capturar_fixtures_frontend.py
    (em frontend/)  npx prettier --write src/test/fixtures

A ordem dos parametros replica `montarParametrosIndicador` (frontend/src/lib/api/client.ts):
se as duas divergirem, o teste do frontend falha por fixture ausente — nao passa em silencio.
"""

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from api.config import Settings  # noqa: E402
from api.main import create_app  # noqa: E402

DESTINO = RAIZ / "frontend" / "src" / "test" / "fixtures"
DIMENSOES = ["presencial", "ead_polo", "ead_nacional", "ead_exterior"]
# Dimensoes com territorio: as unicas em que o coropletico (IND-R-01) existe.
DIMENSOES_MAPA = ("presencial", "ead_polo")
ORDEM_FILTROS = ("rede", "categoria", "organizacao", "regiao", "uf", "municipio", "limite")


def url_indicador(ind: dict[str, Any], nivel: str, **filtros: str | int) -> str:
    qs: list[tuple[str, str]] = [("nivel", nivel), ("recorte", ind["recorte"])]
    if ind["exige_dimensao"]:
        admitidas = DIMENSOES if nivel == "brasil" else ind["dimensoes_territoriais"]
        qs += [("dimensao", d) for d in DIMENSOES if d in admitidas]
    qs += [(k, str(filtros[k])) for k in ORDEM_FILTROS if k in filtros]
    return f"/api/v1/indicadores/{ind['slug']}?{urlencode(qs)}"


ORDEM_COMPOSICAO = (*ORDEM_FILTROS[:-1], "area", "grau", "limite")
ORDEM_INSTITUICOES = (*ORDEM_FILTROS[:-1], "ordem", "limite", "pagina")


def url_composicao(
    ind: dict[str, Any], eixo: str, nivel: str = "brasil", **filtros: str | int
) -> str:
    """Replica `montarParametrosComposicao`; `nivel` so decide as dimensoes admitidas."""
    qs: list[tuple[str, str]] = [("por", eixo), ("recorte", ind["recorte"])]
    if ind["exige_dimensao"]:
        admitidas = DIMENSOES if nivel == "brasil" else ind["dimensoes_territoriais"]
        qs += [("dimensao", d) for d in DIMENSOES if d in admitidas]
    qs += [(k, str(filtros[k])) for k in ORDEM_COMPOSICAO if k in filtros]
    return f"/api/v1/indicadores/{ind['slug']}/composicao?{urlencode(qs)}"


def url_instituicoes(**filtros: str | int) -> str:
    """Replica `montarParametrosInstituicoes`, com todas as dimensoes selecionadas."""
    qs = [("dimensao", d) for d in DIMENSOES]
    qs += [(k, str(filtros[k])) for k in ORDEM_INSTITUICOES if k in filtros]
    return f"/api/v1/instituicoes?{urlencode(qs)}"


def url_razao(
    razao: dict[str, Any],
    nivel: str = "brasil",
    fixa: str | None = None,
    base: str | None = None,
    por: str | None = None,
    **filtros: str | int,
) -> str:
    """Replica `montarParametrosRazao` + `resolverDimensoesRazao`, com todas as dimensoes
    selecionadas. `nivel` e o da consulta: o de `por`, se territorial; senao o do territorio."""
    admitidas = [
        d for d in razao["dimensoes"] if nivel == "brasil" or d in razao["dimensoes_territoriais"]
    ]
    qs: list[tuple[str, str]] = [("recorte", razao["recorte"])]
    qs += [("dimensao", d) for d in DIMENSOES if d in admitidas and fixa in (None, d)]
    if razao["usa_base"] and base:
        qs.append(("base", base))
    if por:
        qs.append(("por", por))
    qs += [(k, str(filtros[k])) for k in ORDEM_FILTROS if k in filtros]
    return f"/api/v1/razoes/{razao['slug']}?{urlencode(qs)}"


def gravar(nome: str, corpo: Any) -> None:
    # Compacto de proposito: quem define a quebra de linha e o prettier do frontend.
    (DESTINO / nome).write_text(
        json.dumps(corpo, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    with TestClient(create_app(Settings())) as cliente:

        def get(caminho: str, status: int = 200) -> Any:
            r = cliente.get(caminho)
            assert r.status_code == status, f"{caminho} -> {r.status_code}: {r.text[:200]}"
            return r.json()

        catalogo = get("/api/v1/indicadores")
        por_slug = {i["slug"]: i for i in catalogo}
        ies, matriculas = por_slug["ies"], por_slug["matriculas"]

        gravar("health.json", get("/api/health"))
        gravar("metadados.json", get("/api/v1/metadados"))
        gravar("indicadores.json", catalogo)
        gravar("ies-brasil.json", get(url_indicador(ies, "brasil")))
        gravar("ies-uf-publica.json", get(url_indicador(ies, "uf", rede="publica")))
        gravar("matriculas-brasil.json", get(url_indicador(matriculas, "brasil")))
        gravar("matriculas-regiao.json", get(url_indicador(matriculas, "regiao")))
        gravar("municipios-df.json", get("/api/v1/territorios/municipios?uf=DF"))
        gravar(
            "erro-422.json",
            get("/api/v1/indicadores/vagas?nivel=uf&recorte=oferta&dimensao=ead_polo", 422),
        )

        # /painel sem filtros: KPIs do Brasil + distribuicao do primeiro indicador.
        padrao = ["/api/v1/metadados", "/api/v1/indicadores"]
        padrao += [url_indicador(i, "brasil") for i in catalogo]
        padrao += [url_indicador(ies, "regiao"), url_indicador(ies, "uf")]
        gravar("painel-padrao.json", {c: get(c) for c in padrao})

        # /painel com territorio (UF = DF) e com filtro institucional (categoria).
        filtrado = ["/api/v1/metadados", "/api/v1/indicadores"]
        filtrado += ["/api/v1/territorios/municipios?uf=DF"]
        filtrado += [url_indicador(i, "uf", uf="DF") for i in catalogo]
        filtrado += [url_indicador(ies, "municipio", uf="DF", limite=20)]
        filtrado += [url_indicador(i, "regiao", regiao="centro_oeste") for i in catalogo]
        filtrado += [url_indicador(ies, "uf", regiao="centro_oeste")]
        filtrado += [url_indicador(i, "municipio", uf="DF", municipio="5300108") for i in catalogo]
        filtrado += [url_indicador(i, "brasil", categoria="publica_federal") for i in catalogo]
        filtrado += [url_indicador(ies, "regiao", categoria="publica_federal")]
        gravar("painel-filtrado.json", {c: get(c) for c in filtrado})

        # /instituicoes: padrao, medida = docentes, ordem, pagina 2 e territorio (UF = DF).
        docentes = por_slug["docentes"]
        base = ["/api/v1/metadados", "/api/v1/indicadores"]
        inst = [*base, "/api/v1/territorios/municipios?uf=DF"]
        for filtros_inst in ({}, {"uf": "DF"}):
            nivel = "uf" if filtros_inst else "brasil"
            inst += [
                url_composicao(ies, e, nivel, **filtros_inst) for e in ("categoria", "organizacao")
            ]
            inst += [url_composicao(docentes, "titulacao", nivel, **filtros_inst)]
            inst += [url_instituicoes(**filtros_inst, limite=25)]
        inst += [url_composicao(docentes, e) for e in ("categoria", "organizacao")]
        inst += [
            url_instituicoes(limite=25, pagina=2),
            url_instituicoes(ordem="docentes", limite=25),
        ]
        gravar("instituicoes.json", {c: get(c) for c in inst})

        # /cursos: padrao (matriculas), indicador = cursos, area = saude e municipio (Brasilia).
        eixos = ("grau", "dimensao", "area", "rotulo_cine")

        def cartoes(ind: dict[str, Any], nivel: str = "brasil", **f: str | int) -> list[str]:
            return [
                url_composicao(ind, e, nivel, **f, **({"limite": 20} if e == "rotulo_cine" else {}))
                for e in eixos
            ]

        cur = [*base, "/api/v1/territorios/municipios?uf=DF"]
        cur += cartoes(matriculas) + cartoes(por_slug["cursos"]) + cartoes(matriculas, area="saude")
        cur += cartoes(matriculas, "uf", uf="DF")
        # No municipio os eixos CINE nao sao consultados (piso de supressao pendente).
        cur += cartoes(matriculas, "municipio", uf="DF", municipio="5300108")[:2]
        gravar("cursos.json", {c: get(c) for c in cur})

        # /matriculas: padrao, base = ingressantes, comparacao por UF e municipio (Brasilia).
        razoes = {r["slug"]: r for r in get("/api/v1/razoes")}
        fluxo = [
            por_slug[s]
            for s in ("matriculas", "ingressantes", "concluintes", "vagas", "inscricoes")
        ]
        perfis = ("sexo", "faixa_etaria", "cor_raca", "procedencia_escolar", "nacionalidade")

        def cartoes_razao(
            base_fluxo: str, por: str, nivel: str = "brasil", **f: str | int
        ) -> list[str]:
            territorial = por in ("regiao", "uf", "municipio")
            n = por if territorial else nivel
            urls = [
                url_razao(razoes[s], n, base=base_fluxo, por=por, **f)
                for s in ("financiamento", "reserva_vagas")
                if nivel != "municipio"
            ]
            urls += [
                url_razao(razoes[s], n, fixa="presencial", por=por, **f)
                for s in ("ingressantes_por_vaga", "inscricoes_por_vaga")
            ]
            if nivel == "brasil":
                # A dimensao sem territorio nao tem comparacao territorial: so o valor geral.
                urls.append(
                    url_razao(
                        razoes["inscricoes_por_vaga"],
                        fixa="ead_nacional",
                        por=None if territorial else por,
                    )
                )
            return urls

        mat = [*base, "/api/v1/razoes", "/api/v1/territorios/municipios?uf=DF"]
        mat += [url_indicador(i, "brasil") for i in fluxo]
        mat += [url_composicao(matriculas, e) for e in perfis]
        mat += [url_composicao(por_slug["ingressantes"], e) for e in (*perfis, "tipo_ingresso")]
        mat += cartoes_razao("matriculas", "rede")
        mat += cartoes_razao("ingressantes", "rede")
        mat += cartoes_razao("matriculas", "uf")
        brasilia = {"uf": "DF", "municipio": "5300108"}
        mat += [url_indicador(i, "municipio", **brasilia) for i in fluxo]
        mat += cartoes_razao("matriculas", "rede", "municipio", **brasilia)
        gravar("matriculas.json", {c: get(c) for c in mat})

        # /mapa: os tres modos no Brasil, no DF (UF pequena) e com um municipio selecionado
        # (Brasilia: o mapa consulta a UF, nunca o municipio).
        def url_coropletico(nivel: str, dims: tuple[str, ...] = DIMENSOES_MAPA, **f: str) -> str:
            """Replica `montarParametrosCoropletico`; o recorte e fixo (IND-R-01 so em oferta)."""
            qs = [("nivel", nivel), ("recorte", "oferta")]
            qs += [("dimensao", d) for d in dims]
            qs += [(k, f[k]) for k in ORDEM_FILTROS if k in f]
            return f"/api/v1/mapa/coropletico?{urlencode(qs)}"

        mapa = [*base, "/api/v1/territorios/municipios?uf=DF", url_indicador(ies, "uf")]
        mapa += [
            url_coropletico("uf"),
            url_coropletico("uf", regiao="centro_oeste"),
            url_coropletico("uf", categoria="especial"),
            url_coropletico("uf", dims=("presencial",)),
            url_coropletico("municipio", uf="DF"),
            url_indicador(ies, "municipio"),
            url_indicador(ies, "municipio", uf="DF"),
            url_indicador(matriculas, "municipio", uf="DF"),
            url_indicador(docentes, "municipio", uf="DF"),
            url_instituicoes(uf="DF", municipio="5300108", limite=10),
        ]
        gravar("mapa.json", {c: get(c) for c in mapa})

        # /comparar: padrao (as cinco regioes), UFs em ordem que nao e a de valor, rede fixada,
        # selecao montada pela tela (SP + DF) e municipios (um sem sede de IES + Brasilia).
        def url_comparacao(nivel: str, *unidades: str, rede: str | None = None) -> str:
            """Replica `montarParametrosComparacao`."""
            qs = [("nivel", nivel), *(("unidade", u) for u in unidades)]
            if rede:
                qs.append(("rede", rede))
            return f"/api/v1/comparacoes?{urlencode(qs)}"

        regioes = [r["slug"] for r in get("/api/v1/metadados")["regioes"]]
        comparar = ["/api/v1/metadados", "/api/v1/territorios/municipios?uf=DF"]
        comparar += [
            url_comparacao("regiao", *regioes),
            url_comparacao("regiao", *regioes, rede="publica"),
            url_comparacao("uf", "RR", "SP", "DF"),
            url_comparacao("uf", "SP", "DF"),
            url_comparacao("municipio", "1100015", "5300108"),
        ]
        gravar("comparar.json", {c: get(c) for c in comparar})

        # Malha: a de UFs inteira (104 KB) e so o DF da municipal (3,9 MB nao viram fixture).
        # Geometria real do IBGE, filtrada pelo codigo — nunca escrita a mao.
        malha_ufs = get("/api/v1/mapa/malha/uf")
        malha_municipios = get("/api/v1/mapa/malha/municipio")
        assert len(malha_ufs["features"]) == 27, len(malha_ufs["features"])
        df = [f for f in malha_municipios["features"] if f["properties"]["codarea"][:2] == "53"]
        assert df, "malha municipal sem feicoes do DF"
        gravar("malha-ufs.json", malha_ufs)
        gravar("malha-df.json", {**malha_municipios, "features": df})

    print(f"fixtures gravadas em {DESTINO}")


if __name__ == "__main__":
    main()
