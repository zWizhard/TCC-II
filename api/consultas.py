"""Consultas analiticas: validacao metodologica dos parametros + SQL de agregacao.

Todo SQL e montado so com fragmentos fixos deste modulo e do catalogo; valores de usuario
entram exclusivamente como parametros nomeados do DuckDB. Especificacao e JOIN auditados
contra o DuckDB local em 2026-09-26 (ver docs/data/JOIN_STRATEGY.md).

Regras aplicadas (docs/tcc/methodology/INDICADORES.md, regras transversais):
- ano como texto ('2024');
- tp_dimensao declarada em todo indicador de cursos (sem padrao);
- filtro de 7 digitos em co_municipio em TODO nivel territorial: limpa as 8 colunas
  contaminadas por 'Cursos a distância' nas mesmas linhas;
- metrica de IES agregada so na tabela de IES; nenhuma consulta junta IES com cursos;
- no nivel municipal, pre-agrega (1 linha por codigo) e so depois faz JOIN N:1 com municipio.
"""

from typing import Any

from api.db import BaseAnalitica
from api.erros import ParametroInvalido
from api.indicadores import (
    ROTULO_DIMENSAO,
    ROTULO_REDE,
    UF,
    Dimensao,
    Indicador,
    Nivel,
    Recorte,
    Rede,
)
from api.schemas import Filtros, IndicadorInfo, Linha, RespostaIndicador

ANO_CENSO = "2024"
# Teto de linhas por resposta: acima das 5.571 unidades municipais existentes.
LIMITE_MAXIMO = 6000

_TABELA = {"ies": "inep_educacao_superior_ies", "cursos": "inep_educacao_superior_cursos"}

# (codigo, nome, sigla da UF) por nivel. Pares codigo<->nome medidos 1:1 nas duas tabelas.
_COLUNAS_NIVEL: dict[str, dict[Nivel, tuple[str, str, str]]] = {
    "ies": {
        Nivel.REGIAO: ("CAST(co_regiao_ies AS VARCHAR)", "no_regiao_ies", "NULL"),
        Nivel.UF: ("co_uf_ies", "no_uf_ies", "sg_uf_ies"),
        Nivel.MUNICIPIO: ("co_municipio_ies", "no_municipio_ies", "sg_uf_ies"),
    },
    "cursos": {
        Nivel.REGIAO: ("co_regiao", "no_regiao", "NULL"),
        Nivel.UF: ("co_uf", "no_uf", "sg_uf"),
        Nivel.MUNICIPIO: ("co_municipio", "no_municipio", "sg_uf"),
    },
}
_COLUNA_REDE = {"ies": "ds_rede", "cursos": "tp_rede"}
_COLUNA_UF = {"ies": "sg_uf_ies", "cursos": "sg_uf"}
_COM_TERRITORIO = "regexp_full_match(co_municipio, '[0-9]{7}')"
# Regra transversal 7 / ADR-0007.
_NOTA_PUBLICA = (
    "A rede Pública inclui as 28 IES de categoria administrativa Especial; "
    "não é sinônimo de pública em sentido estrito."
)


def info(ind: Indicador) -> IndicadorInfo:
    return IndicadorInfo(
        slug=ind.slug,
        codigo=ind.codigo,
        nome=ind.nome,
        unidade=ind.unidade,
        recorte=ind.recorte,
        exige_dimensao=ind.exige_dimensao,
        dimensoes_territoriais=sorted(ind.dimensoes_territoriais),
        limitacoes=list(ind.limitacoes),
    )


def validar(
    ind: Indicador,
    nivel: Nivel,
    recorte: Recorte,
    dimensoes: list[Dimensao],
    uf: UF | None,
) -> list[Dimensao]:
    """Recusa combinacoes que a metodologia nao admite. Devolve as dimensoes normalizadas."""
    if recorte != ind.recorte:
        raise ParametroInvalido(
            f"{ind.codigo} só é definido no recorte '{ind.recorte}' (ADR-0004); "
            f"recebido '{recorte}'."
        )
    dims = sorted(set(dimensoes))
    if ind.exige_dimensao and not dims:
        raise ParametroInvalido(
            f"{ind.codigo} exige 'dimensao' declarada (tp_dimensao não tem padrão)."
        )
    if not ind.exige_dimensao and dims:
        raise ParametroInvalido(f"{ind.codigo} vem da tabela de IES, que não tem tp_dimensao.")
    if nivel != Nivel.BRASIL:
        fora = [d for d in dims if d not in ind.dimensoes_territoriais]
        if fora:
            raise ParametroInvalido(
                f"{ind.codigo} não é territorializável nas dimensões {[str(d) for d in fora]}; "
                f"no nível '{nivel}' admite apenas {sorted(str(d) for d in ind.dimensoes_territoriais)}."
            )
    if uf is not None and nivel != Nivel.MUNICIPIO:
        raise ParametroInvalido("O filtro 'uf' só se aplica ao nível 'municipio'.")
    return dims


def _where(
    ind: Indicador, dims: list[Dimensao], rede: Rede | None, uf: UF | None
) -> tuple[list[str], dict[str, Any]]:
    condicoes = ["nu_ano_censo = $ano"]
    params: dict[str, Any] = {"ano": ANO_CENSO}
    if dims:
        condicoes.append("list_contains($dims, tp_dimensao)")
        params["dims"] = [ROTULO_DIMENSAO[d] for d in dims]
    if rede is not None:
        condicoes.append(f"{_COLUNA_REDE[ind.tabela]} = $rede")
        params["rede"] = ROTULO_REDE[rede]
    if uf is not None:
        condicoes.append(f"{_COLUNA_UF[ind.tabela]} = $uf")
        params["uf"] = str(uf)
    return condicoes, params


def _sem_territorio(
    base: BaseAnalitica, ind: Indicador, dims: list[Dimensao], rede: Rede | None
) -> int:
    """Parcela sem municipio identificado (regra transversal 8). IES: sempre com sede valida."""
    if ind.tabela == "ies":
        return 0
    condicoes, params = _where(ind, dims, rede, None)
    sql = (
        f"SELECT CAST(coalesce({ind.expressao}, 0) AS BIGINT) FROM {_TABELA[ind.tabela]} "
        f"WHERE {' AND '.join(condicoes)} AND NOT {_COM_TERRITORIO}"
    )
    return int(base.consultar(sql, params)[0][0])


def consultar_indicador(
    base: BaseAnalitica,
    ind: Indicador,
    nivel: Nivel,
    recorte: Recorte,
    dimensoes: list[Dimensao],
    rede: Rede | None = None,
    uf: UF | None = None,
    limite: int = LIMITE_MAXIMO,
) -> RespostaIndicador:
    dims = validar(ind, nivel, recorte, dimensoes, uf)
    tabela = _TABELA[ind.tabela]
    condicoes, params = _where(ind, dims, rede, uf)

    if nivel == Nivel.BRASIL:
        sql = f"SELECT CAST(coalesce({ind.expressao}, 0) AS BIGINT) FROM {tabela} WHERE {' AND '.join(condicoes)}"
        valor = int(base.consultar(sql, params)[0][0])
        linhas = [Linha(codigo="BR", nome="Brasil", valor=valor)]
        total, unidades = valor, 1
    else:
        if ind.tabela == "cursos":
            condicoes.append(_COM_TERRITORIO)
        cod, nome, sigla = _COLUNAS_NIVEL[ind.tabela][nivel]
        municipal = nivel == Nivel.MUNICIPIO
        # Pre-agregacao garante 1 linha por codigo; o JOIN com municipio e N:1 (chave unica,
        # 0 orfaos, 0 sentinelas referenciadas) e so acrescenta coordenadas.
        sql = f"""
            WITH agg AS (
                SELECT {cod} AS codigo, any_value({nome}) AS nome, any_value({sigla}) AS uf,
                       CAST({ind.expressao} AS BIGINT) AS valor
                FROM {tabela}
                WHERE {" AND ".join(condicoes)}
                GROUP BY 1
            )
            SELECT a.codigo, a.nome, a.uf, a.valor,
                   {"CAST(m.latitude AS DOUBLE), CAST(m.longitude AS DOUBLE)" if municipal else "NULL, NULL"},
                   CAST(SUM(a.valor) OVER () AS BIGINT), COUNT(*) OVER ()
            FROM agg a
            {"LEFT JOIN municipio m ON m.codigo_municipio_dv = a.codigo" if municipal else ""}
            ORDER BY a.valor DESC, a.codigo
            LIMIT $limite
        """
        params["limite"] = limite
        rows = base.consultar(sql, params)
        linhas = [
            Linha(codigo=r[0], nome=r[1], uf=r[2], valor=r[3], latitude=r[4], longitude=r[5])
            for r in rows
        ]
        total = int(rows[0][6]) if rows else 0
        unidades = int(rows[0][7]) if rows else 0

    return RespostaIndicador(
        indicador=info(ind),
        ano_censo=ANO_CENSO,
        recorte=ind.recorte,
        nivel=nivel,
        filtros=Filtros(
            dimensoes=[ROTULO_DIMENSAO[d] for d in dims],
            rede=ROTULO_REDE[rede] if rede else None,
            uf=str(uf) if uf else None,
        ),
        total=total,
        unidades=unidades,
        truncado=unidades > len(linhas),
        valor_sem_territorio=None if uf else _sem_territorio(base, ind, dims, rede),
        notas=[_NOTA_PUBLICA] if rede == Rede.PUBLICA else [],
        linhas=linhas,
    )
