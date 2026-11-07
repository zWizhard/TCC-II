"""Razoes de Matriculas e Fluxo (Fase 9): IND-R-08, IND-R-09, IND-R-10 e IND-R-11.

Mesmas garantias de `api/consultas.py`: SQL montado so com fragmentos fixos do catalogo, valores
de usuario como parametros nomeados. Numerador e denominador sao somados NAS MESMAS LINHAS de
`cursos` (mesmo filtro, mesmas dimensoes, mesmo recorte) e so entao divididos — nenhuma razao
cruza dimensoes de oferta nem tabelas. Auditoria em scripts/analise/auditar_fluxo.py (2026-10-07).

O que NAO e servido aqui, por decisao metodologica (INDICADORES.md, Bloco C): qualquer razao
entre concluintes, ingressantes e matriculas (IND-Q-01), as situacoes de matricula (IND-Q-02) e
qualquer leitura temporal (IND-Q-04).
"""

from typing import Any

from api.analises import _COLUNAS_EIXO, _SLUG_DO_ROTULO, _filtros_resposta, nivel_dos_filtros
from api.consultas import (
    _COLUNA_REDE,
    _COLUNAS_NIVEL,
    _COM_TERRITORIO,
    _NOTA_PUBLICA,
    _TABELA,
    ANO_CENSO,
    LIMITE_MAXIMO,
    FiltrosConsulta,
    _where,
    info,
    validar,
)
from api.db import BaseAnalitica
from api.erros import ParametroInvalido
from api.indicadores import (
    AGRUPAMENTOS_TERRITORIAIS,
    CATALOGO,
    PREFIXO_BASE,
    Agrupamento,
    BaseFluxo,
    DefRazao,
    Dimensao,
    Eixo,
    Nivel,
    Recorte,
    Rede,
)
from api.schemas import Filtros, LinhaRazao, RazaoInfo, RespostaRazao, ValorRazao

_NOTA_SEM_MUNICIPIO = (
    "A comparação por território deixa de fora os registros de polo EAD sem município "
    "identificado; o valor do território selecionado os inclui."
)
_NOTA_REDE = (
    "Sem filtro de rede, as diferenças entre os grupos refletem em grande parte quanto da oferta "
    "de cada um é pública ou privada."
)
_NOTA_RETRATO = (
    "Retrato de 2024: numerador e denominador são do mesmo ano e do mesmo conjunto de cursos; "
    "a razão não acompanha uma turma ao longo do tempo."
)


def info_razao(d: DefRazao) -> RazaoInfo:
    return RazaoInfo(
        **info(d.ind).model_dump(),
        usa_base=d.usa_base,
        percentual=d.percentual,
        dimensoes=sorted(d.dimensoes),
        dimensao_unica=d.dimensao_unica,
        municipal=d.municipal,
    )


def _valor(d: DefRazao, numerador: int, denominador: int) -> float | None:
    """Denominador zero = razao nao aplicavel (nula), nunca zero."""
    if denominador == 0:
        return None
    return numerador / denominador * (100 if d.percentual else 1)


def _termos(d: DefRazao, base_fluxo: BaseFluxo | None) -> tuple[str, str, str, str]:
    """(coluna do numerador, coluna do denominador, nome do numerador, nome do denominador)."""
    if not d.usa_base:
        return d.numerador, d.denominador, d.nome_numerador, d.nome_denominador
    assert base_fluxo is not None
    prefixo = PREFIXO_BASE[base_fluxo]
    nome = CATALOGO[base_fluxo].nome
    return f"{prefixo}_{d.numerador}", prefixo, f"{nome} {d.nome_numerador}", nome


def consultar_razao(
    base: BaseAnalitica,
    d: DefRazao,
    recorte: Recorte,
    dimensoes: list[Dimensao],
    filtros: FiltrosConsulta | None = None,
    por: Agrupamento | None = None,
    base_fluxo: BaseFluxo | None = None,
    limite: int = LIMITE_MAXIMO,
) -> RespostaRazao:
    """Razao no territorio dos filtros e, opcionalmente, comparada por um agrupamento."""
    filtros = filtros or FiltrosConsulta()
    ind = d.ind
    territorial = por in AGRUPAMENTOS_TERRITORIAIS
    nivel = Nivel(por) if por is not None and territorial else nivel_dos_filtros(filtros)
    dims = validar(ind, nivel, recorte, dimensoes, filtros)

    if d.usa_base and base_fluxo is None:
        raise ParametroInvalido(
            f"{ind.codigo} exige 'base' declarada: matriculas, ingressantes ou concluintes."
        )
    if not d.usa_base and base_fluxo is not None:
        raise ParametroInvalido(f"{ind.codigo} tem numerador e denominador fixos; não usa 'base'.")
    fora = [dim for dim in dims if dim not in d.dimensoes]
    if fora:
        raise ParametroInvalido(
            f"{ind.codigo} não é definido nas dimensões {[str(x) for x in fora]}: nelas a base "
            f"não registra numerador e denominador juntos. Admite {sorted(str(x) for x in d.dimensoes)}."
        )
    if d.dimensao_unica and len(dims) != 1:
        raise ParametroInvalido(
            f"{ind.codigo} é calculado em uma única dimensão de oferta por vez: dimensões "
            "diferentes não são somadas numa mesma razão."
        )
    if por == Agrupamento.DIMENSAO and d.dimensao_unica:
        raise ParametroInvalido(f"{ind.codigo} não admite comparação por dimensão de oferta.")
    if nivel == Nivel.MUNICIPIO and not d.municipal:
        # Pendencia de INDICADORES.md: 304 municipios tem de 1 a 9 matriculas (2026-10-07).
        # Bloqueio por nivel, NAO piso: UF com filtros ainda devolve celulas pequenas.
        raise ParametroInvalido(
            f"{ind.codigo} não é servido no nível municipal: bloqueio provisório por nível, "
            "enquanto o piso de supressão para células pequenas não é definido."
        )
    if nivel == Nivel.MUNICIPIO and por == Agrupamento.AREA:
        raise ParametroInvalido(
            "Recortes por área CINE não são servidos no nível municipal: bloqueio provisório, "
            "enquanto o piso de supressão para células pequenas (IND-R-06) não é definido."
        )

    num, den, nome_num, nome_den = _termos(d, base_fluxo)
    tabela = _TABELA["cursos"]
    soma_num = f"CAST(coalesce(SUM({num}), 0) AS BIGINT)"
    soma_den = f"CAST(coalesce(SUM({den}), 0) AS BIGINT)"

    # Valor do territorio selecionado, nas dimensoes recebidas (com `por` territorial o cliente
    # so pode enviar as territorializaveis, entao o denominador pode diferir do nivel Brasil).
    condicoes, params = _where(ind, dims, filtros)
    if filtros.territorial:
        condicoes.append(_COM_TERRITORIO)
    g = base.consultar(
        f"SELECT {soma_num}, {soma_den} FROM {tabela} WHERE {' AND '.join(condicoes)}", params
    )[0]
    geral = ValorRazao(numerador=g[0], denominador=g[1], valor=_valor(d, int(g[0]), int(g[1])))

    linhas: list[LinhaRazao] = []
    unidades = 0
    if por is not None:
        params_linhas: dict[str, Any] = {**params, "limite": limite}
        if territorial:
            if not filtros.territorial:
                condicoes.append(_COM_TERRITORIO)
            cod, nome, sigla = _COLUNAS_NIVEL["cursos"][nivel]
            slugs: dict[str, str] = {}
        elif por == Agrupamento.REDE:
            cod = nome = _COLUNA_REDE["cursos"]
            sigla = "NULL"
            slugs = _SLUG_DO_ROTULO[Eixo.REDE]
        else:
            eixo = Eixo(por.value)
            cod, nome, _ = _COLUNAS_EIXO[eixo]
            sigla = "NULL"
            slugs = _SLUG_DO_ROTULO.get(eixo, {})
        rows = base.consultar(
            f"""
            WITH agg AS (
                SELECT {cod} AS codigo, any_value({nome}) AS nome, any_value({sigla}) AS uf,
                       {soma_num} AS numerador, {soma_den} AS denominador
                FROM {tabela}
                WHERE {" AND ".join(condicoes)}
                GROUP BY 1
            )
            SELECT codigo, nome, uf, numerador, denominador, COUNT(*) OVER ()
            FROM agg
            ORDER BY denominador DESC, codigo
            LIMIT $limite
            """,
            params_linhas,
        )
        unidades = int(rows[0][5]) if rows else 0
        linhas = [
            LinhaRazao(
                codigo=slugs.get(r[0], r[0]),
                nome=r[1],
                uf=r[2],
                numerador=r[3],
                denominador=r[4],
                valor=_valor(d, int(r[3]), int(r[4])),
            )
            for r in rows
        ]

    return RespostaRazao(
        indicador=info_razao(d),
        base=base_fluxo,
        numerador_nome=nome_num,
        denominador_nome=nome_den,
        ano_censo=ANO_CENSO,
        recorte=ind.recorte,
        nivel=nivel,
        por=por,
        filtros=Filtros(**_filtros_resposta(filtros, dims)),
        geral=geral,
        unidades=unidades,
        truncado=unidades > len(linhas),
        notas=[
            _NOTA_RETRATO,
            *(
                [_NOTA_SEM_MUNICIPIO]
                if territorial and not filtros.territorial and Dimensao.EAD_POLO in dims
                else []
            ),
            *(
                [_NOTA_REDE]
                if por not in (None, Agrupamento.REDE, Agrupamento.CATEGORIA)
                and filtros.rede is None
                and filtros.categoria is None
                else []
            ),
            *([_NOTA_PUBLICA] if filtros.rede == Rede.PUBLICA else []),
        ],
        linhas=linhas,
    )
