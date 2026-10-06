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
