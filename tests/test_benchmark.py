"""Benchmark da Fase 14: criterios de correcao, estatistica e integridade do conjunto de teste.

Nenhum teste chama um modelo. Os marcados `dados` usam a camada analitica local.
"""

import json
from collections.abc import Iterator
from decimal import Decimal

import pytest

from api.analista.pipeline import _sem_llm
from api.analista.plano import interpretar_plano
from api.config import Settings
from api.db import BaseAnalitica
from api.semantica import recuperar_contexto
from benchmark.avaliacao import (
    diferencas_de_plano,
    ha_empate_na_ordem,
    mesmo_resultado,
    plano_canonico,
)
from benchmark.casos import CASOS, casos
from benchmark.executar import medir_caso, referencia, validar_conjunto
from benchmark.provedor import ProvedorRoteirizado
from benchmark.relatorio import (
    acertos,
    cochran_q,
    holm,
    mcnemar_exato,
    percentil,
    qui2_cauda,
    wilson,
)
from tests.apoio_analista import dims, filtro, plano_dict

# --- plano canonico -------------------------------------------------------------------------------


def test_plano_canonico_ignora_ordem_de_listas_e_dica_de_visualizacao() -> None:
    a = plano_dict(
        metrics=["vagas", "inscricoes"],
        dimensions=dims("oferta", "brasil", "presencial", "ead_nacional"),
        filters=[filtro("rede", "privada"), filtro("uf", "SP", "RJ")],
        visualization_hint="table",
    )
    b = plano_dict(
        metrics=["inscricoes", "vagas"],
        dimensions=dims("oferta", "brasil", "ead_nacional", "presencial"),
        filters=[filtro("uf", "RJ", "SP"), filtro("rede", "privada")],
    )
    assert plano_canonico(a) == plano_canonico(b)


@pytest.mark.parametrize(
    ("mudanca", "campo"),
    [
        ({"intent": "distribuicao"}, "intent"),
        ({"metrics": ["ingressantes"]}, "metrics"),
        ({"dimensions": dims("oferta", "uf", "presencial")}, "nivel_territorial"),
        ({"dimensions": dims("oferta", "brasil", "ead_polo")}, "dimensao_de_oferta"),
        ({"filters": [filtro("rede", "publica")]}, "filters"),
        ({"group_by": ["grau"]}, "group_by"),
        ({"having": [{"metrica": "matriculas", "operador": ">=", "valor": 10}]}, "having"),
        ({"order_by": [{"por": "matriculas", "direcao": "asc"}]}, "order_by"),
        ({"limit": 5}, "limit"),
    ],
)
def test_diferenca_de_plano_aponta_o_campo(mudanca: dict[str, object], campo: str) -> None:
    base = plano_dict(
        filters=[filtro("rede", "privada")],
        having=[{"metrica": "matriculas", "operador": ">", "valor": 10}],
        order_by=[{"por": "matriculas", "direcao": "desc"}],
    )
    obtido = plano_canonico({**base, **mudanca})
    assert diferencas_de_plano(obtido, plano_canonico(base)) == [campo]


def test_limite_omitido_equivale_ao_padrao() -> None:
    assert plano_canonico(plano_dict()) == plano_canonico(plano_dict(limit=100))


# --- comparacao de resultados ---------------------------------------------------------------------

_COLS = ["uf_codigo", "matriculas"]


def test_resultado_e_multiconjunto_quando_nao_ordenado() -> None:
    ref = [("SP", 10), ("RJ", 5)]
    assert mesmo_resultado(_COLS, ref, _COLS, [["RJ", 5], ["SP", 10]], ["matriculas"], False)
    assert not mesmo_resultado(_COLS, ref, _COLS, [["RJ", 5], ["SP", 10]], ["matriculas"], True)


def test_resultado_projeta_pelo_nome_e_ignora_colunas_extras() -> None:
    ref = [("SP", 10)]
    colunas = ["uf_codigo", "uf", "matriculas"]
    assert mesmo_resultado(_COLS, ref, colunas, [["SP", "São Paulo", 10]], ["matriculas"], False)
    assert not mesmo_resultado(
        _COLS, ref, ["uf", "matriculas"], [["SP", 10]], ["matriculas"], False
    )


@pytest.mark.parametrize(
    "linhas",
    [
        [["SP", 11]],  # valor errado
        [["RJ", 10]],  # chave errada
        [["SP", 10], ["SP", 10]],  # linha a mais (multiconjunto, nao conjunto)
        [],  # linha a menos
    ],
)
def test_resultado_diferente_e_reprovado(linhas: list[list[object]]) -> None:
    assert not mesmo_resultado(_COLS, [("SP", 10)], _COLS, linhas, ["matriculas"], False)


def test_tipos_numericos_equivalentes_e_arredondamento_de_razao() -> None:
    cols = ["regiao_codigo", "razao"]
    ref = [(3, Decimal("10")), (4, 0.123449)]
    # Chave inteira x texto; Decimal x int; razao arredondada a 4 casas na resposta.
    assert mesmo_resultado(cols, ref, cols, [["3", 10], ["4", 0.1234]], ["razao"], False)
    assert not mesmo_resultado(cols, ref, cols, [["3", 10], ["4", 0.1236]], ["razao"], False)


def test_nulo_so_casa_com_nulo() -> None:
    cols = ["rede", "razao"]
    assert mesmo_resultado(cols, [("Privada", None)], cols, [["Privada", None]], ["razao"], False)
    assert not mesmo_resultado(cols, [("Privada", None)], cols, [["Privada", 0]], ["razao"], False)


def test_empate_na_ordem() -> None:
    assert ha_empate_na_ordem(_COLS, [("PE", 118), ("RS", 118)], "matriculas")
    assert not ha_empate_na_ordem(_COLS, [("PE", 118), ("RS", 117)], "matriculas")


# --- estatistica ----------------------------------------------------------------------------------


def test_wilson_bate_com_valores_conhecidos() -> None:
    baixo, alto = wilson(14, 28)
    assert (round(baixo, 3), round(alto, 3)) == (0.326, 0.674)
    assert tuple(round(x, 3) for x in wilson(28, 28)) == (0.879, 1.0)
    assert round(wilson(0, 28)[0], 9) == 0.0


def test_mcnemar_exato() -> None:
    assert mcnemar_exato(0, 0) == 1.0
    assert mcnemar_exato(5, 5) == 1.0
    assert round(mcnemar_exato(0, 6), 4) == 0.0312  # 2 * 0.5**6
    assert round(mcnemar_exato(1, 9), 4) == 0.0215


def test_percentil_e_acerto_estrito() -> None:
    assert percentil([float(i) for i in range(1, 11)], 0.9) == 9.0
    execucoes = [
        {"caso": "A1", "repeticao": 1, "resultado_correto": True},
        {"caso": "A1", "repeticao": 2, "resultado_correto": False},
        {"caso": "A2", "repeticao": 1, "resultado_correto": True},
    ]
    assert acertos(execucoes, "resultado_correto") == {"A1": False, "A2": True}


# --- integridade do conjunto ----------------------------------------------------------------------


def test_ids_e_perguntas_unicos_e_planos_sintaticamente_validos() -> None:
    assert len({c.id for c in CASOS}) == len(CASOS) == len({c.pergunta for c in CASOS})
    for caso in casos("modelo"):
        assert caso.plano is not None
        interpretar_plano(json.dumps(caso.plano))


def test_blocos_separam_o_que_chega_ao_llm() -> None:
    for caso in CASOS:
        chega = _sem_llm(recuperar_contexto(caso.pergunta)) is None
        assert chega == (caso.bloco == "modelo"), caso.id


@pytest.fixture(scope="module")
def base() -> Iterator[BaseAnalitica]:
    s = Settings()
    b = BaseAnalitica(s.analytics_duckdb_path, s.api_query_timeout_seconds)
    yield b
    b.fechar()


@pytest.mark.dados
def test_conjunto_valido_plano_de_referencia_reproduz_sql_de_referencia(
    base: BaseAnalitica,
) -> None:
    assert validar_conjunto(base) == []


@pytest.mark.dados
def test_plano_errado_mas_valido_e_reprovado_no_resultado(base: BaseAnalitica) -> None:
    # H1: SC tem exatamente 100 IES. '>=' passa na validacao e muda o resultado.
    caso = next(c for c in CASOS if c.id == "H1")
    assert caso.plano is not None
    errado = {**caso.plano, "having": [{"metrica": "ies", "operador": ">=", "valor": 100}]}
    r = medir_caso(caso, base, ProvedorRoteirizado(errado), referencia(caso, base))
    assert r["plano_valido"] and r["sql_executavel"]
    assert not (r["plano_correto"] or r["sql_correto"] or r["resultado_correto"])
    assert r["campos_divergentes"] == ["having"]


@pytest.mark.dados
def test_resposta_que_nao_e_plano_reprova_tudo(base: BaseAnalitica) -> None:
    caso = casos("modelo")[0]
    r = medir_caso(caso, base, ProvedorRoteirizado({"oi": 1}), referencia(caso, base))
    assert r["desfecho"] == "resposta_do_modelo_invalida"
    assert not any(r[k] for k in ("json_valido", "plano_valido", "plano_correto", "sql_correto"))


def test_holm_qui_quadrado_e_cochran() -> None:
    assert [round(p, 4) for p in holm([0.01, 0.04, 0.03])] == [0.03, 0.06, 0.06]
    assert holm([0.5, 0.9]) == [1.0, 1.0]
    for x, gl in ((3.841459, 1), (5.991465, 2), (7.814728, 3)):
        assert round(qui2_cauda(x, gl), 4) == 0.05
    # Com dois modelos, Q de Cochran e o qui-quadrado de McNemar: (b - c)^2 / (b + c).
    q = cochran_q([[True, False]] * 4 + [[True, True]] * 3)
    assert q is not None and (q[0], q[1]) == (4.0, 1)
    assert cochran_q([[True, True], [False, False]]) is None
