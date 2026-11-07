"""Schemas de resposta. Todo indicador territorial declara recorte, nivel e filtros (ADR-0004)."""

from pydantic import BaseModel, Field

from api.indicadores import (
    UF,
    Agrupamento,
    AreaCine,
    BaseFluxo,
    Categoria,
    Dimensao,
    Eixo,
    Grau,
    Nivel,
    NivelMalha,
    OrdemInstituicoes,
    Organizacao,
    Recorte,
    Rede,
    Regiao,
    TipoComparacao,
)


class Saude(BaseModel):
    status: str
    base_analitica: str


class DimensaoOferta(BaseModel):
    slug: Dimensao
    rotulo: str = Field(description="Valor literal de tp_dimensao no Censo.")
    territorializavel: bool
    modalidade: str = Field(description="Valor literal de tp_modalidade_ensino nessa dimensao.")


class RegiaoInfo(BaseModel):
    slug: Regiao
    nome: str


class UFInfo(BaseModel):
    sigla: UF
    nome: str
    regiao: Regiao


class CategoriaInfo(BaseModel):
    slug: Categoria
    rotulo: str = Field(description="Valor literal de tp_categoria_administrativa.")
    rede: Rede


class OrganizacaoInfo(BaseModel):
    slug: Organizacao
    rotulo: str = Field(description="Valor literal de tp_organizacao_academica.")


class AreaCineInfo(BaseModel):
    slug: AreaCine
    codigo: int = Field(description="Valor de co_cine_area_geral.")
    nome: str = Field(description="Valor literal de no_cine_area_geral.")


class GrauInfo(BaseModel):
    slug: Grau
    rotulo: str = Field(description="Valor literal de tp_grau_academico.")


class Metadados(BaseModel):
    ano_censo: str
    fonte: str
    extraido_em: str | None = Field(description="Data de extracao da copia local (ETL_MANIFEST).")
    recortes: list[Recorte]
    niveis: list[Nivel]
    dimensoes_oferta: list[DimensaoOferta]
    regioes: list[RegiaoInfo]
    ufs: list[UFInfo]
    categorias: list[CategoriaInfo]
    organizacoes: list[OrganizacaoInfo]
    areas_cine: list[AreaCineInfo]
    graus: list[GrauInfo]
    aviso: str


class IndicadorInfo(BaseModel):
    slug: str
    codigo: str = Field(
        description="Identificador da ficha em docs/tcc/methodology/INDICADORES.md."
    )
    nome: str
    unidade: str
    recorte: Recorte
    exige_dimensao: bool
    dimensoes_territoriais: list[Dimensao]
    limitacoes: list[str]


class Filtros(BaseModel):
    dimensoes: list[str] = Field(description="Rotulos literais de tp_dimensao incluidos.")
    rede: str | None
    categoria: str | None = Field(description="Rotulo de tp_categoria_administrativa aplicado.")
    organizacao: str | None = Field(description="Rotulo de tp_organizacao_academica aplicado.")
    regiao: str | None
    uf: str | None
    municipio: str | None = Field(description="Codigo IBGE de 7 digitos aplicado como filtro.")


class Linha(BaseModel):
    codigo: str
    nome: str
    uf: str | None = None
    valor: int
    latitude: float | None = None
    longitude: float | None = None


class RespostaIndicador(BaseModel):
    indicador: IndicadorInfo
    ano_censo: str
    recorte: Recorte
    nivel: Nivel
    filtros: Filtros
    total: int = Field(description="Soma de todas as unidades do nivel, antes do limite.")
    unidades: int = Field(description="Numero de unidades com registro, antes do limite.")
    truncado: bool
    valor_sem_territorio: int | None = Field(
        description=(
            "Parcela do indicador sem municipio identificado (regra transversal 8): incluida no "
            "nivel brasil, excluida dos demais. Nula quando ha filtro territorial."
        )
    )
    notas: list[str] = Field(description="Ressalvas que dependem dos filtros escolhidos.")
    linhas: list[Linha]


class FiltrosComposicao(Filtros):
    area: str | None = Field(description="Rotulo de no_cine_area_geral aplicado como filtro.")
    grau: str | None = Field(description="Rotulo de tp_grau_academico aplicado como filtro.")


class LinhaComposicao(BaseModel):
    codigo: str
    nome: str
    grupo: str | None = Field(
        default=None, description="Area geral CINE a que o rotulo pertence (eixo rotulo_cine)."
    )
    valor: int
    participacao: float | None = Field(
        description="valor / total * 100, sobre todas as categorias. Nula se o total for zero."
    )


class RespostaComposicao(BaseModel):
    indicador: IndicadorInfo
    eixo: Eixo
    eixo_nome: str
    ficha: str | None = Field(
        description="Ficha do Bloco B de INDICADORES.md que esta composicao realiza, se houver."
    )
    ano_censo: str
    recorte: Recorte
    nivel: Nivel = Field(description="Nivel do territorio selecionado pelos filtros.")
    filtros: FiltrosComposicao
    total: int = Field(description="Soma de todas as categorias, antes do limite.")
    categorias: int = Field(description="Numero de categorias com registro, antes do limite.")
    truncado: bool
    notas: list[str]
    linhas: list[LinhaComposicao]


class RazaoInfo(IndicadorInfo):
    usa_base: bool = Field(description="Exige 'base': matriculas, ingressantes ou concluintes.")
    percentual: bool = Field(
        description="True: numerador contido no denominador, valor em %. False: razao simples."
    )
    dimensoes: list[Dimensao] = Field(
        description="Dimensoes de oferta admitidas em qualquer nivel."
    )
    dimensao_unica: bool = Field(description="Aceita uma unica dimensao de oferta por consulta.")
    municipal: bool = Field(description="Servida no nivel municipal.")


class ValorRazao(BaseModel):
    numerador: int
    denominador: int
    valor: float | None = Field(
        description="numerador / denominador (x 100 se percentual). Nula se o denominador for zero."
    )


class LinhaRazao(ValorRazao):
    codigo: str
    nome: str
    uf: str | None = None


class RespostaRazao(BaseModel):
    indicador: RazaoInfo
    base: BaseFluxo | None
    numerador_nome: str
    denominador_nome: str
    ano_censo: str
    recorte: Recorte
    nivel: Nivel = Field(
        description="Nivel das linhas quando 'por' e territorial; senao, o do territorio dos filtros."
    )
    por: Agrupamento | None
    filtros: Filtros
    geral: ValorRazao = Field(description="Razao no territorio selecionado pelos filtros.")
    unidades: int = Field(description="Numero de grupos com registro, antes do limite.")
    truncado: bool
    notas: list[str]
    linhas: list[LinhaRazao]


class LinhaCoropletico(BaseModel):
    codigo: str = Field(
        description="Codigo IBGE: 7 digitos (municipio) ou 2 (UF). E o `codarea` da malha."
    )
    nome: str
    uf: str
    numerador: int | None = Field(
        description="Matriculas. Nulo = unidade sem registro de oferta (ausencia, nao zero)."
    )
    denominador: int = Field(description="Populacao estimada da unidade.")
    valor: float | None = Field(description="numerador / denominador x 100.000. Nulo sem registro.")
    classe: int | None = Field(description="Indice da classe da legenda. Nulo sem registro.")


class ClasseCoropletico(BaseModel):
    indice: int
    minimo: float = Field(description="Menor valor observado na classe.")
    maximo: float = Field(description="Maior valor observado na classe.")
    unidades: int


class ValorCoropletico(BaseModel):
    numerador: int | None = Field(
        description="Nulo quando nenhuma unidade do territorio tem registro (ausencia, nao zero)."
    )
    denominador: int
    valor: float | None


class RespostaCoropletico(BaseModel):
    indicador: IndicadorInfo
    numerador_nome: str
    denominador_nome: str
    ano_censo: str
    ano_populacao: str
    recorte: Recorte
    nivel: NivelMalha
    filtros: Filtros
    geral: ValorCoropletico = Field(
        description="Razao no territorio dos filtros: o denominador e a populacao de TODAS as "
        "unidades do territorio, com ou sem oferta."
    )
    unidades: int = Field(description="Unidades do territorio (universo do denominador).")
    com_registro: int
    sem_registro: int = Field(description="Unidades sem linha de oferta: ausencia, nao zero.")
    metodo_classes: str
    classes: list[ClasseCoropletico]
    notas: list[str]
    linhas: list[LinhaCoropletico]


class UnidadeComparada(BaseModel):
    codigo: str = Field(
        description="Slug da regiao, sigla da UF, codigo IBGE de 7 digitos ou 'BR' (referencia)."
    )
    nome: str
    uf: str | None
    populacao: int = Field(description="Populacao estimada (IBGE), contexto de porte da unidade.")


class ValorComparado(BaseModel):
    valor: float | None = Field(
        description="Nulo = sem registro na base ou denominador zero: ausencia, nunca zero."
    )
    numerador: int | None = Field(description="So nos indicadores relativos.")
    denominador: int | None = Field(description="So nos indicadores relativos.")


class IndicadorComparado(BaseModel):
    slug: str
    codigo: str = Field(description="Ficha em docs/tcc/methodology/INDICADORES.md.")
    nome: str
    unidade: str
    tipo: TipoComparacao
    recorte: Recorte
    dimensoes: list[str] = Field(description="Rotulos de tp_dimensao; vazio na tabela de IES.")
    numerador_nome: str | None
    denominador_nome: str | None
    limitacoes: list[str]
    nao_se_aplica: str | None = Field(
        description="Motivo pelo qual a linha inteira nao se aplica aos filtros escolhidos."
    )
    valores: list[ValorComparado] = Field(description="Na mesma ordem de `unidades`.")
    referencia: ValorComparado = Field(description="Brasil, pela mesma definicao e mesmos filtros.")


class RespostaComparacao(BaseModel):
    ano_censo: str
    ano_populacao: str
    nivel: Nivel
    rede: str | None = Field(description="Rotulo da rede aplicada a todas as unidades.")
    dimensoes: list[str] = Field(description="Dimensoes de oferta fixas da comparacao.")
    unidades: list[UnidadeComparada] = Field(description="Na ordem pedida; a API nao ordena.")
    referencia: UnidadeComparada
    indicadores: list[IndicadorComparado]
    notas: list[str]


class LinhaInstituicao(BaseModel):
    co_ies: int
    nome: str
    sigla: str | None = Field(description="Nula quando sg_ies esta vazia (17,92% das IES).")
    uf: str
    municipio_codigo: str = Field(description="Codigo IBGE de 7 digitos do municipio de sede.")
    municipio: str
    rede: str
    categoria: str
    organizacao: str
    docentes: int
    tecnicos: int | None = Field(
        description="qt_tec_total e a unica coluna de ies que admite NULL."
    )
    # Metricas de curso: nulas quando a IES nao tem linha nas dimensoes de oferta selecionadas
    # (ausencia de oferta nessas dimensoes, nao zero registrado).
    cursos: int | None
    matriculas: int | None
    ingressantes: int | None
    concluintes: int | None


class TotaisInstituicoes(BaseModel):
    ies: int
    ies_com_oferta: int = Field(
        description="IES com ao menos uma linha nas dimensoes de oferta selecionadas."
    )
    docentes: int
    tecnicos: int
    # Nulos quando ha filtro territorial: somar a oferta de toda a IES sob o territorio da sede
    # fabricaria "matriculas do territorio" que nao sao as de IND-D-03 (IND-Q-03, IND-Q-06).
    cursos: int | None
    matriculas: int | None
    ingressantes: int | None
    concluintes: int | None


class RespostaInstituicoes(BaseModel):
    ano_censo: str
    recorte: Recorte = Field(description="O filtro territorial vale para a sede da IES.")
    filtros: Filtros
    ordem: OrdemInstituicoes
    pagina: int
    limite: int
    paginas: int
    totais: TotaisInstituicoes = Field(
        description="Somas sobre todas as IES que atendem aos filtros, antes da paginacao."
    )
    notas: list[str]
    linhas: list[LinhaInstituicao]


class MunicipioInfo(BaseModel):
    codigo: str = Field(description="Codigo IBGE de 7 digitos.")
    nome: str
    sede: bool = Field(description="Ha IES com sede no municipio.")
    oferta: bool = Field(description="Ha curso presencial ou polo EAD no municipio.")


class RespostaMunicipios(BaseModel):
    ano_censo: str
    uf: UF
    municipios: list[MunicipioInfo]
