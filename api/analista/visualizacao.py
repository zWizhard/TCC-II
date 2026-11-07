"""Spec de visualizacao: estrutura validada, nunca codigo.

O frontend so interpreta esta spec; nada aqui e HTML, JavaScript ou expressao executavel. O
`visualization_hint` do LLM e apenas sugestao: quem decide e o backend, pela FORMA do resultado
(um valor -> kpi; um agrupamento -> bar/ranking/composition/map; dois -> heatmap ou tabela), e
a spec final e conferida contra as colunas que o resultado realmente tem.

`line` esta na allowlist de tipos do projeto, mas e sempre rejeitado nesta base: so existe o
ano de 2024, e um grafico de linha sugeriria serie temporal. O titulo e montado pelo backend com
nomes da camada semantica e ainda assim passa pelo saneamento (sem `<`, `>`, `javascript:`...).
"""

import re
from collections.abc import Collection
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.analista.plano import Intencao, TipoVisualizacao
from api.analista.sql import ColunaSaida
from api.analista.validacao import PlanoValidado, aditiva
from api.consultas import ANO_CENSO
from api.indicadores import Nivel
from api.semantica import CAMADA, CamadaSemantica

_PROIBIDO_NO_TITULO = re.compile(
    r"[<>{}`\\\x00-\x1f]|javascript\s*:|data\s*:|vbscript\s*:|\bon\w+\s*=|&#|&\w+;", re.IGNORECASE
)
_NIVEIS_COM_MAPA = frozenset({Nivel.UF, Nivel.MUNICIPIO})


class SpecInvalida(ValueError):
    pass


class SpecVisualizacao(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: TipoVisualizacao
    title: str = Field(min_length=1, max_length=200)
    x: str | None = None  # coluna de categoria (ou o codigo territorial, no mapa)
    y: tuple[str, ...] = Field(default=(), max_length=8)  # colunas de metrica
    series: str | None = None  # segunda categoria (heatmap)
    notes: tuple[str, ...] = ()

    @field_validator("title")
    @classmethod
    def _titulo_sem_marcacao(cls, titulo: str) -> str:
        if _PROIBIDO_NO_TITULO.search(titulo):
            raise ValueError("título com marcação, script ou caractere de controle")
        return titulo

    @model_validator(mode="after")
    def _forma(self) -> Self:
        if self.type == TipoVisualizacao.LINE:
            raise ValueError(
                f"gráfico de linha não se aplica: a base tem um único ano ({ANO_CENSO})"
            )
        precisa_x = self.type not in (TipoVisualizacao.KPI, TipoVisualizacao.TABLE)
        if precisa_x and (self.x is None or not self.y):
            raise ValueError(f"'{self.type}' exige x e ao menos uma coluna em y")
        if self.type == TipoVisualizacao.KPI and (self.x is not None or not self.y):
            raise ValueError("'kpi' exige y e não tem x")
        if (self.type == TipoVisualizacao.HEATMAP) != (self.series is not None):
            raise ValueError("'series' é exigido no heatmap, e só nele")
        return self


def validar_spec(spec: SpecVisualizacao, colunas: Collection[str]) -> SpecVisualizacao:
    """Toda coluna citada pela spec tem de existir no resultado."""
    citadas = [c for c in (spec.x, spec.series, *spec.y) if c is not None]
    fora = [c for c in citadas if c not in colunas]
    if fora:
        raise SpecInvalida(f"a visualização cita coluna que o resultado não tem: {fora}")
    if len(set(citadas)) != len(citadas):
        raise SpecInvalida("a visualização repete uma coluna")
    return spec


def construir_spec(dados: dict[str, object], colunas: Collection[str]) -> SpecVisualizacao:
    """Spec vinda de fora (teste, ou um modelo no futuro): schema fechado + colunas existentes."""
    try:
        spec = SpecVisualizacao.model_validate(dados)
    except ValueError as exc:  # ValidationError do Pydantic e ValueError
        raise SpecInvalida("spec de visualização fora do formato permitido") from exc
    return validar_spec(spec, colunas)


def _titulo(validado: PlanoValidado, camada: CamadaSemantica) -> str:
    texto = " e ".join(m.nome for m in validado.metricas)
    if validado.agrupamentos:
        texto += " por " + " e ".join(camada.dimensao(a).nome for a in validado.agrupamentos)
    return f"{texto} — Censo {ANO_CENSO}"


def decidir_spec(
    validado: PlanoValidado,
    colunas: tuple[ColunaSaida, ...],
    n_linhas: int,
    truncado: bool,
    camada: CamadaSemantica | None = None,
) -> SpecVisualizacao:
    """Escolhe o tipo pela forma do resultado; o hint so desempata entre os tipos cabiveis."""
    camada = camada or CAMADA
    plano = validado.plano
    hint = plano.visualization_hint
    dims = [c.id for c in colunas if c.papel == "dimensao"]
    codigos = {c.referencia: c.id for c in colunas if c.papel == "codigo"}
    y = tuple(c.id for c in colunas if c.papel == "metrica")
    uma_metrica = len(y) == 1
    notas: list[str] = []

    tipo = TipoVisualizacao.TABLE
    x: str | None = None
    series: str | None = None
    if n_linhas == 0:
        notas.append("Sem linhas no resultado.")
    elif not dims:
        tipo = TipoVisualizacao.KPI
    elif len(dims) == 1:
        x = dims[0]
        somavel = uma_metrica and aditiva(validado.metricas[0])
        cabiveis = {TipoVisualizacao.BAR, TipoVisualizacao.RANKING, TipoVisualizacao.TABLE}
        if somavel and not truncado and not plano.having:
            cabiveis.add(TipoVisualizacao.COMPOSITION)
        # Mapa parcial engana: area sem cor pareceria 'sem dado', e nao 'cortada'.
        inteiro = not truncado and not plano.having
        if uma_metrica and inteiro and plano.dimensions.nivel_territorial in _NIVEIS_COM_MAPA:
            cabiveis.add(TipoVisualizacao.MAP)
        ordenado = plano.intent == Intencao.RANKING and uma_metrica
        tipo = TipoVisualizacao.RANKING if ordenado else TipoVisualizacao.BAR
        if not uma_metrica:
            tipo = TipoVisualizacao.TABLE
            cabiveis = {TipoVisualizacao.TABLE, TipoVisualizacao.BAR}
        if hint in cabiveis:
            tipo = hint
        if tipo == TipoVisualizacao.MAP:
            # O mapa casa com a malha pelo codigo; no municipio a propria coluna ja e o codigo.
            x = codigos.get(str(plano.dimensions.nivel_territorial), x)
    elif len(dims) == 2 and uma_metrica and hint == TipoVisualizacao.HEATMAP:
        tipo, x, series = TipoVisualizacao.HEATMAP, dims[0], dims[1]
    if hint is not None and hint != tipo:
        notas.append(f"A sugestão '{hint}' não cabe na forma do resultado; usado '{tipo}'.")
    if tipo == TipoVisualizacao.TABLE:
        x = None
    spec = SpecVisualizacao(
        type=tipo,
        title=_titulo(validado, camada),
        x=x,
        y=y if tipo != TipoVisualizacao.TABLE else (),
        series=series,
        notes=tuple(notas),
    )
    return validar_spec(spec, [c.id for c in colunas])
