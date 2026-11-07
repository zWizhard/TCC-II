"""Catalogo fechado dos indicadores servidos pela API.

Cada entrada corresponde a uma ficha do Bloco A de `docs/tcc/methodology/INDICADORES.md`.
E este catalogo — e nao o frontend — que decide tabela, expressao, recorte e dimensoes validas:
nenhum parametro de requisicao chega ao SQL como texto, so como valor vinculado.

Valores literais (tp_dimensao, rede, UFs) e restricoes territoriais medidos no DuckDB local em
2026-09-26 (relatorio do data-engineer, Fase 5).
"""

from dataclasses import dataclass
from enum import StrEnum


class Recorte(StrEnum):
    SEDE = "sede"  # municipio de sede da IES (698 unidades)
    OFERTA = "oferta"  # municipio de oferta, incl. polos EAD (3.551 unidades)


class Nivel(StrEnum):
    BRASIL = "brasil"
    REGIAO = "regiao"
    UF = "uf"
    MUNICIPIO = "municipio"


class Dimensao(StrEnum):
    PRESENCIAL = "presencial"
    EAD_POLO = "ead_polo"
    EAD_NACIONAL = "ead_nacional"
    EAD_EXTERIOR = "ead_exterior"


# Valores literais de cursos.tp_dimensao.
ROTULO_DIMENSAO: dict[Dimensao, str] = {
    Dimensao.PRESENCIAL: "Cursos presenciais ofertados no Brasil",
    Dimensao.EAD_POLO: "Cursos a distância ofertados no Brasil",
    Dimensao.EAD_NACIONAL: "Cursos a distância com dimensão de dados somente a nível Brasil",
    Dimensao.EAD_EXTERIOR: "Cursos a distância ofertados por instituições brasileiras no exterior",
}
# As duas ultimas nao tem municipio, UF nem regiao em nenhuma linha.
DIMENSOES_COM_TERRITORIO = frozenset({Dimensao.PRESENCIAL, Dimensao.EAD_POLO})


class Rede(StrEnum):
    PUBLICA = "publica"
    PRIVADA = "privada"


# Mesmos rotulos em ies.ds_rede e cursos.tp_rede (ADR-0007). 'Pública' inclui as 28 IES Especial.
ROTULO_REDE: dict[Rede, str] = {Rede.PUBLICA: "Pública", Rede.PRIVADA: "Privada"}


class UF(StrEnum):
    """As 27 siglas presentes no Censo 2024 (identicas em ies e cursos; conferido em teste)."""

    AC = "AC"
    AL = "AL"
    AM = "AM"
    AP = "AP"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MG = "MG"
    MS = "MS"
    MT = "MT"
    PA = "PA"
    PB = "PB"
    PE = "PE"
    PI = "PI"
    PR = "PR"
    RJ = "RJ"
    RN = "RN"
    RO = "RO"
    RR = "RR"
    RS = "RS"
    SC = "SC"
    SE = "SE"
    SP = "SP"
    TO = "TO"


class Regiao(StrEnum):
    NORTE = "norte"
    NORDESTE = "nordeste"
    SUDESTE = "sudeste"
    SUL = "sul"
    CENTRO_OESTE = "centro_oeste"


# (co_regiao, no_regiao) — identicos em ies e cursos; conferido em teste.
CODIGO_REGIAO: dict[Regiao, str] = {
    Regiao.NORTE: "1",
    Regiao.NORDESTE: "2",
    Regiao.SUDESTE: "3",
    Regiao.SUL: "4",
    Regiao.CENTRO_OESTE: "5",
}
ROTULO_REGIAO: dict[Regiao, str] = {
    Regiao.NORTE: "Norte",
    Regiao.NORDESTE: "Nordeste",
    Regiao.SUDESTE: "Sudeste",
    Regiao.SUL: "Sul",
    Regiao.CENTRO_OESTE: "Centro-Oeste",
}

# UF -> (nome, regiao), como aparecem em no_uf/no_uf_ies e co_regiao; conferido em teste.
UF_INFO: dict[UF, tuple[str, Regiao]] = {
    UF.AC: ("Acre", Regiao.NORTE),
    UF.AM: ("Amazonas", Regiao.NORTE),
    UF.AP: ("Amapá", Regiao.NORTE),
    UF.PA: ("Pará", Regiao.NORTE),
    UF.RO: ("Rondônia", Regiao.NORTE),
    UF.RR: ("Roraima", Regiao.NORTE),
    UF.TO: ("Tocantins", Regiao.NORTE),
    UF.AL: ("Alagoas", Regiao.NORDESTE),
    UF.BA: ("Bahia", Regiao.NORDESTE),
    UF.CE: ("Ceará", Regiao.NORDESTE),
    UF.MA: ("Maranhão", Regiao.NORDESTE),
    UF.PB: ("Paraíba", Regiao.NORDESTE),
    UF.PE: ("Pernambuco", Regiao.NORDESTE),
    UF.PI: ("Piauí", Regiao.NORDESTE),
    UF.RN: ("Rio Grande do Norte", Regiao.NORDESTE),
    UF.SE: ("Sergipe", Regiao.NORDESTE),
    UF.ES: ("Espírito Santo", Regiao.SUDESTE),
    UF.MG: ("Minas Gerais", Regiao.SUDESTE),
    UF.RJ: ("Rio de Janeiro", Regiao.SUDESTE),
    UF.SP: ("São Paulo", Regiao.SUDESTE),
    UF.PR: ("Paraná", Regiao.SUL),
    UF.RS: ("Rio Grande do Sul", Regiao.SUL),
    UF.SC: ("Santa Catarina", Regiao.SUL),
    UF.DF: ("Distrito Federal", Regiao.CENTRO_OESTE),
    UF.GO: ("Goiás", Regiao.CENTRO_OESTE),
    UF.MS: ("Mato Grosso do Sul", Regiao.CENTRO_OESTE),
    UF.MT: ("Mato Grosso", Regiao.CENTRO_OESTE),
}


# Codigo IBGE de 2 digitos de cada UF: e o `cd_uf` de `municipio`, o `co_uf`/`co_uf_ies` do
# Censo e o `codarea` da malha de UFs. Pares conferidos contra a base em teste.
CODIGO_UF: dict[UF, str] = {
    UF.RO: "11", UF.AC: "12", UF.AM: "13", UF.RR: "14", UF.PA: "15", UF.AP: "16", UF.TO: "17",
    UF.MA: "21", UF.PI: "22", UF.CE: "23", UF.RN: "24", UF.PB: "25", UF.PE: "26", UF.AL: "27",
    UF.SE: "28", UF.BA: "29", UF.MG: "31", UF.ES: "32", UF.RJ: "33", UF.SP: "35", UF.PR: "41",
    UF.SC: "42", UF.RS: "43", UF.MS: "50", UF.MT: "51", UF.GO: "52", UF.DF: "53",
}  # fmt: skip
UF_DO_CODIGO: dict[str, UF] = {c: u for u, c in CODIGO_UF.items()}


class Categoria(StrEnum):
    PUBLICA_FEDERAL = "publica_federal"
    PUBLICA_ESTADUAL = "publica_estadual"
    PUBLICA_MUNICIPAL = "publica_municipal"
    PRIVADA_COM_FINS = "privada_com_fins_lucrativos"
    PRIVADA_SEM_FINS = "privada_sem_fins_lucrativos"
    ESPECIAL = "especial"


# Valores literais de tp_categoria_administrativa, identicos em ies e cursos e constantes por
# IES (medido em 2026-10-06). Cada categoria pertence a uma unica rede.
ROTULO_CATEGORIA: dict[Categoria, str] = {
    Categoria.PUBLICA_FEDERAL: "Pública Federal",
    Categoria.PUBLICA_ESTADUAL: "Pública Estadual",
    Categoria.PUBLICA_MUNICIPAL: "Pública Municipal",
    Categoria.PRIVADA_COM_FINS: "Privada com fins lucrativos",
    Categoria.PRIVADA_SEM_FINS: "Privada sem fins lucrativos",
    Categoria.ESPECIAL: "Especial",
}
REDE_DA_CATEGORIA: dict[Categoria, Rede] = {
    Categoria.PUBLICA_FEDERAL: Rede.PUBLICA,
    Categoria.PUBLICA_ESTADUAL: Rede.PUBLICA,
    Categoria.PUBLICA_MUNICIPAL: Rede.PUBLICA,
    Categoria.PRIVADA_COM_FINS: Rede.PRIVADA,
    Categoria.PRIVADA_SEM_FINS: Rede.PRIVADA,
    Categoria.ESPECIAL: Rede.PUBLICA,
}


class Organizacao(StrEnum):
    UNIVERSIDADE = "universidade"
    CENTRO_UNIVERSITARIO = "centro_universitario"
    FACULDADE = "faculdade"
    INSTITUTO_FEDERAL = "instituto_federal"
    CEFET = "cefet"


# Valores literais de tp_organizacao_academica, identicos em ies e cursos e constantes por IES.
ROTULO_ORGANIZACAO: dict[Organizacao, str] = {
    Organizacao.UNIVERSIDADE: "Universidade",
    Organizacao.CENTRO_UNIVERSITARIO: "Centro Universitário",
    Organizacao.FACULDADE: "Faculdade",
    Organizacao.INSTITUTO_FEDERAL: "Instituto Federal de Educação, Ciência e Tecnologia",
    Organizacao.CEFET: "Centro Federal de Educação Tecnológica",
}

# tp_modalidade_ensino e funcao de tp_dimensao (medido em 2026-10-06): so a dimensao
# presencial e 'Presencial'; as tres de EAD sao 'Curso a distância'.
MODALIDADE_DA_DIMENSAO: dict[Dimensao, str] = {
    Dimensao.PRESENCIAL: "Presencial",
    Dimensao.EAD_POLO: "Curso a distância",
    Dimensao.EAD_NACIONAL: "Curso a distância",
    Dimensao.EAD_EXTERIOR: "Curso a distância",
}


class AreaCine(StrEnum):
    PROGRAMAS_BASICOS = "programas_basicos"
    EDUCACAO = "educacao"
    ARTES_HUMANIDADES = "artes_humanidades"
    CIENCIAS_SOCIAIS = "ciencias_sociais"
    NEGOCIOS_DIREITO = "negocios_direito"
    CIENCIAS_NATURAIS = "ciencias_naturais"
    COMPUTACAO_TIC = "computacao_tic"
    ENGENHARIA = "engenharia"
    AGRICULTURA_VETERINARIA = "agricultura_veterinaria"
    SAUDE = "saude"
    SERVICOS = "servicos"


# (co_cine_area_geral, no_cine_area_geral) — pares 1:1, 11 de 11 (medido em 2026-10-06).
# 'Programas básicos' (codigo 0) reune exatamente os 374 cursos com qt_curso = 0: sao as
# Areas Basicas de Ingresso (ABI), com 61.053 matriculas e nenhum concluinte.
AREA_CINE: dict[AreaCine, tuple[int, str]] = {
    AreaCine.PROGRAMAS_BASICOS: (0, "Programas básicos"),
    AreaCine.EDUCACAO: (1, "Educação"),
    AreaCine.ARTES_HUMANIDADES: (2, "Artes e humanidades"),
    AreaCine.CIENCIAS_SOCIAIS: (3, "Ciências sociais, comunicação e informação"),
    AreaCine.NEGOCIOS_DIREITO: (4, "Negócios, administração e direito"),
    AreaCine.CIENCIAS_NATURAIS: (5, "Ciências naturais, matemática e estatística"),
    AreaCine.COMPUTACAO_TIC: (6, "Computação e Tecnologias da Informação e Comunicação (TIC)"),
    AreaCine.ENGENHARIA: (7, "Engenharia, produção e construção"),
    AreaCine.AGRICULTURA_VETERINARIA: (8, "Agricultura, silvicultura, pesca e veterinária"),
    AreaCine.SAUDE: (9, "Saúde e bem-estar"),
    AreaCine.SERVICOS: (10, "Serviços"),
}


class Grau(StrEnum):
    BACHARELADO = "bacharelado"
    LICENCIATURA = "licenciatura"
    TECNOLOGICO = "tecnologico"
    NAO_APLICAVEL = "nao_aplicavel"


# Valores literais de cursos.tp_grau_academico; constante por curso (0 cursos com mais de um).
ROTULO_GRAU: dict[Grau, str] = {
    Grau.BACHARELADO: "Bacharelado",
    Grau.LICENCIATURA: "Licenciatura",
    Grau.TECNOLOGICO: "Tecnológico",
    Grau.NAO_APLICAVEL: "Não aplicável",
}


class Eixo(StrEnum):
    """Dimensao categorica pela qual um indicador direto pode ser decomposto."""

    REDE = "rede"
    CATEGORIA = "categoria"
    ORGANIZACAO = "organizacao"
    DIMENSAO = "dimensao"
    GRAU = "grau"
    AREA = "area"
    ROTULO_CINE = "rotulo_cine"
    TITULACAO = "titulacao"
    # Perfil (IND-R-07) e tipo de vaga do ingresso: decomposicao por colunas, nao por GROUP BY.
    SEXO = "sexo"
    COR_RACA = "cor_raca"
    FAIXA_ETARIA = "faixa_etaria"
    NACIONALIDADE = "nacionalidade"
    PROCEDENCIA_ESCOLAR = "procedencia_escolar"
    TIPO_INGRESSO = "tipo_ingresso"


@dataclass(frozen=True)
class EixoInfo:
    nome: str
    tabelas: frozenset[str]  # tabelas em que o eixo existe
    ficha: str | None  # ficha do Bloco B que a composicao realiza, quando ha
    notas: tuple[str, ...] = ()
    # Restrito a estes indicadores; vazio = qualquer indicador das tabelas acima.
    so_indicadores: frozenset[str] = frozenset()


_AMBAS = frozenset({"ies", "cursos"})
_SO_CURSOS = frozenset({"cursos"})
# Indicadores que tem as colunas de perfil (qt_mat_*, qt_ing_*, qt_conc_*).
_COM_PERFIL = frozenset({"matriculas", "ingressantes", "concluintes"})
_NOTA_NAO_DECLARADO = (
    "'Não declarada/informada' é ausência de informação, não uma categoria residual: permanece "
    "no denominador e não pode ser somada a outra categoria."
)

EIXOS: dict[Eixo, EixoInfo] = {
    Eixo.REDE: EixoInfo("Rede", _AMBAS, "IND-R-03"),
    Eixo.CATEGORIA: EixoInfo("Categoria administrativa", _AMBAS, None),
    Eixo.ORGANIZACAO: EixoInfo("Organização acadêmica", _AMBAS, None),
    Eixo.DIMENSAO: EixoInfo(
        "Dimensão de oferta",
        _SO_CURSOS,
        "IND-R-04",
        (
            "A modalidade é medida por tp_dimensao: vaga e matrícula de EAD não coexistem na "
            "mesma dimensão, e a participação da EAD muda conforme as dimensões incluídas.",
        ),
    ),
    Eixo.GRAU: EixoInfo(
        "Grau acadêmico",
        _SO_CURSOS,
        "IND-R-05",
        ("'Não aplicável' é uma categoria real da base e permanece no denominador.",),
    ),
    Eixo.AREA: EixoInfo(
        "Área geral (CINE)",
        _SO_CURSOS,
        "IND-R-06",
        (
            "'Programas básicos' reúne as Áreas Básicas de Ingresso (ABI): têm matrículas, mas "
            "não entram na contagem de cursos (marcador qt_curso = 0).",
        ),
    ),
    Eixo.ROTULO_CINE: EixoInfo(
        "Rótulo CINE",
        _SO_CURSOS,
        "IND-R-06",
        (
            "O rótulo CINE é a classificação do INEP, não o nome do curso dado pela IES; "
            "são 353 rótulos, e a lista pode estar truncada pelo limite.",
        ),
    ),
    Eixo.TITULACAO: EixoInfo(
        "Maior titulação",
        frozenset({"ies"}),
        "IND-R-12",
        (
            "Titulação descreve o corpo docente; não é medida de qualidade de ensino.",
            "Docentes são atribuídos à sede da IES, não ao local de atuação.",
        ),
        frozenset({"docentes"}),
    ),
    Eixo.SEXO: EixoInfo(
        "Sexo",
        _SO_CURSOS,
        "IND-R-07",
        ("Sexo é registrado como binário na base; a plataforma descreve o dado.",),
        _COM_PERFIL,
    ),
    Eixo.COR_RACA: EixoInfo(
        "Cor ou raça", _SO_CURSOS, "IND-R-07", (_NOTA_NAO_DECLARADO,), _COM_PERFIL
    ),
    Eixo.FAIXA_ETARIA: EixoInfo("Faixa etária", _SO_CURSOS, "IND-R-07", (), _COM_PERFIL),
    Eixo.NACIONALIDADE: EixoInfo("Nacionalidade", _SO_CURSOS, "IND-R-07", (), _COM_PERFIL),
    Eixo.PROCEDENCIA_ESCOLAR: EixoInfo(
        "Procedência escolar (ensino médio)",
        _SO_CURSOS,
        "IND-R-07",
        (_NOTA_NAO_DECLARADO,),
        _COM_PERFIL,
    ),
    Eixo.TIPO_INGRESSO: EixoInfo(
        "Tipo de vaga do ingresso",
        _SO_CURSOS,
        None,
        (
            "Reparte os ingressos pelo tipo de vaga ocupada, não pelo tipo de processo seletivo "
            "(vestibular, Enem…): essas outras colunas não fecham com o total e não são publicadas.",
            "A semântica oficial de cada tipo de vaga depende do dicionário do INEP (a confirmar).",
        ),
        frozenset({"ingressantes"}),
    ),
}

# Colunas de ies que particionam qt_doc_total exatamente (0 divergencias em 2.561 linhas),
# na ordem natural da titulacao.
TITULACOES: tuple[tuple[str, str, str], ...] = (
    ("sem_graduacao", "Sem graduação", "qt_doc_ex_sem_grad"),
    ("graduacao", "Graduação", "qt_doc_ex_grad"),
    ("especializacao", "Especialização", "qt_doc_ex_esp"),
    ("mestrado", "Mestrado", "qt_doc_ex_mest"),
    ("doutorado", "Doutorado", "qt_doc_ex_dout"),
)

# Prefixo das colunas de cada base de fluxo (slug do indicador direto -> familia de colunas).
PREFIXO_BASE: dict[str, str] = {
    "matriculas": "qt_mat",
    "ingressantes": "qt_ing",
    "concluintes": "qt_conc",
}

# (slug, nome, sufixo da coluna) por eixo de perfil. Cada eixo e particao exata de qt_mat, qt_ing
# e qt_conc, linha a linha: 0 divergencias em 720.349 linhas, nas tres bases (medido em
# 2026-10-07, scripts/analise/auditar_fluxo.py). 'Não declarada/informada' e categoria da base.
PERFIS: dict[Eixo, tuple[tuple[str, str, str], ...]] = {
    Eixo.SEXO: (("feminino", "Feminino", "fem"), ("masculino", "Masculino", "masc")),
    Eixo.COR_RACA: (
        ("branca", "Branca", "branca"),
        ("preta", "Preta", "preta"),
        ("parda", "Parda", "parda"),
        ("amarela", "Amarela", "amarela"),
        ("indigena", "Indígena", "indigena"),
        ("nao_declarada", "Não declarada", "cornd"),
    ),
    Eixo.FAIXA_ETARIA: (
        ("0_17", "Até 17 anos", "0_17"),
        ("18_24", "18 a 24 anos", "18_24"),
        ("25_29", "25 a 29 anos", "25_29"),
        ("30_34", "30 a 34 anos", "30_34"),
        ("35_39", "35 a 39 anos", "35_39"),
        ("40_49", "40 a 49 anos", "40_49"),
        ("50_59", "50 a 59 anos", "50_59"),
        ("60_mais", "60 anos ou mais", "60_mais"),
    ),
    Eixo.NACIONALIDADE: (
        ("brasileira", "Brasileira", "nacbras"),
        ("estrangeira", "Estrangeira", "nacestrang"),
    ),
    Eixo.PROCEDENCIA_ESCOLAR: (
        ("escola_publica", "Escola pública", "procescpublica"),
        ("escola_privada", "Escola privada", "procescprivada"),
        ("nao_informada", "Não informada", "procnaoinformada"),
    ),
}

# Particao exata de qt_ing (0 divergencias em 720.349 linhas, 2026-10-07). qt_ing_proc_seletivo
# existe e e zero em todas as linhas; os seis 'tipos de selecao' (vestibular, enem...) NAO fecham
# (40.050 linhas acima, 130.209 abaixo) e ficam fora.
TIPOS_INGRESSO: tuple[tuple[str, str, str], ...] = (
    ("vaga_nova", "Ingresso em vaga nova", "qt_ing_vg_nova"),
    ("vaga_remanescente", "Ingresso em vaga remanescente", "qt_ing_vg_remanesc"),
    ("programa_especial", "Ingresso em vaga de programa especial", "qt_ing_vg_prog_especial"),
    ("outra_forma", "Outras formas de ingresso", "qt_ing_outra_forma"),
)


def colunas_do_eixo(eixo: Eixo, slug: str) -> tuple[tuple[str, str, str], ...] | None:
    """(slug, nome, coluna) dos eixos decompostos por colunas; None para os de GROUP BY."""
    if eixo == Eixo.TITULACAO:
        return TITULACOES
    if eixo == Eixo.TIPO_INGRESSO:
        return TIPOS_INGRESSO
    if eixo in PERFIS:
        prefixo = PREFIXO_BASE[slug]
        return tuple((s, nome, f"{prefixo}_{sufixo}") for s, nome, sufixo in PERFIS[eixo])
    return None


class BaseFluxo(StrEnum):
    """Base sobre a qual IND-R-08 e IND-R-09 sao medidos."""

    MATRICULAS = "matriculas"
    INGRESSANTES = "ingressantes"
    CONCLUINTES = "concluintes"


class Agrupamento(StrEnum):
    """Por onde uma razao pode ser comparada: territorio (um nivel) ou eixo categorico."""

    REGIAO = "regiao"
    UF = "uf"
    MUNICIPIO = "municipio"
    REDE = "rede"
    CATEGORIA = "categoria"
    ORGANIZACAO = "organizacao"
    DIMENSAO = "dimensao"
    GRAU = "grau"
    AREA = "area"


AGRUPAMENTOS_TERRITORIAIS = frozenset({Agrupamento.REGIAO, Agrupamento.UF, Agrupamento.MUNICIPIO})


class OrdemInstituicoes(StrEnum):
    MATRICULAS = "matriculas"
    CURSOS = "cursos"
    INGRESSANTES = "ingressantes"
    CONCLUINTES = "concluintes"
    DOCENTES = "docentes"
    TECNICOS = "tecnicos"
    NOME = "nome"


@dataclass(frozen=True)
class Indicador:
    slug: str
    codigo: str
    nome: str
    unidade: str
    tabela: str  # "ies" | "cursos"
    expressao: str  # fragmento SQL fixo
    # Dimensoes admitidas nos niveis territoriais. Vazio = tabela sem tp_dimensao (IES).
    dimensoes_territoriais: frozenset[Dimensao]
    limitacoes: tuple[str, ...]

    @property
    def recorte(self) -> Recorte:
        return Recorte.SEDE if self.tabela == "ies" else Recorte.OFERTA

    @property
    def exige_dimensao(self) -> bool:
        return self.tabela == "cursos"


_SO_PRESENCIAL = frozenset({Dimensao.PRESENCIAL})

_LIM_SEDE = "Atribuído ao município de sede da IES, não aos campi nem aos polos."
_LIM_VINCULO = "Conta vínculos, não pessoas distintas."

CATALOGO: dict[str, Indicador] = {
    i.slug: i
    for i in (
        Indicador(
            slug="ies",
            codigo="IND-D-01",
            nome="Instituições de ensino superior instaladas",
            unidade="instituições",
            tabela="ies",
            expressao="COUNT(*)",
            dimensoes_territoriais=frozenset(),
            limitacoes=(
                _LIM_SEDE,
                "Não é contagem de campi nem de polos: uma IES com várias unidades conta 1.",
            ),
        ),
        Indicador(
            slug="cursos",
            codigo="IND-D-02",
            nome="Cursos contabilizados na oferta",
            unidade="cursos",
            tabela="cursos",
            expressao="SUM(qt_curso)",
            dimensoes_territoriais=_SO_PRESENCIAL,
            limitacoes=(
                "SUM(qt_curso) = 45.776 difere de COUNT(DISTINCT co_curso) = 46.150; o rótulo não promete 'todos os cursos'.",
                "O marcador é zero em todo polo EAD: por território, só existe no presencial.",
            ),
        ),
        Indicador(
            slug="matriculas",
            codigo="IND-D-03",
            nome="Matrículas",
            unidade="matrículas",
            tabela="cursos",
            expressao="SUM(qt_mat)",
            dimensoes_territoriais=DIMENSOES_COM_TERRITORIO,
            limitacoes=(_LIM_VINCULO, "Contadas no local de oferta; em EAD, no polo."),
        ),
        Indicador(
            slug="ingressantes",
            codigo="IND-D-04",
            nome="Ingressantes",
            unidade="ingressos",
            tabela="cursos",
            expressao="SUM(qt_ing)",
            dimensoes_territoriais=DIMENSOES_COM_TERRITORIO,
            limitacoes=(_LIM_VINCULO,),
        ),
        Indicador(
            slug="concluintes",
            codigo="IND-D-05",
            nome="Concluintes",
            unidade="concluintes",
            tabela="cursos",
            expressao="SUM(qt_conc)",
            dimensoes_territoriais=DIMENSOES_COM_TERRITORIO,
            limitacoes=(
                _LIM_VINCULO,
                "Não pode ser dividido por ingressantes ou matrículas como taxa de conclusão (IND-Q-01).",
            ),
        ),
        Indicador(
            slug="vagas",
            codigo="IND-D-06",
            nome="Vagas ofertadas",
            unidade="vagas",
            tabela="cursos",
            expressao="SUM(qt_vg_total)",
            dimensoes_territoriais=_SO_PRESENCIAL,
            limitacoes=(
                "Vaga só existe territorializada no presencial; 78,5% das vagas estão na dimensão EAD sem território.",
            ),
        ),
        Indicador(
            slug="inscricoes",
            codigo="IND-D-07",
            nome="Inscrições em processo seletivo",
            unidade="inscrições",
            tabela="cursos",
            expressao="SUM(qt_inscrito_total)",
            dimensoes_territoriais=_SO_PRESENCIAL,
            limitacoes=(
                "Inscrições não são candidatos: uma pessoa pode inscrever-se em vários cursos.",
                "Territorializável só no presencial.",
            ),
        ),
        Indicador(
            slug="docentes",
            codigo="IND-D-08",
            nome="Docentes em exercício",
            unidade="docentes",
            tabela="ies",
            expressao="SUM(qt_doc_total)",
            dimensoes_territoriais=frozenset(),
            limitacoes=(_LIM_SEDE, "Agregado na tabela de IES; nunca após JOIN com cursos."),
        ),
        Indicador(
            slug="tecnicos",
            codigo="IND-D-09",
            nome="Técnicos administrativos",
            unidade="funcionários",
            tabela="ies",
            expressao="SUM(qt_tec_total)",
            dimensoes_territoriais=frozenset(),
            limitacoes=(_LIM_SEDE,),
        ),
    )
}

# --- Mapa (Fase 10) -------------------------------------------------------------------------------


class NivelMalha(StrEnum):
    """Niveis para os quais ha geometria (data/reference/malha) e, portanto, coropletico."""

    UF = "uf"
    MUNICIPIO = "municipio"


# IND-R-01. O numerador e IND-D-03 (matriculas, local de oferta); o denominador vem de
# `ibge_populacao_estimada`, por isso nao cabe em `RAZOES` (duas somas das mesmas linhas de cursos).
MATRICULAS_POR_HABITANTE = Indicador(
    slug="matriculas_por_100_mil_habitantes",
    codigo="IND-R-01",
    nome="Matrículas por 100 mil habitantes",
    unidade="matrículas por 100 mil habitantes",
    tabela="cursos",
    expressao="SUM(qt_mat)",
    dimensoes_territoriais=DIMENSOES_COM_TERRITORIO,
    limitacoes=(
        "A matrícula é contada no local de oferta e o habitante no local de residência: um "
        "município que atende a região inteira, ou um polo EAD, eleva a razão sem que a "
        "população local estude mais.",
        "Não é taxa de escolarização: o denominador é a população total estimada pelo IBGE "
        "para 2024, não a população em idade de cursar o ensino superior.",
        "Unidade territorial sem registro de oferta é ausência de dado, não zero.",
        "Em município pequeno, poucas matrículas deslocam muito a razão.",
        _LIM_VINCULO,
    ),
)

# --- Comparacoes (Fase 11) ------------------------------------------------------------------------


class NivelComparacao(StrEnum):
    """Niveis em que unidades territoriais podem ser postas lado a lado (o Brasil e a referencia)."""

    REGIAO = "regiao"
    UF = "uf"
    MUNICIPIO = "municipio"


class TipoComparacao(StrEnum):
    ABSOLUTO = "absoluto"  # contagem ou soma: mede sobretudo o porte da unidade
    RELATIVO = "relativo"  # razao ou proporcao: comparavel entre unidades de portes diferentes


# --- Razoes (Bloco B de INDICADORES.md) -----------------------------------------------------------


@dataclass(frozen=True)
class DefRazao:
    """Razao entre duas somas de `cursos`, no mesmo recorte e nas mesmas linhas."""

    ind: Indicador  # codigo, nome, unidade, dimensoes territoriais e limitacoes
    # Colunas; quando `usa_base`, sufixo aplicado ao prefixo da base (o denominador e o prefixo).
    numerador: str
    denominador: str
    nome_numerador: str
    nome_denominador: str
    usa_base: bool
    percentual: bool  # True: numerador contido no denominador, valor em %
    dimensoes: frozenset[Dimensao]  # admitidas em qualquer nivel
    dimensao_unica: bool  # as dimensoes admitidas nao podem ser somadas numa unica razao
    municipal: bool  # servida no nivel municipal


_COM_BASE = frozenset({Dimensao.PRESENCIAL, Dimensao.EAD_POLO, Dimensao.EAD_EXTERIOR})
_LIM_SO_AGREGADO = "Só o agregado é publicado: os tipos se sobrepõem, não formam composição e não podem ser somados."


def _razao(
    slug: str,
    codigo: str,
    nome: str,
    unidade: str,
    territoriais: frozenset[Dimensao],
    limitacoes: tuple[str, ...],
) -> Indicador:
    return Indicador(slug, codigo, nome, unidade, "cursos", "", territoriais, limitacoes)


RAZOES: dict[str, DefRazao] = {
    d.ind.slug: d
    for d in (
        DefRazao(
            ind=_razao(
                "financiamento",
                "IND-R-08",
                "Participação de financiamento estudantil",
                "%",
                DIMENSOES_COM_TERRITORIO,
                (
                    _LIM_SO_AGREGADO,
                    "Praticamente só existe na rede privada (37,5% das matrículas, contra 0,5% na "
                    "pública): sem fixar a rede, a comparação mostra sobretudo a composição da oferta.",
                    "Não distingue bolsa integral de parcial nem mede valor financeiro.",
                    _LIM_VINCULO,
                ),
            ),
            numerador="financ",
            denominador="",
            nome_numerador="com financiamento ou auxílio declarado",
            nome_denominador="",
            usa_base=True,
            percentual=True,
            dimensoes=_COM_BASE,
            dimensao_unica=False,
            municipal=False,
        ),
        DefRazao(
            ind=_razao(
                "reserva_vagas",
                "IND-R-09",
                "Participação de reserva de vagas",
                "%",
                DIMENSOES_COM_TERRITORIO,
                (
                    _LIM_SO_AGREGADO,
                    "A reserva concentra-se na rede pública: comparar territórios ou categorias sem "
                    "controlar a rede confunde política de acesso com composição da oferta.",
                    _LIM_VINCULO,
                ),
            ),
            numerador="reserva_vaga",
            denominador="",
            nome_numerador="com reserva de vagas",
            nome_denominador="",
            usa_base=True,
            percentual=True,
            dimensoes=_COM_BASE,
            dimensao_unica=False,
            municipal=False,
        ),
        DefRazao(
            ind=_razao(
                "ingressantes_por_vaga",
                "IND-R-10",
                "Ingressantes por vaga ofertada",
                "ingressos por vaga",
                _SO_PRESENCIAL,
                (
                    "Exclusivamente presencial: em EAD, ingressos e vagas estão em dimensões diferentes da base.",
                    "Não é taxa de ocupação: a base não garante que os ingressos do ano venham das "
                    "vagas do mesmo ano, nem que vaga não preenchida seja ociosidade.",
                    "Um terço das vagas do denominador (33,6%) são remanescentes, com razão muito "
                    "menor (0,14) que a das vagas novas (0,42): o valor mistura as duas.",
                    "As redes pública e privada têm valores muito diferentes neste indicador: comparar "
                    "territórios, áreas ou graus sem fixar a rede mostra sobretudo a composição da oferta.",
                    "Pode exceder 1 (ingresso por programa especial ou vaga remanescente).",
                    "Sem vaga ofertada no recorte, a razão não se aplica — não é zero.",
                ),
            ),
            numerador="qt_ing",
            denominador="qt_vg_total",
            nome_numerador="Ingressantes",
            nome_denominador="Vagas ofertadas",
            usa_base=False,
            percentual=False,
            dimensoes=_SO_PRESENCIAL,
            dimensao_unica=True,
            municipal=True,
        ),
        DefRazao(
            ind=_razao(
                "inscricoes_por_vaga",
                "IND-R-11",
                "Inscrições por vaga ofertada",
                "inscrições por vaga",
                _SO_PRESENCIAL,
                (
                    "Inscrições não são pessoas: uma pessoa pode inscrever-se em vários cursos e "
                    "instituições. Não é 'candidatos por vaga'.",
                    "Processos seletivos têm regras diferentes entre IES: a razão não mede seletividade "
                    "nem concorrência. Na rede pública (cerca de 5 inscrições por vaga, contra 1 na "
                    "privada) reflete sistemas de inscrição em vários cursos.",
                    "As redes pública e privada têm valores muito diferentes neste indicador: comparar "
                    "territórios, áreas ou graus sem fixar a rede mostra sobretudo a composição da oferta.",
                    "Por território, só no presencial; a dimensão EAD 'somente a nível Brasil' não "
                    "tem município, UF nem região e nunca é somada à presencial.",
                ),
            ),
            numerador="qt_inscrito_total",
            denominador="qt_vg_total",
            nome_numerador="Inscrições",
            nome_denominador="Vagas ofertadas",
            usa_base=False,
            percentual=False,
            dimensoes=frozenset({Dimensao.PRESENCIAL, Dimensao.EAD_NACIONAL}),
            dimensao_unica=True,
            municipal=True,
        ),
    )
}
