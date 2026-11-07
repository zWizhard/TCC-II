"""Geracao do SQL a partir de um plano JA validado. O LLM nunca escreve SQL.

O texto do SQL e montado so com fragmentos fixos: a tabela e as colunas vem da camada semantica
(`entidade.tabela`, `metrica.expressao`, `metrica.filtro_obrigatorio`, colunas das dimensoes) e
as palavras-chave deste modulo. Todo VALOR vai como parametro nomeado do DuckDB — literais de
filtro, dimensoes de oferta, limiar do HAVING, ano e limite. Nada que venha do modelo ou do
usuario e concatenado: do plano saem apenas ids ja conferidos contra a camada, usados como chave
de dicionario, e os valores vinculados.

Regras de dados aplicadas sempre (CLAUDE.md, INDICADORES.md):
- `nu_ano_censo = $ano`, com o ano como TEXTO;
- em cursos, `tp_dimensao` declarada em toda consulta e o filtro de 7 digitos de `co_municipio`
  sempre que ha territorio (nivel, filtro ou quebra territorial);
- a rede e lida de `ies.ds_rede` / `cursos.tp_rede` (e a coluna que a camada declara);
- uma tabela por consulta: metrica de IES nunca e agregada apos JOIN com cursos;
- `LIMIT` sempre. O limite vinculado e `plano.limit + 1`: a linha a mais so serve para o pipeline
  sinalizar truncamento e e cortada antes da resposta.
"""

import re
from dataclasses import dataclass
from typing import Any, Literal

from api.analista.plano import Direcao, Operador
from api.analista.validacao import PlanoValidado
from api.consultas import ANO_CENSO
from api.semantica import CAMADA, CamadaSemantica
from api.semantica.modelos import ColunaDimensao, DimensaoSemantica, Metrica

_COLUNA_ANO = "nu_ano_censo"
_REGRA_7_DIGITOS = "filtro_7_digitos"
_DIMENSAO_DE_OFERTA = "dimensao"
_IDENTIFICADOR = re.compile(r"[a-z][a-z0-9_]*")
_OPERADOR_SQL: dict[Operador, str] = {
    Operador.MAIOR: ">",
    Operador.MAIOR_OU_IGUAL: ">=",
    Operador.MENOR: "<",
    Operador.MENOR_OU_IGUAL: "<=",
    Operador.IGUAL: "=",
}
_DIRECAO_SQL: dict[Direcao, str] = {Direcao.ASC: "ASC", Direcao.DESC: "DESC"}


@dataclass(frozen=True)
class ColunaSaida:
    id: str  # alias no SQL e nome da coluna no resultado
    nome: str
    papel: Literal["dimensao", "codigo", "metrica"]
    referencia: str  # id da dimensao ou da metrica na camada
    unidade: str | None = None


@dataclass(frozen=True)
class ConsultaGerada:
    sql: str
    params: dict[str, Any]
    entidade: str  # escopo do validador AST
    colunas: tuple[ColunaSaida, ...]
    limite: int  # linhas que a resposta pode trazer (o SQL pede uma a mais)


def _alias(id_: str) -> str:
    # Os ids vem da camada; a conferencia aqui e so uma segunda trava.
    if not _IDENTIFICADOR.fullmatch(id_):
        raise ValueError(f"identificador inesperado na camada: {id_!r}")
    return id_


def coluna_da_dimensao(d: DimensaoSemantica, entidade: str) -> ColunaDimensao:
    """Coluna da dimensao na tabela da consulta (a primeira declarada na camada)."""
    return next(c for c in d.colunas if c.entidade == entidade)


def _literais(d: DimensaoSemantica, entidade: str, valores: tuple[str, ...]) -> list[str | int]:
    """Valores do plano -> literais da coluna, como a camada os declara (tipo incluido)."""
    coluna = coluna_da_dimensao(d, entidade).coluna
    if not d.valores_enumerados:  # so `municipio` chega aqui: o codigo de 7 digitos e o literal
        return list(valores)
    por_id = {str(v.id): v for v in d.valores}
    return [
        next(
            lit.valor
            for lit in por_id[v].literais
            if lit.entidade == entidade and lit.coluna == coluna
        )
        for v in valores
    ]


def _expressao(m: Metrica) -> str:
    if m.tipo == "direta":
        return f"CAST(coalesce({m.expressao}, 0) AS BIGINT)"
    return f"CAST({m.expressao} AS DOUBLE)"  # razao: denominador zero fica nulo, nunca zero


def gerar_sql(validado: PlanoValidado, camada: CamadaSemantica | None = None) -> ConsultaGerada:
    camada = camada or CAMADA
    plano = validado.plano
    entidade = str(plano.entity)
    tabela = camada.entidade(entidade).tabela
    camada.coluna(entidade, _COLUNA_ANO)  # a coluna do ano existe nesta tabela, ou falha aqui

    condicoes = [f"{_COLUNA_ANO} = $ano"]
    params: dict[str, Any] = {"ano": ANO_CENSO}
    if entidade == "cursos":
        oferta = camada.dimensao(_DIMENSAO_DE_OFERTA)
        coluna = coluna_da_dimensao(oferta, entidade).coluna
        condicoes.append(f"list_contains($oferta, {coluna})")
        params["oferta"] = _literais(
            oferta, entidade, tuple(str(d) for d in plano.dimensions.dimensao_de_oferta)
        )
        if validado.territorial:
            predicado = camada.regra(_REGRA_7_DIGITOS).predicado
            assert predicado is not None
            condicoes.append(predicado)
    for m in validado.metricas:
        if m.filtro_obrigatorio is not None and m.filtro_obrigatorio not in condicoes:
            condicoes.append(m.filtro_obrigatorio)
    for i, f in enumerate(plano.filters):
        d = camada.dimensao(f.dimensao)
        condicoes.append(f"list_contains($f{i}, {coluna_da_dimensao(d, entidade).coluna})")
        params[f"f{i}"] = _literais(d, entidade, f.valores)

    selecao: list[str] = []
    colunas: list[ColunaSaida] = []
    chaves: list[str] = []  # expressoes do GROUP BY
    desempate: list[str] = []  # alias que tornam a ordem deterministica
    alias_de: dict[str, str] = {}  # id do plano -> alias pelo qual se ordena
    for id_ in validado.agrupamentos:
        d = camada.dimensao(id_)
        col = coluna_da_dimensao(d, entidade)
        alias = _alias(id_)
        chaves.append(col.coluna)
        if col.coluna_rotulo is None:
            selecao.append(f"{col.coluna} AS {alias}")
            colunas.append(ColunaSaida(alias, d.nome, "dimensao", id_))
            desempate.append(alias)
        else:
            # Pares codigo/rotulo sao 1:1 (conferido na camada): any_value nao escolhe nada.
            selecao.append(f"{col.coluna} AS {alias}_codigo")
            selecao.append(f"any_value({col.coluna_rotulo}) AS {alias}")
            colunas.append(ColunaSaida(f"{alias}_codigo", f"{d.nome} (código)", "codigo", id_))
            colunas.append(ColunaSaida(alias, d.nome, "dimensao", id_))
            desempate.append(f"{alias}_codigo")
        alias_de[id_] = alias
    for m in validado.metricas:
        alias = _alias(m.id)
        selecao.append(f"{_expressao(m)} AS {alias}")
        colunas.append(ColunaSaida(alias, m.nome, "metrica", m.id, m.unidade))
        alias_de[m.id] = alias

    partes = [
        f"SELECT {', '.join(selecao)}",
        f"FROM {tabela}",
        f"WHERE {' AND '.join(condicoes)}",
    ]
    if chaves:
        partes.append(f"GROUP BY {', '.join(chaves)}")
    por_id = {m.id: m for m in validado.metricas}
    limiares: list[str] = []
    for i, h in enumerate(plano.having):
        limiares.append(f"{por_id[h.metrica].expressao} {_OPERADOR_SQL[h.operador]} $h{i}")
        params[f"h{i}"] = h.valor
    if limiares:
        partes.append(f"HAVING {' AND '.join(limiares)}")
    if chaves:
        ordem = [f"{alias_de[o.por]} {_DIRECAO_SQL[o.direcao]} NULLS LAST" for o in plano.order_by]
        if not ordem:
            ordem = [f"{alias_de[validado.metricas[0].id]} DESC NULLS LAST"]
        ordem += [f"{a} ASC" for a in desempate]
        partes.append(f"ORDER BY {', '.join(ordem)}")
    partes.append("LIMIT $limite")
    params["limite"] = plano.limit + 1
    return ConsultaGerada("\n".join(partes), params, entidade, tuple(colunas), plano.limit)
