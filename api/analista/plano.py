"""QueryPlan: a unica coisa que o LLM pode devolver (Fase 13).

O plano so carrega identificadores da camada semantica e enums fechados. Nao ha campo de texto
livre: nada aqui vira SQL por concatenacao. Todo identificador obedece a `_ID` (letras, digitos e
sublinhado), de modo que uma string como "SP'; DROP TABLE ies;--" nem chega a ser um plano.

Como `dimensions` e `group_by` se relacionam (nao sao redundantes):

- `dimensions` DECLARA as dimensoes obrigatorias, que nao sao coluna de agrupamento livre: o
  recorte territorial (ADR-0004), o nivel territorial e as dimensoes de oferta somadas. Os tres
  campos sao obrigatorios e sem padrao: plano que omita qualquer um e invalido.
- `group_by` lista as quebras por dimensao CATEGORICA (rede, grau, area...). O agrupamento por
  territorio vem so de `dimensions.nivel_territorial`: `regiao`, `uf` e `municipio` em `group_by`
  sao rejeitados, para que os dois campos nunca digam coisas diferentes.

As colunas de dimensao do resultado sao, nesta ordem: o nivel territorial (se nao for Brasil) e
depois cada item de `group_by`.

Existir como QueryPlan nao basta: o plano ainda passa por `validacao.validar_plano`, contra a
camada e contra o contexto da pergunta, antes de qualquer SQL.
"""

import json
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from api.erros import RespostaDoModeloInvalida
from api.indicadores import Dimensao, Nivel, Recorte

TETO_LINHAS = 1000  # teto rigido de linhas de uma resposta; nenhuma configuracao o ultrapassa
LIMITE_PADRAO = 100
MAX_METRICAS = 4
MAX_FILTROS = 8
MAX_VALORES_POR_FILTRO = 30
MAX_AGRUPAMENTOS = 2

_ID = r"^[A-Za-z0-9_]{1,64}$"
Identificador = Annotated[str, StringConstraints(pattern=_ID)]


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Intencao(StrEnum):
    VALOR = "valor"  # um unico numero por metrica, sem agrupamento
    DISTRIBUICAO = "distribuicao"  # uma linha por grupo
    RANKING = "ranking"  # grupos ordenados por uma metrica


class EntidadePlano(StrEnum):
    # Sem docstring de proposito nas classes do plano que citariam detalhe tecnico: a docstring
    # vira `description` do JSON Schema, e o schema vai ao LLM. Uma consulta usa UMA entidade:
    # IES e cursos nunca sao combinados no Analista IA.

    IES = "ies"
    CURSOS = "cursos"


class Operador(StrEnum):
    MAIOR = ">"
    MAIOR_OU_IGUAL = ">="
    MENOR = "<"
    MENOR_OU_IGUAL = "<="
    IGUAL = "="


class Direcao(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TipoVisualizacao(StrEnum):
    KPI = "kpi"
    TABLE = "table"
    BAR = "bar"
    RANKING = "ranking"
    COMPOSITION = "composition"
    LINE = "line"
    MAP = "map"
    HEATMAP = "heatmap"


class DimensoesDeclaradas(_Modelo):
    """Dimensoes obrigatorias. Sem padrao: omitir qualquer uma invalida o plano."""

    recorte: Recorte
    nivel_territorial: Nivel
    # Vazio so para a entidade `ies`, que nao tem dimensao de oferta.
    dimensao_de_oferta: tuple[Dimensao, ...] = Field(max_length=len(Dimensao))


class Filtro(_Modelo):
    """`dimensao` em qualquer um dos `valores` (uniao dentro da mesma dimensao)."""

    dimensao: Identificador
    # Ids de valores da camada; em `municipio`, codigos IBGE de 7 digitos.
    valores: tuple[Identificador, ...] = Field(min_length=1, max_length=MAX_VALORES_POR_FILTRO)


class Having(_Modelo):
    metrica: Identificador
    operador: Operador
    # Teto de magnitude: nenhuma contagem da base chega perto, e evita overflow no motor.
    valor: Annotated[int | float, Field(allow_inf_nan=False, ge=-1e15, le=1e15)]


class Ordenacao(_Modelo):
    por: Identificador  # metrica do plano, nivel territorial ou dimensao de `group_by`
    direcao: Direcao = Direcao.DESC


class QueryPlan(_Modelo):
    intent: Intencao
    entity: EntidadePlano
    metrics: tuple[Identificador, ...] = Field(min_length=1, max_length=MAX_METRICAS)
    dimensions: DimensoesDeclaradas
    filters: tuple[Filtro, ...] = Field(default=(), max_length=MAX_FILTROS)
    group_by: tuple[Identificador, ...] = Field(default=(), max_length=MAX_AGRUPAMENTOS)
    having: tuple[Having, ...] = Field(default=(), max_length=MAX_METRICAS)
    order_by: tuple[Ordenacao, ...] = Field(default=(), max_length=3)
    # O teto (`TETO_LINHAS` ou a configuracao, o menor) e conferido em `validar_plano`.
    limit: int = Field(default=LIMITE_PADRAO, ge=1)
    visualization_hint: TipoVisualizacao | None = None


def _sem_chave_repetida(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    chaves = [k for k, _ in pares]
    if len(set(chaves)) != len(chaves):
        raise ValueError("chave repetida no JSON")
    return dict(pares)


def interpretar_plano(texto: str) -> QueryPlan:
    """Texto do LLM -> QueryPlan, em modo estrito. Qualquer desvio e erro (502), nunca conserto.

    Sem regex de resgate e sem nova tentativa: com temperatura 0 a repeticao seria identica.
    """
    try:
        # Chave repetida e rejeitada: o parser ficaria com a ultima, e quem le o log
        # veria a primeira.
        json.loads(texto, object_pairs_hook=_sem_chave_repetida)
    except (ValueError, RecursionError) as exc:
        raise RespostaDoModeloInvalida(
            "O modelo não devolveu um JSON válido (ou repetiu uma chave)."
        ) from exc
    try:
        return QueryPlan.model_validate_json(texto, strict=True)
    except ValidationError as exc:
        # So local e tipo de cada problema: o conteudo devolvido pelo modelo nao e ecoado.
        problemas = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '(raiz)'}: {e['type']}"
            for e in exc.errors()[:8]
        )
        raise RespostaDoModeloInvalida(
            f"O modelo não devolveu um plano de consulta válido ({problemas})."
        ) from exc
