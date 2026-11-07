"""Regressoes da revisao de seguranca da Fase 13: papel dos numeros, ordem, limite e travas.

Cada teste reproduz um caso em que o plano ERRADO era aceito (ou o certo, rejeitado).
"""

import json
import threading
from typing import Any

import duckdb
import pytest
from apoio_analista import (
    P_IES_BRASIL,
    P_UF_PRIVADA,
    PLANO_IES_BRASIL,
    ProvedorFalso,
    dims,
    filtro,
    plano,
    plano_dict,
    plano_uf_privada,
)
from fastapi.testclient import TestClient

from api.analista import pipeline
from api.analista.analise import interpretar
from api.analista.pipeline import responder
from api.analista.plano import LIMITE_PADRAO, QueryPlan, interpretar_plano
from api.analista.sql import gerar_sql
from api.analista.validacao import PlanoInvalido, pendencias_do_contexto, validar_plano
from api.analista.visualizacao import decidir_spec
from api.erros import (
    ConsultaExcedeuTempo,
    ConsultaFalhou,
    ModeloOcupado,
    RespostaDoModeloInvalida,
)
from api.semantica import recuperar_contexto

URL = "/api/v1/analista/perguntas"
UF_PRESENCIAL = dims("oferta", "uf", "presencial")
MUN_PRESENCIAL = dims("oferta", "municipio", "presencial")


def limiar(operador: str, valor: float, metrica: str = "matriculas") -> dict[str, Any]:
    return {"metrica": metrica, "operador": operador, "valor": valor}


def aceita(pergunta: str, **campos: Any) -> None:
    validar_plano(plano(**campos), recuperar_contexto(pergunta))


def codigos(pergunta: str, **campos: Any) -> set[str]:
    with pytest.raises(PlanoInvalido) as exc:
        validar_plano(plano(**campos), recuperar_contexto(pergunta))
    return exc.value.codigos()


# --- I-4 (a): numero no formato brasileiro e um numero so -----------------------------------------


@pytest.mark.parametrize(
    ("pergunta", "numeros"),
    [
        ("UFs com mais de 100.000 matrículas presenciais", ("100000",)),
        ("UFs com mais de 1.234.567 matrículas presenciais", ("1234567",)),
        ("UFs com pelo menos 1,5 inscrições por vaga presenciais", ("1.5",)),
        ("UFs com mais de 1.234,5 matrículas presenciais", ("1234.5",)),
        ("municípios com mais de 2.000 matrículas presenciais", ("2000",)),
        ("UFs com mais de 100000 matrículas presenciais", ("100000",)),
        # Formato que NAO e brasileiro nao e adivinhado: fica em pedacos e vira esclarecimento.
        ("UFs com mais de 1.5 inscrições por vaga presenciais", ("1", "5")),
    ],
)
def test_numero_brasileiro_e_um_token_so(pergunta: str, numeros: tuple[str, ...]) -> None:
    assert recuperar_contexto(pergunta).numeros == numeros


def test_ano_continua_sendo_ano_e_2024_apos_limiar_e_quantidade() -> None:
    assert recuperar_contexto("matrículas presenciais em 2023").recusa("variacao_temporal")
    assert recuperar_contexto("matrículas presenciais em 2.023").recusa("variacao_temporal")
    base = recuperar_contexto("matrículas presenciais em 2024")
    assert (base.situacao, base.numeros, base.recusas) == ("pronta", (), ())
    # Depois de operador de limiar, 2024 (e 2023) e quantidade — e nao pode sumir.
    for texto in ("2024", "2023", "2.024"):
        c = recuperar_contexto(f"municípios com mais de {texto} matrículas presenciais")
        (n,) = c.numeros_citados
        assert (c.situacao, n.papel, n.sentido) == ("pronta", "limiar", "maior")
        assert n.texto == texto.replace(".", "") and c.recusas == ()


# --- I-4 (b): cada numero tem um papel ------------------------------------------------------------


@pytest.mark.parametrize(
    ("pergunta", "papel", "sentido", "ordem"),
    [
        ("UFs com mais de 100.000 matrículas presenciais", "limiar", "maior", None),
        ("UFs com menos de 100.000 matrículas presenciais", "limiar", "menor", None),
        ("matrículas presenciais por UF acima de 100.000", "limiar", "maior", None),
        ("matrículas presenciais por UF abaixo de 100.000", "limiar", "menor", None),
        ("UFs com pelo menos 100.000 matrículas presenciais", "limiar", "maior", None),
        ("UFs com matrículas presenciais maior que 100.000", "limiar", "maior", None),
        ("top 5 UF com mais matrículas presenciais", "limite", None, "desc"),
        ("os 10 municípios com mais matrículas presenciais", "limite", None, "desc"),
        ("5 maiores UFs em matrículas presenciais", "limite", None, "desc"),
        ("as 3 UFs com menores inscrições por vaga presenciais", "limite", None, "asc"),
        ("matrículas presenciais no município 3550308", "municipio", None, None),
        ("municípios com mais de 3550308 matrículas presenciais", "limiar", "maior", None),
        ("matrículas presenciais 42 por UF", "sem_papel", None, None),
    ],
)
def test_papel_de_cada_numero(
    pergunta: str, papel: str, sentido: str | None, ordem: str | None
) -> None:
    c = recuperar_contexto(pergunta)
    (n,) = c.numeros_citados
    assert (n.papel, n.sentido, c.ordem) == (papel, sentido, ordem)


@pytest.mark.parametrize(
    ("pergunta", "trecho"),
    [
        ("matrículas presenciais 42 por UF", "sem dizer o que ele é"),
        ("os 10 municípios com matrículas presenciais", "por qual ordem"),
        ("matrículas presenciais por UF acima de 100.000 e abaixo de 500.000", "mais de um limiar"),
        ("maiores e menores UFs em matrículas presenciais", "Qual das duas ordens"),
        ("matrículas presenciais por UF e por município", "mais de um nível territorial"),
        ("matrículas e ingressantes presenciais por UF com mais de 100.000", "a qual delas"),
        ("UFs com mais de 1.5 inscrições por vaga presenciais", "sem dizer o que ele é"),
    ],
)
def test_o_que_nao_se_deriva_vira_esclarecimento_antes_do_modelo(
    pergunta: str, trecho: str
) -> None:
    c = recuperar_contexto(pergunta)
    assert c.situacao == "pronta"  # a camada lexica nao ve o problema: quem ve e o analista
    assert any(trecho in x for x in pendencias_do_contexto(c))
    llm = ProvedorFalso(plano_dict())
    r = responder(pergunta, None, llm)  # type: ignore[arg-type]
    assert (r.situacao, llm.chamadas) == ("requer_esclarecimento", [])
    assert any(trecho in x for x in r.esclarecimentos)
    # E, se um plano chegasse ao validador mesmo assim, seria rejeitado.
    assert "contexto_requer_esclarecimento" in codigos(pergunta, **plano_dict())


def test_limiar_100_mil_o_plano_certo_passa_e_os_errados_nao() -> None:
    pergunta = "UFs com mais de 100.000 matrículas presenciais"
    base = {"intent": "distribuicao", "dimensions": UF_PRESENCIAL}
    aceita(pergunta, **base, having=[limiar(">", 100000)])
    aceita(pergunta, **base, having=[limiar(">=", 100000)])
    assert "having_fora_do_contexto" in codigos(pergunta, **base, having=[limiar(">", 100)])
    assert "having_fora_do_contexto" in codigos(pergunta, **base, having=[limiar(">", 0)])
    # Sentido contrario ao da pergunta.
    for operador in ("<", "<=", "="):
        obtidos = codigos(pergunta, **base, having=[limiar(operador, 100000)])
        assert "operador_diverge_do_contexto" in obtidos, operador
    # Limiar descartado.
    assert codigos(pergunta, **base) == {"limiar_do_contexto_omitido"}
    # Dois limiares na mesma metrica (>100000 e <100000 devolveria zero linhas).
    dois = [limiar(">", 100000), limiar("<", 100000)]
    assert "having_repetido" in codigos(pergunta, **base, having=dois)


def test_limiar_menor_e_decimal() -> None:
    pergunta = "matrículas presenciais por UF com menos de 100.000"
    base = {"intent": "distribuicao", "dimensions": UF_PRESENCIAL}
    aceita(pergunta, **base, having=[limiar("<", 100000)])
    assert "operador_diverge_do_contexto" in codigos(pergunta, **base, having=[limiar(">", 100000)])
    pergunta = "UFs com pelo menos 1,5 inscrições por vaga presenciais"
    razao = {**base, "metrics": ["inscricoes_por_vaga"]}
    aceita(pergunta, **razao, having=[limiar(">=", 1.5, "inscricoes_por_vaga")])
    assert "having_fora_do_contexto" in codigos(
        pergunta, **razao, having=[limiar(">=", 15, "inscricoes_por_vaga")]
    )


def test_limiar_2024_nao_some() -> None:
    pergunta = "municípios com mais de 2024 matrículas presenciais"
    base = {"intent": "distribuicao", "dimensions": MUN_PRESENCIAL}
    aceita(pergunta, **base, having=[limiar(">", 2024)])
    assert codigos(pergunta, **base) == {"limiar_do_contexto_omitido"}


def test_os_10_municipios_com_mais_matriculas() -> None:
    pergunta = "os 10 municípios com mais matrículas presenciais"
    base = {"intent": "ranking", "dimensions": MUN_PRESENCIAL}
    desc = [{"por": "matriculas", "direcao": "desc"}]
    aceita(pergunta, **base, order_by=desc, limit=10)
    # 10 e limite: nao pode virar limiar, e o limite nao pode ser outro.
    obtidos = codigos(pergunta, **base, order_by=desc, limit=1000, having=[limiar("<", 10)])
    assert {"having_fora_do_contexto", "limite_diverge_do_contexto"} <= obtidos
    assert codigos(pergunta, **base, order_by=desc) == {"limite_diverge_do_contexto"}
    # 'com mais' e ordem decrescente: crescente devolveria os 10 MENORES.
    asc = [{"por": "matriculas", "direcao": "asc"}]
    assert codigos(pergunta, **base, order_by=asc, limit=10) == {"ordenacao_diverge_do_contexto"}
    sem_ordem = {"intent": "distribuicao", "dimensions": MUN_PRESENCIAL, "limit": 10}
    assert "ordenacao_diverge_do_contexto" in codigos(pergunta, **sem_ordem)
    por_nome = [{"por": "municipio", "direcao": "desc"}]
    assert "ordenacao_diverge_do_contexto" in codigos(pergunta, **base, order_by=por_nome, limit=10)


def test_ordem_crescente_quando_a_pergunta_pede_os_menores() -> None:
    pergunta = "as 3 UFs com menores inscrições por vaga presenciais"
    base = {"intent": "ranking", "metrics": ["inscricoes_por_vaga"], "dimensions": UF_PRESENCIAL}
    aceita(pergunta, **base, order_by=[{"por": "inscricoes_por_vaga", "direcao": "asc"}], limit=3)
    desc = [{"por": "inscricoes_por_vaga", "direcao": "desc"}]
    assert codigos(pergunta, **base, order_by=desc, limit=3) == {"ordenacao_diverge_do_contexto"}


def test_codigo_de_municipio_nao_e_limiar_nem_limite() -> None:
    pergunta = "matrículas presenciais no município 3550308"
    base = {"intent": "distribuicao", "dimensions": MUN_PRESENCIAL}
    aceita(pergunta, **base, filters=[filtro("municipio", "3550308")])
    como_limiar = codigos(pergunta, **base, having=[limiar(">", 3550308)])
    assert {"having_fora_do_contexto", "filtro_do_contexto_omitido"} <= como_limiar
    # E um limiar de 7 digitos nao vira codigo de municipio.
    pergunta = "municípios com mais de 3550308 matrículas presenciais"
    assert "filtro_fora_do_contexto" in codigos(
        pergunta, **base, filters=[filtro("municipio", "3550308")]
    )


def test_sem_numero_na_pergunta_o_limite_e_o_padrao() -> None:
    for limite in (1, 7, 99, 101, 1000):
        assert codigos(P_UF_PRIVADA, **plano_uf_privada(limit=limite)) == {
            "limite_diverge_do_contexto"
        }
    aceita(P_UF_PRIVADA, **plano_uf_privada(limit=LIMITE_PADRAO))
    # Com teto configurado abaixo do padrao, o limite esperado e o teto.
    contexto = recuperar_contexto(P_UF_PRIVADA)
    validar_plano(plano(**plano_uf_privada(limit=10)), contexto, 10)
    with pytest.raises(PlanoInvalido) as exc:
        validar_plano(plano(**plano_uf_privada(limit=5)), contexto, 10)
    assert exc.value.codigos() == {"limite_diverge_do_contexto"}


# --- I-5: metricas, quebras e ordem nao ficam a escolha do modelo ---------------------------------


def test_todas_as_metricas_e_quebras_da_pergunta() -> None:
    pergunta = "matrículas e ingressantes presenciais por rede"
    oferta = dims("oferta", "brasil", "presencial")
    certo = {
        "intent": "distribuicao",
        "metrics": ["matriculas", "ingressantes"],
        "dimensions": oferta,
        "group_by": ["rede"],
    }
    aceita(pergunta, **certo)
    so_uma = codigos(pergunta, metrics=["ingressantes"], dimensions=oferta)
    assert {"metrica_do_contexto_omitida", "agrupamento_do_contexto_omitido"} <= so_uma
    assert codigos(pergunta, **{**certo, "metrics": ["matriculas"]}) == {
        "metrica_do_contexto_omitida"
    }
    sem_quebra = {**certo, "intent": "valor", "group_by": []}
    assert codigos(pergunta, **sem_quebra) == {"agrupamento_do_contexto_omitido"}
    # Dimensao citada como FILTRO nao pode virar quebra.
    assert "agrupamento_fora_do_contexto" in codigos(
        P_UF_PRIVADA, **plano_uf_privada(group_by=["rede"])
    )


def test_ordem_so_quando_a_pergunta_pede() -> None:
    for direcao in ("asc", "desc"):
        ordem = [{"por": "matriculas", "direcao": direcao}]
        obtidos = codigos(P_UF_PRIVADA, **plano_uf_privada(intent="ranking", order_by=ordem))
        assert obtidos == {"ordenacao_diverge_do_contexto"}, direcao
    # Ordenacao fora de um ranking e incoerente.
    ordem = [{"por": "matriculas", "direcao": "desc"}]
    assert "intencao_incoerente" in codigos(P_UF_PRIVADA, **plano_uf_privada(order_by=ordem))
    # 'qual a rede com mais matriculas': ranking decrescente pela metrica, quebra por rede.
    pergunta = "qual a rede com mais matrículas presenciais"
    base = {
        "intent": "ranking",
        "dimensions": dims("oferta", "brasil", "presencial"),
        "group_by": ["rede"],
    }
    aceita(pergunta, **base, order_by=ordem)
    assert "ordenacao_diverge_do_contexto" in codigos(
        pergunta, **{**base, "intent": "distribuicao"}
    )


def test_interpretacao_declara_ordem_e_limite() -> None:
    pergunta = "os 10 municípios com mais matrículas presenciais"
    dados = plano_dict(
        intent="ranking",
        dimensions=MUN_PRESENCIAL,
        order_by=[{"por": "matriculas", "direcao": "desc"}],
        limit=10,
    )
    texto = interpretar(validar_plano(plano(**dados), recuperar_contexto(pergunta)))
    assert "ordenado por Matrículas (decrescente)" in texto and "até 10 linhas" in texto
    padrao = interpretar(
        validar_plano(plano(**plano_uf_privada()), recuperar_contexto(P_UF_PRIVADA))
    )
    assert "decrescente, ordem padrão" in padrao and "até 100 linhas" in padrao
    unico = interpretar(validar_plano(plano(**PLANO_IES_BRASIL), recuperar_contexto(P_IES_BRASIL)))
    assert "ordenado" not in unico and "linhas" not in unico


def test_metrica_fora_da_v1_pedida_nao_e_trocada_pela_base() -> None:
    llm = ProvedorFalso(plano_dict())
    r = responder("participação da rede privada nas matrículas presenciais", None, llm)  # type: ignore[arg-type]
    assert (r.situacao, llm.chamadas) == ("nao_suportada", [])
    r = responder("IES e docentes por UF e matrículas presenciais", None, llm)  # type: ignore[arg-type]
    assert r.situacao != "respondida" and llm.chamadas == []


# --- menores --------------------------------------------------------------------------------------


def test_m1_limiar_tem_teto_de_magnitude() -> None:
    for valor in (1e16, -1e16, 1e300):
        with pytest.raises(RespostaDoModeloInvalida):
            interpretar_plano(json.dumps(plano_dict(having=[limiar(">", valor)])))
    for texto in ('{"valor": NaN}', '{"valor": Infinity}'):
        bruto = json.dumps(plano_dict(having=[limiar(">", 1)])).replace('"valor": 1', texto[1:-1])
        with pytest.raises(RespostaDoModeloInvalida):
            interpretar_plano(bruto)
    assert interpretar_plano(json.dumps(plano_dict(having=[limiar(">", 1e15)]))).having


def test_m7_chave_duplicada_no_json_e_rejeitada() -> None:
    bom = json.dumps(plano_dict())
    assert isinstance(interpretar_plano(bom), QueryPlan)
    casos = [
        bom[:-1] + ', "metrics": ["docentes"]}',  # o parser ficaria com a ultima
        bom.replace('"recorte": "oferta"', '"recorte": "oferta", "recorte": "sede"'),
        bom[:-1] + ', "limit": 5, "limit": 1000}',
    ]
    for texto in casos:
        with pytest.raises(RespostaDoModeloInvalida) as exc:
            interpretar_plano(texto)
        assert exc.value.status == 502


class BaseQueFalha:
    def __init__(self, erro: Exception) -> None:
        self.erro = erro

    def consultar(self, sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        raise self.erro


def test_m1_erro_do_motor_vira_erro_de_dominio() -> None:
    falha: Any = BaseQueFalha(
        duckdb.BinderException("coluna x nao existe em C:/dados/censo.duckdb")
    )
    with pytest.raises(ConsultaFalhou) as exc:
        responder(P_IES_BRASIL, falha, ProvedorFalso(PLANO_IES_BRASIL))
    assert (exc.value.status, exc.value.codigo) == (500, "consulta_falhou")
    assert "coluna x" not in exc.value.mensagem and "C:/" not in exc.value.mensagem


def test_timeout_do_motor_no_fluxo_do_analista() -> None:
    lenta: Any = BaseQueFalha(ConsultaExcedeuTempo("A consulta excedeu o limite de 10 s."))
    with pytest.raises(ConsultaExcedeuTempo) as exc:
        responder(P_IES_BRASIL, lenta, ProvedorFalso(PLANO_IES_BRASIL))
    assert exc.value.status == 504


@pytest.mark.dados
def test_timeout_real_do_motor_interrompe_a_consulta(cliente: TestClient) -> None:
    """O produto cartesiano que o validador agora barra: no motor, o timeout o interrompe."""
    from api.config import Settings
    from api.db import BaseAnalitica

    curta = BaseAnalitica(Settings().analytics_duckdb_path, 0.2)
    try:
        cursos = "inep_educacao_superior_cursos"
        with pytest.raises(ConsultaExcedeuTempo):
            curta.consultar(f"SELECT COUNT(*) FROM {cursos} a, {cursos} b, {cursos} c", {})
    finally:
        curta.fechar()


@pytest.mark.dados
@pytest.mark.parametrize(
    ("erro", "status", "codigo"),
    [
        (
            ConsultaExcedeuTempo("A consulta excedeu o limite de 10 s."),
            504,
            "consulta_excedeu_tempo",
        ),
        (duckdb.ConversionException("detalhe interno do motor"), 500, "consulta_falhou"),
    ],
)
def test_endpoint_falha_do_motor_tem_envelope_proprio(
    erro: Exception, status: int, codigo: str, cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def falhar(sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        raise erro

    monkeypatch.setattr(cliente.app.state.base, "consultar", falhar)  # type: ignore[attr-defined]
    cliente.app.state.provedor_llm = ProvedorFalso(PLANO_IES_BRASIL)  # type: ignore[attr-defined]
    try:
        r = cliente.post(URL, json={"pergunta": P_IES_BRASIL})
    finally:
        cliente.app.state.provedor_llm = None  # type: ignore[attr-defined]
    assert (r.status_code, r.json()["erro"]["codigo"]) == (status, codigo)
    assert "detalhe interno" not in r.text and "Traceback" not in r.text


def test_m3_caracteres_de_controle_nao_chegam_ao_prompt() -> None:
    for pergunta in (
        "IES no Brasil\x00",
        "IES\nno Brasil",
        "IES no \u202eBrasil",
        "IES\u200b no Brasil",
    ):
        llm = ProvedorFalso(PLANO_IES_BRASIL)
        r = responder(pergunta, None, llm)  # type: ignore[arg-type]
        assert (r.situacao, llm.chamadas) == ("pergunta_invalida", [])
        assert r.pergunta.isprintable()  # a resposta nao devolve o caractere


def test_m6_modelo_atende_uma_pergunta_por_vez() -> None:
    entrou, pode_sair = threading.Event(), threading.Event()

    class Lento:
        def gerar_json(self, sistema: str, usuario: str, schema: dict[str, Any]) -> str:
            entrou.set()
            assert pode_sair.wait(5)
            return json.dumps(PLANO_IES_BRASIL)

    base: Any = BaseQueFalha(ConsultaExcedeuTempo("fim do teste"))
    erros: list[BaseException] = []

    def primeira() -> None:
        try:
            responder(P_IES_BRASIL, base, Lento())
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    t = threading.Thread(target=primeira)
    t.start()
    try:
        assert entrou.wait(5)
        segundo = ProvedorFalso(PLANO_IES_BRASIL)
        with pytest.raises(ModeloOcupado) as exc:
            responder(P_IES_BRASIL, base, segundo)
        assert (exc.value.status, exc.value.codigo) == (503, "modelo_ocupado")
        assert segundo.chamadas == []
    finally:
        pode_sair.set()
        t.join(5)
    assert isinstance(erros[0], ConsultaExcedeuTempo)
    # A vaga foi devolvida: a proxima pergunta chega ao modelo, mesmo apos erro na anterior.
    terceiro = ProvedorFalso("não é JSON")
    with pytest.raises(RespostaDoModeloInvalida):
        responder(P_IES_BRASIL, base, terceiro)
    assert len(terceiro.chamadas) == 1
    assert pipeline._VAGA_DO_MODELO.acquire(blocking=False)
    pipeline._VAGA_DO_MODELO.release()


def test_m9_mapa_nao_e_admitido_com_resultado_parcial() -> None:
    v = validar_plano(
        plano(**plano_uf_privada(visualization_hint="map")), recuperar_contexto(P_UF_PRIVADA)
    )
    colunas = gerar_sql(v).colunas
    assert decidir_spec(v, colunas, 27, truncado=False).type == "map"
    parcial = decidir_spec(v, colunas, 27, truncado=True)
    assert parcial.type == "bar" and parcial.notes
    pergunta = "UFs com mais de 100.000 matrículas presenciais"
    dados = plano_dict(
        intent="distribuicao",
        dimensions=UF_PRESENCIAL,
        having=[limiar(">", 100000)],
        visualization_hint="map",
    )
    v = validar_plano(plano(**dados), recuperar_contexto(pergunta))
    filtrado = decidir_spec(v, gerar_sql(v).colunas, 12, truncado=False)
    assert filtrado.type == "bar" and filtrado.notes


@pytest.mark.dados
def test_ponta_a_ponta_limiar_em_formato_brasileiro(cliente: TestClient) -> None:
    pergunta = "UFs com mais de 500.000 matrículas presenciais"
    dados = plano_dict(
        intent="distribuicao", dimensions=UF_PRESENCIAL, having=[limiar(">", 500000)]
    )
    r = responder(pergunta, cliente.app.state.base, ProvedorFalso(dados))  # type: ignore[attr-defined]
    assert r.situacao == "respondida"
    assert [x[0] for x in r.linhas] == ["SP"] and r.linhas[0][2] > 500_000
    assert r.interpretacao is not None and "Matrículas > 500.000" in r.interpretacao
    assert r.consulta is not None and r.consulta.parametros["h0"] == 500000


@pytest.mark.dados
def test_ponta_a_ponta_os_10_municipios_com_mais_matriculas(cliente: TestClient) -> None:
    pergunta = "os 10 municípios com mais matrículas presenciais"
    dados = plano_dict(
        intent="ranking",
        dimensions=MUN_PRESENCIAL,
        order_by=[{"por": "matriculas", "direcao": "desc"}],
        limit=10,
    )
    r = responder(pergunta, cliente.app.state.base, ProvedorFalso(dados))  # type: ignore[attr-defined]
    assert (r.situacao, len(r.linhas), r.truncado) == ("respondida", 10, True)
    valores = [x[1] for x in r.linhas]
    assert valores == sorted(valores, reverse=True) and r.linhas[0][0] == "3550308"  # São Paulo
    invertido = {**dados, "order_by": [{"por": "matriculas", "direcao": "asc"}]}
    r = responder(pergunta, cliente.app.state.base, ProvedorFalso(invertido))  # type: ignore[attr-defined]
    assert r.situacao == "plano_invalido" and r.linhas == ()
