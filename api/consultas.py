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

from dataclasses import dataclass, replace
from typing import Any

from api.db import BaseAnalitica
from api.erros import ParametroInvalido
from api.indicadores import (
    CODIGO_REGIAO,
    REDE_DA_CATEGORIA,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_ORGANIZACAO,
    ROTULO_REDE,
    ROTULO_REGIAO,
    UF,
    UF_INFO,
    Categoria,
    Dimensao,
    Indicador,
    Nivel,
    Organizacao,
    Recorte,
    Rede,
    Regiao,
)
from api.schemas import (
    Filtros,
    IndicadorInfo,
    Linha,
    MunicipioInfo,
    RespostaIndicador,
    RespostaMunicipios,
)

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
_COLUNA_REGIAO = {"ies": "CAST(co_regiao_ies AS VARCHAR)", "cursos": "co_regiao"}
_COLUNA_MUNICIPIO = {"ies": "co_municipio_ies", "cursos": "co_municipio"}
# Mesmos nomes e mesmos rotulos nas duas tabelas; constantes por IES (medido em 2026-10-06).
_COLUNA_CATEGORIA = "tp_categoria_administrativa"
_COLUNA_ORGANIZACAO = "tp_organizacao_academica"
# Cada filtro territorial so vale do seu proprio nivel para baixo: no nivel 'uf', `uf=SP`
# devolve a linha de SP; no nivel 'municipio', os municipios de SP.
_NIVEIS_DO_FILTRO: dict[str, tuple[Nivel, ...]] = {
    "regiao": (Nivel.REGIAO, Nivel.UF, Nivel.MUNICIPIO),
    "uf": (Nivel.UF, Nivel.MUNICIPIO),
    "municipio": (Nivel.MUNICIPIO,),
}
_COM_TERRITORIO = "regexp_full_match(co_municipio, '[0-9]{7}')"
# Regra transversal 7 / ADR-0007.
_NOTA_PUBLICA = (
    "A rede Pública inclui as 28 IES de categoria administrativa Especial; "
    "não é sinônimo de pública em sentido estrito."
)


@dataclass(frozen=True)
class FiltrosConsulta:
    """Filtros opcionais de uma consulta. Todos enumerados, exceto `municipio` (7 digitos)."""

    rede: Rede | None = None
    categoria: Categoria | None = None
    organizacao: Organizacao | None = None
    regiao: Regiao | None = None
    uf: UF | None = None
    municipio: str | None = None

    @property
    def territorial(self) -> bool:
        return self.regiao is not None or self.uf is not None or self.municipio is not None

    def sem_territorio(self) -> "FiltrosConsulta":
        return replace(self, regiao=None, uf=None, municipio=None)


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
    filtros: FiltrosConsulta,
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
    for nome, niveis in _NIVEIS_DO_FILTRO.items():
        if getattr(filtros, nome) is not None and nivel not in niveis:
            raise ParametroInvalido(
                f"O filtro '{nome}' só se aplica aos níveis {[str(n) for n in niveis]}; "
                f"recebido nível '{nivel}'."
            )
    if filtros.uf is not None and filtros.regiao is not None:
        regiao_da_uf = UF_INFO[filtros.uf][1]
        if regiao_da_uf != filtros.regiao:
            raise ParametroInvalido(
                f"A UF {filtros.uf} pertence à região {ROTULO_REGIAO[regiao_da_uf]}, "
                f"não à região {ROTULO_REGIAO[filtros.regiao]}."
            )
    if filtros.categoria is not None and filtros.rede is not None:
        rede_da_categoria = REDE_DA_CATEGORIA[filtros.categoria]
        if rede_da_categoria != filtros.rede:
            raise ParametroInvalido(
                f"A categoria administrativa '{ROTULO_CATEGORIA[filtros.categoria]}' pertence "
                f"à rede {ROTULO_REDE[rede_da_categoria]}, não à rede {ROTULO_REDE[filtros.rede]}."
            )
    return dims


def _where(
    ind: Indicador, dims: list[Dimensao], filtros: FiltrosConsulta
) -> tuple[list[str], dict[str, Any]]:
    condicoes = ["nu_ano_censo = $ano"]
    params: dict[str, Any] = {"ano": ANO_CENSO}
    if dims:
        condicoes.append("list_contains($dims, tp_dimensao)")
        params["dims"] = [ROTULO_DIMENSAO[d] for d in dims]
    if filtros.rede is not None:
        condicoes.append(f"{_COLUNA_REDE[ind.tabela]} = $rede")
        params["rede"] = ROTULO_REDE[filtros.rede]
    if filtros.categoria is not None:
        condicoes.append(f"{_COLUNA_CATEGORIA} = $categoria")
        params["categoria"] = ROTULO_CATEGORIA[filtros.categoria]
    if filtros.organizacao is not None:
        condicoes.append(f"{_COLUNA_ORGANIZACAO} = $organizacao")
        params["organizacao"] = ROTULO_ORGANIZACAO[filtros.organizacao]
    if filtros.regiao is not None:
        condicoes.append(f"{_COLUNA_REGIAO[ind.tabela]} = $regiao")
        params["regiao"] = CODIGO_REGIAO[filtros.regiao]
    if filtros.uf is not None:
        condicoes.append(f"{_COLUNA_UF[ind.tabela]} = $uf")
        params["uf"] = str(filtros.uf)
    if filtros.municipio is not None:
        condicoes.append(f"{_COLUNA_MUNICIPIO[ind.tabela]} = $municipio")
        params["municipio"] = filtros.municipio
    return condicoes, params


def _sem_territorio(
    base: BaseAnalitica, ind: Indicador, dims: list[Dimensao], filtros: FiltrosConsulta
) -> int:
    """Parcela sem municipio identificado (regra transversal 8). IES: sempre com sede valida."""
    if ind.tabela == "ies":
        return 0
    condicoes, params = _where(ind, dims, filtros.sem_territorio())
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
    filtros: FiltrosConsulta | None = None,
    limite: int = LIMITE_MAXIMO,
) -> RespostaIndicador:
    filtros = filtros or FiltrosConsulta()
    dims = validar(ind, nivel, recorte, dimensoes, filtros)
    tabela = _TABELA[ind.tabela]
    condicoes, params = _where(ind, dims, filtros)

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
            rede=ROTULO_REDE[filtros.rede] if filtros.rede else None,
            categoria=ROTULO_CATEGORIA[filtros.categoria] if filtros.categoria else None,
            organizacao=ROTULO_ORGANIZACAO[filtros.organizacao] if filtros.organizacao else None,
            regiao=ROTULO_REGIAO[filtros.regiao] if filtros.regiao else None,
            uf=str(filtros.uf) if filtros.uf else None,
            municipio=filtros.municipio,
        ),
        total=total,
        unidades=unidades,
        truncado=unidades > len(linhas),
        valor_sem_territorio=(
            None if filtros.territorial else _sem_territorio(base, ind, dims, filtros)
        ),
        notas=[_NOTA_PUBLICA] if filtros.rede == Rede.PUBLICA else [],
        linhas=linhas,
    )


def listar_municipios(base: BaseAnalitica, uf: UF) -> RespostaMunicipios:
    """Municipios da UF que aparecem no Censo, como sede de IES ou como local de oferta.

    Serve so para popular o filtro de municipio. As duas tabelas sao lidas separadamente e
    empilhadas (UNION ALL), sem JOIN entre IES e cursos; o filtro de 7 digitos descarta as
    linhas de cursos sem territorio.
    """
    sql = f"""
        SELECT codigo, min(nome), bool_or(sede), bool_or(oferta)
        FROM (
            SELECT co_municipio_ies AS codigo, no_municipio_ies AS nome,
                   TRUE AS sede, FALSE AS oferta
            FROM {_TABELA["ies"]}
            WHERE nu_ano_censo = $ano AND sg_uf_ies = $uf
            UNION ALL
            SELECT co_municipio, no_municipio, FALSE, TRUE
            FROM {_TABELA["cursos"]}
            WHERE nu_ano_censo = $ano AND sg_uf = $uf AND {_COM_TERRITORIO}
        )
        GROUP BY codigo
        ORDER BY 2, 1
    """
    rows = base.consultar(sql, {"ano": ANO_CENSO, "uf": str(uf)})
    return RespostaMunicipios(
        ano_censo=ANO_CENSO,
        uf=uf,
        municipios=[MunicipioInfo(codigo=r[0], nome=r[1], sede=r[2], oferta=r[3]) for r in rows],
    )
