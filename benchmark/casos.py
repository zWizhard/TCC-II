"""Conjunto de teste do benchmark: perguntas, QueryPlan de referencia e SQL de referencia.

Dois blocos, que medem coisas diferentes e nunca sao somados:

- BLOCO M (modelo): a camada semantica classifica a pergunta como `pronta`, entao o LLM e chamado.
  Cada caso traz o QueryPlan esperado e um SQL de referencia ESCRITO A MAO, direto sobre as
  tabelas, sem passar pelo gerador de `api/analista/sql.py`. O resultado esperado e o desse SQL.
- BLOCO S (sistema): JOIN, variacao temporal, ambiguidade e fora de escopo. Nesta arquitetura a
  pergunta e barrada ANTES do LLM, de forma deterministica; o desfecho e o mesmo para qualquer
  modelo. O caso traz a `situacao` ideal — a que a especificacao pede, nao a que o codigo devolve.

O SQL de referencia segue as regras de dados do projeto (CLAUDE.md, INDICADORES.md): ano como
texto, `SUM(qt_curso)` para cursos, `tp_dimensao` sempre declarada e o filtro de 7 digitos de
`co_municipio` em toda agregacao territorial de cursos. As colunas do SQL de referencia levam o
nome das colunas da resposta do Analista com as quais sao comparadas (`uf_codigo`, `rede`, ...).
"""

from dataclasses import dataclass, field
from typing import Any, Literal

IES = "inep_educacao_superior_ies"
CURSOS = "inep_educacao_superior_cursos"
_ANO = "nu_ano_censo = '2024'"
_PRESENCIAL = "tp_dimensao = 'Cursos presenciais ofertados no Brasil'"
_POLO = "tp_dimensao = 'Cursos a distância ofertados no Brasil'"
_TERRITORIO = "regexp_full_match(co_municipio, '[0-9]{7}')"

# Casos cujo plano de referencia depende de uma convencao do validador que o prompt de sistema nao
# enuncia: sao reportados tambem como subgrupo, e a taxa de sucesso sai com e sem eles.
# - F4, M1, M2: filtro por um unico municipio, regiao ou UF. A resposta tem uma linha so, mas o
#   nivel territorial deixa de ser Brasil e a validacao exige `distribuicao`, nao `valor`.
# - G4: a pergunta nao escolhe dimensao de oferta; a validacao exige declarar as quatro.
CONVENCAO_IMPLICITA = frozenset({"F4", "G4", "M1", "M2"})

Bloco = Literal["modelo", "sistema"]
Categoria = Literal[
    "agregacao",
    "filtro_simples",
    "group_by",
    "having",
    "ranking",
    "comparacao",
    "multiplos_filtros",
    "razao",
    "join",
    "evolucao_temporal",
    "ambiguidade",
    "fora_de_escopo",
]


@dataclass(frozen=True)
class Caso:
    id: str
    bloco: Bloco
    categoria: Categoria
    pergunta: str
    # Bloco M:
    plano: dict[str, Any] | None = None
    sql_referencia: str | None = None
    ordenado: bool = False  # a ordem das linhas faz parte da resposta (ranking)
    # Bloco S:
    situacao_ideal: str | None = None
    nota: str = ""
    # O plano de referencia depende de uma convencao do validador que o prompt nao enuncia.
    convencao_implicita: bool = False
    metricas: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.bloco == "modelo":
            assert self.plano is not None and self.sql_referencia is not None, self.id
            object.__setattr__(self, "metricas", tuple(self.plano["metrics"]))
            object.__setattr__(self, "convencao_implicita", self.id in CONVENCAO_IMPLICITA)
        else:
            assert self.situacao_ideal is not None and self.plano is None, self.id


def _dims(recorte: str, nivel: str, *oferta: str) -> dict[str, Any]:
    return {"recorte": recorte, "nivel_territorial": nivel, "dimensao_de_oferta": list(oferta)}


def _f(dimensao: str, *valores: str) -> dict[str, Any]:
    return {"dimensao": dimensao, "valores": list(valores)}


def _plano(
    intent: str, entity: str, metrics: list[str], dims: dict[str, Any], **resto: Any
) -> dict[str, Any]:
    return {"intent": intent, "entity": entity, "metrics": metrics, "dimensions": dims, **resto}


def _m(
    id_: str, categoria: Categoria, pergunta: str, plano: dict[str, Any], sql: str, **kw: Any
) -> Caso:
    return Caso(id_, "modelo", categoria, pergunta, plano=plano, sql_referencia=sql, **kw)


def _s(id_: str, categoria: Categoria, pergunta: str, situacao: str, nota: str = "") -> Caso:
    return Caso(id_, "sistema", categoria, pergunta, situacao_ideal=situacao, nota=nota)


def _ordem(metrica: str) -> list[dict[str, str]]:
    return [{"por": metrica, "direcao": "desc"}]


CASOS: tuple[Caso, ...] = (
    # --- agregacao: um numero, sem filtro ---------------------------------------------------------
    _m(
        "A1",
        "agregacao",
        "Quantas IES existem no Brasil?",
        _plano("valor", "ies", ["ies"], _dims("sede", "brasil")),
        f"SELECT COUNT(*) AS ies FROM {IES} WHERE {_ANO}",
    ),
    _m(
        "A2",
        "agregacao",
        "Quantas matrículas presenciais há no Brasil?",
        _plano("valor", "cursos", ["matriculas"], _dims("oferta", "brasil", "presencial")),
        f"SELECT SUM(qt_mat) AS matriculas FROM {CURSOS} WHERE {_ANO} AND {_PRESENCIAL}",
    ),
    _m(
        "A3",
        "agregacao",
        "Quantos docentes existem no Brasil?",
        _plano("valor", "ies", ["docentes"], _dims("sede", "brasil")),
        f"SELECT SUM(qt_doc_total) AS docentes FROM {IES} WHERE {_ANO}",
    ),
    # --- filtro simples ---------------------------------------------------------------------------
    _m(
        "F1",
        "filtro_simples",
        "Quantas IES existem na rede privada?",
        _plano("valor", "ies", ["ies"], _dims("sede", "brasil"), filters=[_f("rede", "privada")]),
        f"SELECT COUNT(*) AS ies FROM {IES} WHERE {_ANO} AND ds_rede = 'Privada'",
    ),
    _m(
        "F2",
        "filtro_simples",
        "Quantos cursos presenciais de bacharelado existem?",
        _plano(
            "valor",
            "cursos",
            ["cursos"],
            _dims("oferta", "brasil", "presencial"),
            filters=[_f("grau", "bacharelado")],
        ),
        f"SELECT SUM(qt_curso) AS cursos FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND tp_grau_academico = 'Bacharelado'",
    ),
    _m(
        "F3",
        "filtro_simples",
        "Quantas IES comunitárias existem?",
        _plano(
            "valor", "ies", ["ies"], _dims("sede", "brasil"), filters=[_f("comunitaria", "sim")]
        ),
        f"SELECT COUNT(*) AS ies FROM {IES} WHERE {_ANO} AND in_comunitaria = 1",
    ),
    _m(
        "F4",
        "filtro_simples",
        "Quantas IES existem no município 5300108?",
        _plano(
            "distribuicao",
            "ies",
            ["ies"],
            _dims("sede", "municipio"),
            filters=[_f("municipio", "5300108")],
        ),
        f"SELECT co_municipio_ies AS municipio, COUNT(*) AS ies FROM {IES} "
        f"WHERE {_ANO} AND co_municipio_ies = '5300108' GROUP BY 1",
    ),
    # --- GROUP BY ---------------------------------------------------------------------------------
    _m(
        "G1",
        "group_by",
        "matrículas presenciais por UF",
        _plano("distribuicao", "cursos", ["matriculas"], _dims("oferta", "uf", "presencial")),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} GROUP BY 1",
    ),
    _m(
        "G2",
        "group_by",
        "IES por categoria administrativa",
        _plano("distribuicao", "ies", ["ies"], _dims("sede", "brasil"), group_by=["categoria"]),
        f"SELECT tp_categoria_administrativa AS categoria, COUNT(*) AS ies FROM {IES} "
        f"WHERE {_ANO} GROUP BY 1",
    ),
    _m(
        "G3",
        "group_by",
        "matrículas presenciais por rede",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "brasil", "presencial"),
            group_by=["rede"],
        ),
        f"SELECT tp_rede AS rede, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} GROUP BY 1",
    ),
    _m(
        "G4",
        "group_by",
        "matrículas por modalidade",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "brasil", "presencial", "ead_polo", "ead_nacional", "ead_exterior"),
            group_by=["dimensao"],
        ),
        f"SELECT tp_dimensao AS dimensao, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} GROUP BY 1",
        nota="A pergunta nao escolhe dimensao de oferta: so e valido mostrar as quatro, uma por linha.",
    ),
    # --- HAVING -----------------------------------------------------------------------------------
    _m(
        "H1",
        "having",
        "Quais UFs têm mais de 100 IES?",
        _plano(
            "distribuicao",
            "ies",
            ["ies"],
            _dims("sede", "uf"),
            having=[{"metrica": "ies", "operador": ">", "valor": 100}],
        ),
        f"SELECT sg_uf_ies AS uf_codigo, COUNT(*) AS ies FROM {IES} WHERE {_ANO} "
        "GROUP BY 1 HAVING COUNT(*) > 100",
    ),
    _m(
        "H2",
        "having",
        "Quais UFs têm mais de 100.000 matrículas presenciais?",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "uf", "presencial"),
            having=[{"metrica": "matriculas", "operador": ">", "valor": 100000}],
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} GROUP BY 1 HAVING SUM(qt_mat) > 100000",
    ),
    _m(
        "H3",
        "having",
        "Quais regiões têm pelo menos 500 IES?",
        _plano(
            "distribuicao",
            "ies",
            ["ies"],
            _dims("sede", "regiao"),
            having=[{"metrica": "ies", "operador": ">=", "valor": 500}],
        ),
        f"SELECT CAST(co_regiao_ies AS VARCHAR) AS regiao_codigo, COUNT(*) AS ies FROM {IES} "
        f"WHERE {_ANO} GROUP BY 1 HAVING COUNT(*) >= 500",
    ),
    _m(
        "H4",
        "having",
        "Quais UFs têm menos de 20 IES?",
        _plano(
            "distribuicao",
            "ies",
            ["ies"],
            _dims("sede", "uf"),
            having=[{"metrica": "ies", "operador": "<", "valor": 20}],
        ),
        f"SELECT sg_uf_ies AS uf_codigo, COUNT(*) AS ies FROM {IES} WHERE {_ANO} "
        "GROUP BY 1 HAVING COUNT(*) < 20",
    ),
    # --- ranking (a ordem faz parte da resposta) --------------------------------------------------
    _m(
        "R1",
        "ranking",
        "Quais são as 5 UFs com mais matrículas presenciais?",
        _plano(
            "ranking",
            "cursos",
            ["matriculas"],
            _dims("oferta", "uf", "presencial"),
            order_by=_ordem("matriculas"),
            limit=5,
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} GROUP BY 1 "
        "ORDER BY matriculas DESC, uf_codigo LIMIT 5",
        ordenado=True,
    ),
    _m(
        "R2",
        "ranking",
        "top 10 UFs com mais docentes",
        _plano(
            "ranking",
            "ies",
            ["docentes"],
            _dims("sede", "uf"),
            order_by=_ordem("docentes"),
            limit=10,
        ),
        f"SELECT sg_uf_ies AS uf_codigo, SUM(qt_doc_total) AS docentes FROM {IES} WHERE {_ANO} "
        "GROUP BY 1 ORDER BY docentes DESC, uf_codigo LIMIT 10",
        ordenado=True,
    ),
    _m(
        "R3",
        "ranking",
        "Quais os 5 municípios com mais IES?",
        _plano(
            "ranking", "ies", ["ies"], _dims("sede", "municipio"), order_by=_ordem("ies"), limit=5
        ),
        f"SELECT co_municipio_ies AS municipio, COUNT(*) AS ies FROM {IES} WHERE {_ANO} "
        "GROUP BY 1 ORDER BY ies DESC, municipio LIMIT 5",
        ordenado=True,
    ),
    _m(
        "R4",
        "ranking",
        "os 3 graus acadêmicos com mais matrículas presenciais",
        _plano(
            "ranking",
            "cursos",
            ["matriculas"],
            _dims("oferta", "brasil", "presencial"),
            group_by=["grau"],
            order_by=_ordem("matriculas"),
            limit=3,
        ),
        f"SELECT tp_grau_academico AS grau, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} GROUP BY 1 ORDER BY matriculas DESC, grau LIMIT 3",
        ordenado=True,
    ),
    # --- comparacao: duas medidas ou duas unidades lado a lado ------------------------------------
    _m(
        "C1",
        "comparacao",
        "ingressantes e concluintes presenciais por região",
        _plano(
            "distribuicao",
            "cursos",
            ["ingressantes", "concluintes"],
            _dims("oferta", "regiao", "presencial"),
        ),
        f"SELECT CAST(co_regiao AS VARCHAR) AS regiao_codigo, SUM(qt_ing) AS ingressantes, "
        f"SUM(qt_conc) AS concluintes FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} GROUP BY 1",
    ),
    _m(
        "C2",
        "comparacao",
        "matrículas presenciais nas UFs SP e RJ",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "uf", "presencial"),
            filters=[_f("uf", "SP", "RJ")],
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} AND sg_uf IN ('SP', 'RJ') GROUP BY 1",
    ),
    _m(
        "C3",
        "comparacao",
        "vagas e inscrições presenciais por rede",
        _plano(
            "distribuicao",
            "cursos",
            ["vagas", "inscricoes"],
            _dims("oferta", "brasil", "presencial"),
            group_by=["rede"],
        ),
        f"SELECT tp_rede AS rede, SUM(qt_vg_total) AS vagas, SUM(qt_inscrito_total) AS inscricoes "
        f"FROM {CURSOS} WHERE {_ANO} AND {_PRESENCIAL} GROUP BY 1",
    ),
    # --- multiplos filtros ------------------------------------------------------------------------
    _m(
        "M1",
        "multiplos_filtros",
        "matrículas presenciais de licenciatura na rede privada na região Nordeste",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "regiao", "presencial"),
            filters=[_f("grau", "licenciatura"), _f("rede", "privada"), _f("regiao", "nordeste")],
        ),
        f"SELECT CAST(co_regiao AS VARCHAR) AS regiao_codigo, SUM(qt_mat) AS matriculas "
        f"FROM {CURSOS} WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} "
        "AND tp_grau_academico = 'Licenciatura' AND tp_rede = 'Privada' "
        "AND no_regiao = 'Nordeste' GROUP BY 1",
    ),
    _m(
        "M2",
        "multiplos_filtros",
        "Quantos cursos presenciais de licenciatura há na rede privada em MG?",
        _plano(
            "distribuicao",
            "cursos",
            ["cursos"],
            _dims("oferta", "uf", "presencial"),
            filters=[_f("grau", "licenciatura"), _f("rede", "privada"), _f("uf", "MG")],
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_curso) AS cursos FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} "
        "AND tp_grau_academico = 'Licenciatura' AND tp_rede = 'Privada' AND sg_uf = 'MG' GROUP BY 1",
    ),
    _m(
        "M3",
        "multiplos_filtros",
        "Quais UFs têm mais de 200.000 matrículas em polo EAD na rede privada?",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "uf", "ead_polo"),
            filters=[_f("rede", "privada")],
            having=[{"metrica": "matriculas", "operador": ">", "valor": 200000}],
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_POLO} AND {_TERRITORIO} AND tp_rede = 'Privada' "
        "GROUP BY 1 HAVING SUM(qt_mat) > 200000",
    ),
    _m(
        "M4",
        "multiplos_filtros",
        "matrículas presenciais por UF na rede privada",
        _plano(
            "distribuicao",
            "cursos",
            ["matriculas"],
            _dims("oferta", "uf", "presencial"),
            filters=[_f("rede", "privada")],
        ),
        f"SELECT sg_uf AS uf_codigo, SUM(qt_mat) AS matriculas FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} AND tp_rede = 'Privada' GROUP BY 1",
    ),
    # --- razao: metrica derivada do catalogo ------------------------------------------------------
    _m(
        "Z1",
        "razao",
        "ingressantes por vaga nos cursos presenciais por rede",
        _plano(
            "distribuicao",
            "cursos",
            ["ingressantes_por_vaga"],
            _dims("oferta", "brasil", "presencial"),
            group_by=["rede"],
        ),
        f"SELECT tp_rede AS rede, CAST(SUM(qt_ing) AS DOUBLE) / NULLIF(SUM(qt_vg_total), 0) "
        f"AS ingressantes_por_vaga FROM {CURSOS} WHERE {_ANO} AND {_PRESENCIAL} GROUP BY 1",
    ),
    _m(
        "Z2",
        "razao",
        "inscrições por vaga nos cursos presenciais por UF",
        _plano(
            "distribuicao",
            "cursos",
            ["inscricoes_por_vaga"],
            _dims("oferta", "uf", "presencial"),
        ),
        f"SELECT sg_uf AS uf_codigo, CAST(SUM(qt_inscrito_total) AS DOUBLE) / "
        f"NULLIF(SUM(qt_vg_total), 0) AS inscricoes_por_vaga FROM {CURSOS} "
        f"WHERE {_ANO} AND {_PRESENCIAL} AND {_TERRITORIO} GROUP BY 1",
    ),
    # === BLOCO S: decidido pela camada semantica, sem LLM =========================================
    _s(
        "J1",
        "join",
        "matrículas por 100 mil habitantes por UF",
        "nao_suportada",
        "IND-R-01 exige JOIN cursos x municipio x populacao; fora da v1 do Analista.",
    ),
    _s(
        "J2",
        "join",
        "Quantas matrículas presenciais e quantos docentes há por UF?",
        "nao_suportada",
        "Medidas de duas tabelas (cursos e IES) na mesma pergunta: exigiria JOIN.",
    ),
    _s(
        "J3",
        "join",
        "docentes por matrícula por UF",
        "recusada",
        "Razao entre medidas de tabelas e recortes diferentes: em quarentena (INDICADORES.md).",
    ),
    _s(
        "T1",
        "evolucao_temporal",
        "crescimento das matrículas presenciais entre 2020 e 2024",
        "recusada",
        "So existe 2024.",
    ),
    _s("T2", "evolucao_temporal", "matrículas presenciais em 2019", "recusada", "So existe 2024."),
    _s(
        "T3",
        "evolucao_temporal",
        "Como evoluíram as matrículas presenciais?",
        "recusada",
        "So existe 2024; flexao verbal de 'evolucao'.",
    ),
    _s(
        "B1",
        "ambiguidade",
        "Quantas universidades existem no Brasil?",
        "requer_esclarecimento",
        "IES em sentido informal (2.561) x organizacao academica Universidade (206).",
    ),
    _s(
        "B2",
        "ambiguidade",
        "Quantas IES públicas existem?",
        "requer_esclarecimento",
        "Rede publica da base (317, com as 28 Especial) x publica em sentido estrito (289).",
    ),
    _s(
        "B3",
        "ambiguidade",
        "Quantas matrículas EAD existem?",
        "requer_esclarecimento",
        "EAD esta em tres dimensoes de oferta.",
    ),
    _s(
        "B4",
        "ambiguidade",
        "matrículas presenciais em São Paulo",
        "requer_esclarecimento",
        "Estado ou municipio de mesmo nome.",
    ),
    _s(
        "B5",
        "ambiguidade",
        "Quantas matrículas existem no Brasil?",
        "requer_esclarecimento",
        "Dimensao de oferta nao declarada; nao ha padrao.",
    ),
    _s(
        "X1",
        "fora_de_escopo",
        "taxa de evasão dos cursos presenciais",
        "recusada",
        "Evasao nao e calculavel com um ano de dados agregados (quarentena).",
    ),
)

# Pergunta de aquecimento: carrega o modelo na memoria antes da medicao. Nao e um caso do conjunto.
PERGUNTA_DE_AQUECIMENTO = "Quantos técnicos administrativos existem no Brasil?"


def casos(bloco: Bloco) -> tuple[Caso, ...]:
    return tuple(c for c in CASOS if c.bloco == bloco)
