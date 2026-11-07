"""QueryPlan e validacao contra a camada semantica e o contexto. Sem banco e sem LLM."""

import json
from typing import Any

import pytest
from apoio_analista import (
    P_IES_BRASIL,
    P_UF_PRIVADA,
    PLANO_IES_BRASIL,
    dims,
    filtro,
    plano,
    plano_dict,
    plano_uf_privada,
)

from api.analista.plano import LIMITE_PADRAO, TETO_LINHAS, QueryPlan, interpretar_plano
from api.analista.validacao import PlanoInvalido, motivo_fora_da_v1, validar_plano
from api.erros import RespostaDoModeloInvalida
from api.semantica import CAMADA, recuperar_contexto


def codigos(pergunta: str, dados: dict[str, Any], teto: int = TETO_LINHAS) -> set[str]:
    with pytest.raises(PlanoInvalido) as exc:
        validar_plano(interpretar_plano(json.dumps(dados)), recuperar_contexto(pergunta), teto)
    assert all(e.mensagem for e in exc.value.erros)
    return exc.value.codigos()


# --- planos validos -------------------------------------------------------------------------------


def test_plano_valido_passa_e_declara_agrupamentos() -> None:
    v = validar_plano(plano(**plano_uf_privada()), recuperar_contexto(P_UF_PRIVADA))
    assert [m.id for m in v.metricas] == ["matriculas"]
    assert v.territorial is True
    assert v.agrupamentos == ("uf",)


def test_plano_de_ies_nao_tem_dimensao_de_oferta() -> None:
    v = validar_plano(plano(**PLANO_IES_BRASIL), recuperar_contexto(P_IES_BRASIL))
    assert (v.territorial, v.agrupamentos) == (False, ())


def test_limite_tem_padrao_e_plano_e_imutavel() -> None:
    p = plano()
    assert p.limit == LIMITE_PADRAO
    with pytest.raises(ValueError):
        p.limit = 5


# --- o que nem chega a ser um QueryPlan (502) -----------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "isto não é JSON",
        '{"intent": "valor", "entity": "cursos", "metrics": ["matriculas"]',  # truncado
        "[]",  # lista em vez de objeto
        '"só uma string"',
        "{}",  # objeto sem os campos obrigatorios
        json.dumps(plano_dict(sql="SELECT * FROM municipio")),  # campo extra
        json.dumps(plano_dict(intent="apagar")),  # enum desconhecido
        json.dumps(plano_dict(entity="municipio")),
        json.dumps(plano_dict(metrics=[])),
        json.dumps(plano_dict(metrics="matriculas")),
        json.dumps(plano_dict(limit=0)),
        json.dumps(plano_dict(limit="100")),  # modo estrito: texto nao vira numero
        json.dumps(plano_dict(visualization_hint="pie")),
        json.dumps(plano_dict(filters=[filtro("uf", "SP'; DROP TABLE ies;--")])),
        json.dumps(plano_dict(filters=[filtro("uf; DROP TABLE ies", "SP")])),
        json.dumps(plano_dict(metrics=["SUM(qt_mat)"])),
        json.dumps(plano_dict(group_by=["sg_uf, (SELECT 1)"])),
        json.dumps(plano_dict(filters=[{"dimensao": "uf", "valores": []}])),
        json.dumps(plano_dict(having=[{"metrica": "matriculas", "operador": "LIKE", "valor": 1}])),
        json.dumps(plano_dict(having=[{"metrica": "matriculas", "operador": ">", "valor": "1"}])),
        json.dumps(plano_dict(order_by=[{"por": "matriculas", "direcao": "desc; --"}])),
        # Recorte e dimensao de oferta sao obrigatorios e nao tem padrao (ADR-0004).
        json.dumps(
            plano_dict(dimensions={"nivel_territorial": "brasil", "dimensao_de_oferta": []})
        ),
        json.dumps(plano_dict(dimensions={"recorte": "oferta", "nivel_territorial": "brasil"})),
        json.dumps(plano_dict(dimensions={"recorte": "oferta", "dimensao_de_oferta": []})),
        json.dumps(plano_dict(dimensions=dims("campus", "brasil", "presencial"))),
        json.dumps(plano_dict(dimensions=dims("oferta", "mesorregiao", "presencial"))),
        json.dumps(plano_dict(dimensions=dims("oferta", "brasil", "ead"))),
        json.dumps({k: v for k, v in plano_dict().items() if k != "dimensions"}),
    ],
)
def test_resposta_que_nao_e_plano_e_rejeitada_sem_resgate(texto: str) -> None:
    with pytest.raises(RespostaDoModeloInvalida) as exc:
        interpretar_plano(texto)
    assert exc.value.status == 502
    # A mensagem nao ecoa o que o modelo devolveu.
    assert "DROP" not in exc.value.mensagem and "SELECT" not in exc.value.mensagem


def test_schema_do_plano_nao_tem_texto_livre() -> None:
    """Todo campo de texto do plano e identificador restrito por padrao, ou enum."""
    schema = QueryPlan.model_json_schema()

    def textos(no: Any) -> list[dict[str, Any]]:
        if isinstance(no, dict):
            proprios = [no] if no.get("type") == "string" else []
            return proprios + [t for v in no.values() for t in textos(v)]
        if isinstance(no, list):
            return [t for v in no for t in textos(v)]
        return []

    livres = [t for t in textos(schema) if "pattern" not in t and "enum" not in t]
    assert livres == []
    assert schema["additionalProperties"] is False


# --- rejeicoes contra a camada --------------------------------------------------------------------

CASOS_UF_PRIVADA: list[tuple[str, dict[str, Any], str]] = [
    ("metrica inventada", {"metrics": ["alunos_felizes"]}, "metrica_inexistente"),
    ("composicao", {"metrics": ["participacao_privada"]}, "nao_suportado"),
    ("razao com JOIN", {"metrics": ["matriculas_por_100_mil_habitantes"]}, "nao_suportado"),
    ("razao que exige base", {"metrics": ["financiamento"]}, "nao_suportado"),
    ("entidade errada", {"entity": "ies"}, "entidade_incompativel"),
    ("recorte errado", {"dimensions": dims("sede", "uf", "presencial")}, "recorte_invalido"),
    ("oferta vazia", {"dimensions": dims("oferta", "uf")}, "dimensao_de_oferta_ausente"),
    (
        "oferta sem territorio",
        {"dimensions": dims("oferta", "uf", "ead_nacional")},
        "dimensao_de_oferta_sem_territorio",
    ),
    (
        "oferta repetida",
        {"dimensions": dims("oferta", "uf", "presencial", "presencial")},
        "dimensao_de_oferta_repetida",
    ),
    ("dimensao inexistente", {"filters": [filtro("turno", "noturno")]}, "dimensao_inexistente"),
    ("valor fora do dominio", {"filters": [filtro("rede", "federal")]}, "valor_fora_do_dominio"),
    ("filtro em decomposicao", {"filters": [filtro("sexo", "feminino")]}, "dimensao_nao_filtravel"),
    ("filtro em dimensao virtual", {"filters": [filtro("recorte", "sede")]}, "filtro_invalido"),
    ("oferta como filtro", {"filters": [filtro("dimensao", "presencial")]}, "filtro_invalido"),
    (
        "dois filtros na mesma dimensao",
        {"filters": [filtro("rede", "privada"), filtro("rede", "publica")]},
        "filtro_invalido",
    ),
    ("filtro por rotulo CINE", {"filters": [filtro("rotulo_cine", "x")]}, "nao_suportado"),
    ("municipio mal formado", {"filters": [filtro("municipio", "35503")]}, "municipio_mal_formado"),
    ("municipio por nome", {"filters": [filtro("municipio", "Campinas")]}, "municipio_mal_formado"),
    (
        "filtros contraditorios",
        {"filters": [filtro("rede", "privada"), filtro("categoria", "publica_federal")]},
        "filtros_contraditorios",
    ),
    ("territorio em group_by", {"group_by": ["uf"]}, "agrupamento_invalido"),
    ("decomposicao em group_by", {"group_by": ["sexo"]}, "nao_suportado"),
    ("rotulo CINE em group_by", {"group_by": ["rotulo_cine"]}, "nao_suportado"),
    ("group_by inexistente", {"group_by": ["turno"]}, "dimensao_inexistente"),
    ("group_by repetido", {"group_by": ["rede", "rede"]}, "agrupamento_invalido"),
    (
        "having fora do plano",
        {"having": [{"metrica": "ingressantes", "operador": ">", "valor": 1}]},
        "having_fora_do_plano",
    ),
    ("ordenacao por coluna alheia", {"order_by": [{"por": "grau"}]}, "ordenacao_invalida"),
    ("limite acima do teto", {"limit": TETO_LINHAS + 1}, "limite_acima_do_teto"),
    ("valor unico com agrupamento", {"intent": "valor"}, "intencao_incoerente"),
    ("ranking sem ordenacao", {"intent": "ranking"}, "intencao_incoerente"),
    ("linha numa base de um ano", {"visualization_hint": "line"}, "visualizacao_incompativel"),
    ("kpi com agrupamento", {"visualization_hint": "kpi"}, "visualizacao_incompativel"),
    ("heatmap com um eixo", {"visualization_hint": "heatmap"}, "visualizacao_incompativel"),
]


@pytest.mark.parametrize(
    ("mudanca", "codigo"),
    [(m, c) for _, m, c in CASOS_UF_PRIVADA],
    ids=[n for n, _, _ in CASOS_UF_PRIVADA],
)
def test_plano_invalido_contra_a_camada(mudanca: dict[str, Any], codigo: str) -> None:
    assert codigo in codigos(P_UF_PRIVADA, plano_uf_privada(**mudanca))


def test_dimensao_nao_permitida_para_a_metrica() -> None:
    # Grau academico e atributo de curso: nao existe na tabela de IES.
    dados = plano_dict(
        intent="distribuicao",
        entity="ies",
        metrics=["docentes"],
        dimensions=dims("sede", "regiao"),
        filters=[filtro("grau", "bacharelado")],
    )
    assert "dimensao_nao_permitida" in codigos("docentes por região", dados)
    dados = plano_dict(
        intent="distribuicao",
        entity="ies",
        metrics=["docentes"],
        dimensions=dims("sede", "regiao"),
        group_by=["gratuito"],
    )
    assert "dimensao_nao_permitida" in codigos("docentes por região", dados)


def test_ies_nao_aceita_dimensao_de_oferta() -> None:
    dados = {**PLANO_IES_BRASIL, "dimensions": dims("sede", "brasil", "presencial")}
    assert "dimensao_de_oferta_indevida" in codigos(P_IES_BRASIL, dados)


def test_nivel_nao_admitido_e_nivel_bloqueado() -> None:
    # Contar municipios com sede nao existe no nivel municipal.
    dados = plano_dict(
        intent="distribuicao",
        entity="ies",
        metrics=["municipios_com_sede"],
        dimensions=dims("sede", "municipio"),
    )
    assert "nivel_nao_admitido" in codigos(P_IES_BRASIL, dados)
    # Area CINE tem bloqueio provisorio no nivel municipal (piso de supressao pendente).
    dados = plano_dict(
        intent="distribuicao",
        dimensions=dims("oferta", "municipio", "presencial"),
        group_by=["area"],
    )
    assert "nivel_bloqueado" in codigos("matrículas presenciais por área por município", dados)


def test_razao_de_dimensao_unica_nao_soma_dimensoes() -> None:
    dados = plano_dict(
        metrics=["inscricoes_por_vaga"],
        dimensions=dims("oferta", "brasil", "presencial", "ead_nacional"),
    )
    assert "dimensao_de_oferta_unica" in codigos("inscrições por vaga presenciais", dados)
    dados = plano_dict(
        metrics=["ingressantes_por_vaga"], dimensions=dims("oferta", "brasil", "ead_polo")
    )
    assert "dimensao_de_oferta_nao_admitida" in codigos("ingressantes por vaga", dados)


def test_filtro_territorial_so_vale_do_seu_nivel_para_baixo() -> None:
    dados = plano_dict(filters=[filtro("uf", "SP")])
    obtidos = codigos("matrículas presenciais em SP", dados)
    assert "filtro_territorial_fora_do_nivel" in obtidos
    certo = plano_dict(
        intent="distribuicao",
        dimensions=dims("oferta", "uf", "presencial"),
        filters=[filtro("uf", "SP")],
    )
    v = validar_plano(plano(**certo), recuperar_contexto("matrículas presenciais em SP"))
    assert v.agrupamentos == ("uf",)


def test_limite_respeita_o_teto_configurado() -> None:
    assert "limite_acima_do_teto" in codigos(P_UF_PRIVADA, plano_uf_privada(limit=11), teto=10)
    validar_plano(plano(**plano_uf_privada(limit=10)), recuperar_contexto(P_UF_PRIVADA), 10)
    # Nenhuma configuracao passa do teto rigido.
    assert "limite_acima_do_teto" in codigos(
        P_UF_PRIVADA, plano_uf_privada(limit=TETO_LINHAS + 1), teto=10**6
    )


# --- coerencia com o contexto (defesa contra prompt injection) ------------------------------------

CASOS_DE_CONTEXTO: list[tuple[str, dict[str, Any], str]] = [
    ("metrica que a pergunta nao pediu", {"metrics": ["ingressantes"]}, "metrica_fora_do_contexto"),
    (
        "metrica a mais",
        {"metrics": ["matriculas", "concluintes"]},
        "metrica_fora_do_contexto",
    ),
    (
        "recorte trocado",
        {"dimensions": dims("sede", "uf", "presencial")},
        "recorte_diverge_do_contexto",
    ),
    (
        "nivel trocado",
        {"dimensions": dims("oferta", "municipio", "presencial")},
        "nivel_diverge_do_contexto",
    ),
    (
        "oferta trocada",
        {"dimensions": dims("oferta", "uf", "ead_polo")},
        "dimensao_de_oferta_diverge_do_contexto",
    ),
    (
        "oferta ampliada",
        {"dimensions": dims("oferta", "uf", "presencial", "ead_polo")},
        "dimensao_de_oferta_diverge_do_contexto",
    ),
    ("filtro omitido", {"filters": []}, "filtro_do_contexto_omitido"),
    ("filtro trocado", {"filters": [filtro("rede", "publica")]}, "filtro_diverge_do_contexto"),
    (
        "filtro ampliado",
        {"filters": [filtro("rede", "privada", "publica")]},
        "filtro_diverge_do_contexto",
    ),
    (
        "filtro inventado",
        {"filters": [filtro("rede", "privada"), filtro("uf", "RJ")]},
        "filtro_diverge_do_contexto",
    ),
    ("quebra inventada", {"group_by": ["grau"]}, "agrupamento_fora_do_contexto"),
    (
        "limiar inventado",
        {"having": [{"metrica": "matriculas", "operador": ">", "valor": 1000}]},
        "having_fora_do_contexto",
    ),
]


@pytest.mark.parametrize(
    ("mudanca", "codigo"),
    [(m, c) for _, m, c in CASOS_DE_CONTEXTO],
    ids=[n for n, _, _ in CASOS_DE_CONTEXTO],
)
def test_plano_nao_pode_trocar_a_pergunta(mudanca: dict[str, Any], codigo: str) -> None:
    assert codigo in codigos(P_UF_PRIVADA, plano_uf_privada(**mudanca))


def test_dimensao_de_oferta_nao_e_escolhida_pelo_modelo() -> None:
    """Pergunta que nao declara a dimensao: o plano nao pode escolher uma por conta propria."""
    dados = plano_dict(intent="distribuicao", dimensions=dims("oferta", "uf", "presencial"))
    assert "dimensao_de_oferta_nao_declarada" in codigos("matrículas por UF", dados)
    # Com 'por modalidade', so e aceita a quebra com TODAS as dimensoes admitidas.
    todas = ["presencial", "ead_polo", "ead_nacional", "ead_exterior"]
    certo = plano_dict(
        intent="distribuicao", dimensions=dims("oferta", "brasil", *todas), group_by=["dimensao"]
    )
    validar_plano(plano(**certo), recuperar_contexto("matrículas por modalidade"))
    parcial = plano_dict(
        intent="distribuicao",
        dimensions=dims("oferta", "brasil", "presencial"),
        group_by=["dimensao"],
    )
    assert "dimensao_de_oferta_nao_declarada" in codigos("matrículas por modalidade", parcial)


def test_municipio_so_por_codigo_citado_na_pergunta() -> None:
    pergunta = "matrículas presenciais no município 3550308"
    certo = plano_dict(
        intent="distribuicao",
        dimensions=dims("oferta", "municipio", "presencial"),
        filters=[filtro("municipio", "3550308")],
    )
    validar_plano(plano(**certo), recuperar_contexto(pergunta))
    outro = {**certo, "filters": [filtro("municipio", "3304557")]}
    assert "filtro_fora_do_contexto" in codigos(pergunta, outro)
    sem = {**certo, "filters": []}
    assert "filtro_do_contexto_omitido" in codigos(pergunta, sem)


def test_numero_da_pergunta_nao_pode_ser_descartado() -> None:
    pergunta = "top 5 UF com mais matrículas presenciais"
    base = {
        "intent": "ranking",
        "dimensions": dims("oferta", "uf", "presencial"),
        "order_by": [{"por": "matriculas", "direcao": "desc"}],
    }
    assert "limite_diverge_do_contexto" in codigos(pergunta, plano_dict(**base))
    validar_plano(plano(**base, limit=5), recuperar_contexto(pergunta))


def test_limiar_usa_o_numero_da_pergunta() -> None:
    pergunta = "matrículas presenciais por UF com mais de 500000"
    limiar = {"metrica": "matriculas", "operador": ">", "valor": 500000}
    base = {"intent": "distribuicao", "dimensions": dims("oferta", "uf", "presencial")}
    validar_plano(plano(**base, having=[limiar]), recuperar_contexto(pergunta))
    assert "limiar_do_contexto_omitido" in codigos(pergunta, plano_dict(**base))
    outro = {**limiar, "valor": 5}
    assert "having_fora_do_contexto" in codigos(pergunta, plano_dict(**base, having=[outro]))


def test_contexto_nao_pronto_invalida_qualquer_plano() -> None:
    for pergunta in ("quantas universidades existem?", "qual a evasão por UF?", "matrículas EAD"):
        assert "contexto_nao_pronto" in codigos(pergunta, plano_dict())


# --- escopo da v1 ---------------------------------------------------------------------------------


def test_escopo_da_v1_e_explicito() -> None:
    servidas = {m.id for m in CAMADA.metricas if motivo_fora_da_v1(m) is None}
    assert servidas == {
        "ies",
        "cursos",
        "matriculas",
        "ingressantes",
        "concluintes",
        "vagas",
        "inscricoes",
        "docentes",
        "tecnicos",
        "municipios_com_sede",
        "municipios_com_oferta",
        "ingressantes_por_vaga",
        "inscricoes_por_vaga",
    }
    # Toda metrica servida e de uma tabela so, com expressao vinda da camada.
    for m in CAMADA.metricas:
        if m.id in servidas:
            assert m.tipo in ("direta", "razao") and not m.relacionamentos and m.expressao
