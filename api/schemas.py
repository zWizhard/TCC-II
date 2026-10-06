"""Schemas de resposta. Todo indicador territorial declara recorte, nivel e filtros (ADR-0004)."""

from pydantic import BaseModel, Field

from api.indicadores import Dimensao, Nivel, Recorte


class Saude(BaseModel):
    status: str
    base_analitica: str


class DimensaoOferta(BaseModel):
    slug: Dimensao
    rotulo: str = Field(description="Valor literal de tp_dimensao no Censo.")
    territorializavel: bool


class Metadados(BaseModel):
    ano_censo: str
    fonte: str
    extraido_em: str | None = Field(description="Data de extracao da copia local (ETL_MANIFEST).")
    recortes: list[Recorte]
    niveis: list[Nivel]
    dimensoes_oferta: list[DimensaoOferta]
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
    uf: str | None


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
            "nivel brasil, excluida dos demais. Nula quando ha filtro de UF."
        )
    )
    notas: list[str] = Field(description="Ressalvas que dependem dos filtros escolhidos.")
    linhas: list[Linha]
