"""Analises aprofundadas de Instituicoes e Cursos (Fase 8): composicoes e tabela de IES.

Mesmas garantias de `api/consultas.py`: SQL montado so com fragmentos fixos, valores de usuario
como parametros nomeados, e as regras transversais de INDICADORES.md aplicadas no servidor.

Unico JOIN entre IES e cursos da API, auditado em 2026-10-06 (docs/data/JOIN_STRATEGY.md):
`cursos` e pre-agregada por `co_ies` ANTES do JOIN, que assim fica 1:1 sobre a tabela de IES
(2.561 linhas antes e depois, 0 orfaos nos dois sentidos, todas as somas de controle
preservadas). Metrica de IES nunca e somada sobre linhas de curso.
"""

from math import ceil
from typing import Any

from api.consultas import (
    _COLUNA_REDE,
    _COM_TERRITORIO,
    _NOTA_PUBLICA,
    _TABELA,
    ANO_CENSO,
    FiltrosConsulta,
    _where,
    info,
    validar,
)
from api.db import BaseAnalitica
from api.erros import ParametroInvalido
from api.indicadores import (
    AREA_CINE,
    CATALOGO,
    EIXOS,
    PERFIS,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_GRAU,
    ROTULO_ORGANIZACAO,
    ROTULO_REDE,
    ROTULO_REGIAO,
    AreaCine,
    Dimensao,
    Eixo,
    Grau,
    Indicador,
    Nivel,
    OrdemInstituicoes,
    Recorte,
    Rede,
    colunas_do_eixo,
)
from api.schemas import (
    Filtros,
    FiltrosComposicao,
    LinhaComposicao,
    LinhaInstituicao,
    RespostaComposicao,
    RespostaInstituicoes,
    TotaisInstituicoes,
)

# Acima dos 353 rotulos CINE existentes: o padrao devolve qualquer composicao inteira.
LIMITE_COMPOSICAO = 400
LIMITE_INSTITUICOES = 100

# (codigo, nome, grupo) por eixo. Pares codigo<->nome CINE medidos 1:1 (11/11 e 353/353), e
# cada rotulo pertence a uma unica area geral.
_COLUNAS_EIXO: dict[Eixo, tuple[str, str, str]] = {
    Eixo.CATEGORIA: ("tp_categoria_administrativa", "tp_categoria_administrativa", "NULL"),
    Eixo.ORGANIZACAO: ("tp_organizacao_academica", "tp_organizacao_academica", "NULL"),
    Eixo.DIMENSAO: ("tp_dimensao", "tp_dimensao", "NULL"),
    Eixo.GRAU: ("tp_grau_academico", "tp_grau_academico", "NULL"),
    Eixo.AREA: ("CAST(co_cine_area_geral AS VARCHAR)", "no_cine_area_geral", "NULL"),
    # co_cine_rotulo vem da origem entre aspas literais ('"0113P01"'): saem so da exibicao.
    Eixo.ROTULO_CINE: (
        "replace(co_cine_rotulo, '\"', '')",
        "no_cine_rotulo",
        "any_value(no_cine_area_geral)",
    ),
}
# Rotulo literal -> slug do enum, para o codigo das linhas dos eixos categoricos.
_SLUG_DO_ROTULO: dict[Eixo, dict[str, str]] = {
    Eixo.REDE: {r: str(s) for s, r in ROTULO_REDE.items()},
    Eixo.CATEGORIA: {r: str(s) for s, r in ROTULO_CATEGORIA.items()},
    Eixo.ORGANIZACAO: {r: str(s) for s, r in ROTULO_ORGANIZACAO.items()},
    Eixo.DIMENSAO: {r: str(s) for s, r in ROTULO_DIMENSAO.items()},
    Eixo.GRAU: {r: str(s) for s, r in ROTULO_GRAU.items()},
}
_EIXOS_CINE = frozenset({Eixo.AREA, Eixo.ROTULO_CINE})

_NOTA_OFERTA_DA_IES = (
    "Cursos, matrículas, ingressantes e concluintes são o total da IES nas dimensões de oferta "
    "selecionadas, em qualquer local de oferta (inclusive polos EAD fora do território filtrado): "
    "o filtro territorial desta lista vale para a sede da IES."
)
_NOTA_SEM_RAZAO = (
    "Docentes e matrículas aparecem lado a lado só como descrição: a razão aluno/docente não é "
    "calculada (IND-Q-03)."
)


# Zeros estruturais (INDICADORES.md, regra 2): o marcador qt_curso so existe nas dimensoes
# presencial e 'somente a nivel Brasil'; matriculas, ingressos e conclusoes, nas outras tres.
_COM_MARCADOR_DE_CURSO = frozenset({Dimensao.PRESENCIAL, Dimensao.EAD_NACIONAL})
_COM_MATRICULA = frozenset({Dimensao.PRESENCIAL, Dimensao.EAD_POLO, Dimensao.EAD_EXTERIOR})
_NOTA_SEM_MARCADOR = (
    "Nenhuma das dimensões selecionadas carrega o marcador de curso: 'Cursos' aparece como 0 por "
    "construção da base, não por ausência de cursos."
)
_NOTA_SEM_MATRICULA = (
    "A dimensão selecionada não registra matrículas, ingressantes nem concluintes: esses zeros "
    "são da estrutura da base, não uma medida."
)
_NOTA_DIMENSAO_PARCIAL = (
    "As dimensões de oferta foram pré-selecionadas ou restritas pelo território: esta repartição "
    "não é a participação da EAD definida em IND-R-04."
)


def nivel_dos_filtros(filtros: FiltrosConsulta) -> Nivel:
    """Nivel do territorio selecionado: o do filtro territorial mais especifico."""
    if filtros.municipio is not None:
        return Nivel.MUNICIPIO
    if filtros.uf is not None:
        return Nivel.UF
    if filtros.regiao is not None:
        return Nivel.REGIAO
    return Nivel.BRASIL


def _filtros_resposta(filtros: FiltrosConsulta, dims: list[Dimensao]) -> dict[str, Any]:
    return {
        "dimensoes": [ROTULO_DIMENSAO[d] for d in dims],
        "rede": ROTULO_REDE[filtros.rede] if filtros.rede else None,
        "categoria": ROTULO_CATEGORIA[filtros.categoria] if filtros.categoria else None,
        "organizacao": ROTULO_ORGANIZACAO[filtros.organizacao] if filtros.organizacao else None,
        "regiao": ROTULO_REGIAO[filtros.regiao] if filtros.regiao else None,
        "uf": str(filtros.uf) if filtros.uf else None,
        "municipio": filtros.municipio,
    }


def _participacao(valor: int, total: int) -> float | None:
    return valor / total * 100 if total else None


def consultar_composicao(
    base: BaseAnalitica,
    ind: Indicador,
    eixo: Eixo,
    recorte: Recorte,
    dimensoes: list[Dimensao],
    filtros: FiltrosConsulta | None = None,
    area: AreaCine | None = None,
    grau: Grau | None = None,
    limite: int = LIMITE_COMPOSICAO,
) -> RespostaComposicao:
    """Decompoe um indicador direto por um eixo categorico, no territorio dos filtros."""
    filtros = filtros or FiltrosConsulta()
    eixo_info = EIXOS[eixo]
    nivel = nivel_dos_filtros(filtros)
    dims = validar(ind, nivel, recorte, dimensoes, filtros)

    if ind.tabela not in eixo_info.tabelas or (
        eixo_info.so_indicadores and ind.slug not in eixo_info.so_indicadores
    ):
        raise ParametroInvalido(
            f"{ind.codigo} não admite composição por '{eixo}' ({eixo_info.nome})."
        )
    if ind.tabela == "ies" and (area is not None or grau is not None):
        raise ParametroInvalido(
            f"{ind.codigo} vem da tabela de IES, que não tem área CINE nem grau acadêmico."
        )
    if nivel == Nivel.MUNICIPIO and (eixo in _EIXOS_CINE or area is not None):
        # Pendencia aberta em INDICADORES.md: piso de supressao para celulas pequenas.
        raise ParametroInvalido(
            "Recortes por área ou rótulo CINE não são servidos no nível municipal: bloqueio "
            "provisório, enquanto o piso de supressão para células pequenas (IND-R-06) não é "
            "definido."
        )
    if nivel == Nivel.MUNICIPIO and eixo in PERFIS:
        # Mesma pendencia: 304 municipios tem de 1 a 9 matriculas (medido em 2026-10-07).
        raise ParametroInvalido(
            "O perfil (sexo, cor ou raça, faixa etária, nacionalidade, procedência escolar) não "
            "é servido no nível municipal: bloqueio provisório por nível, enquanto o piso de supressão "
            "para células pequenas (IND-R-07) não é definido."
        )

    # IND-R-04: tp_dimensao e o proprio eixo e nao pode vir pre-filtrada; e o indicador nao se
    # aplica a metricas que, no territorio, so existem em uma dimensao (vagas, inscricoes, cursos).
    admitidas = set(Dimensao) if nivel == Nivel.BRASIL else set(ind.dimensoes_territoriais)
    dimensao_parcial = eixo == Eixo.DIMENSAO and (set(dims) != admitidas or len(admitidas) < 2)

    tabela = _TABELA[ind.tabela]
    condicoes, params = _where(ind, dims, filtros)
    if ind.tabela == "cursos" and filtros.territorial:
        condicoes.append(_COM_TERRITORIO)
    if area is not None:
        condicoes.append("co_cine_area_geral = $area")
        params["area"] = AREA_CINE[area][0]
    if grau is not None:
        condicoes.append("tp_grau_academico = $grau")
        params["grau"] = ROTULO_GRAU[grau]

    por_colunas = colunas_do_eixo(eixo, ind.slug)
    if por_colunas is not None:
        # Decomposicao por colunas que particionam exatamente a coluna-total (titulacao no grain
        # da IES; perfil e tipo de vaga do ingresso no grain de cursos), na ordem natural.
        somas = ", ".join(f"CAST(coalesce(SUM({col}), 0) AS BIGINT)" for _, _, col in por_colunas)
        sql = f"SELECT {somas} FROM {tabela} WHERE {' AND '.join(condicoes)}"
        valores = [int(v) for v in base.consultar(sql, params)[0]]
        total = sum(valores)
        linhas = [
            LinhaComposicao(
                codigo=slug, nome=nome, valor=valor, participacao=_participacao(valor, total)
            )
            for (slug, nome, _), valor in zip(por_colunas, valores, strict=True)
        ][:limite]
        categorias = len(por_colunas)
    else:
        if eixo == Eixo.REDE:
            coluna = _COLUNA_REDE[ind.tabela]
            cod, nome, grupo = coluna, coluna, "NULL"
        else:
            cod, nome, grupo = _COLUNAS_EIXO[eixo]
        sql = f"""
            WITH agg AS (
                SELECT {cod} AS codigo, any_value({nome}) AS nome, {grupo} AS grupo,
                       CAST(coalesce({ind.expressao}, 0) AS BIGINT) AS valor
                FROM {tabela}
                WHERE {" AND ".join(condicoes)}
                GROUP BY 1
            )
            SELECT codigo, nome, grupo, valor,
                   CAST(SUM(valor) OVER () AS BIGINT), COUNT(*) OVER ()
            FROM agg
            ORDER BY valor DESC, codigo
            LIMIT $limite
        """
        params["limite"] = limite
        rows = base.consultar(sql, params)
        total = int(rows[0][4]) if rows else 0
        categorias = int(rows[0][5]) if rows else 0
        slugs = _SLUG_DO_ROTULO.get(eixo, {})
        linhas = [
            LinhaComposicao(
                codigo=slugs.get(r[0], r[0]),
                nome=r[1],
                grupo=r[2],
                valor=r[3],
                participacao=_participacao(int(r[3]), total),
            )
            for r in rows
        ]

    return RespostaComposicao(
        indicador=info(ind),
        eixo=eixo,
        eixo_nome=eixo_info.nome,
        ficha=None if dimensao_parcial else eixo_info.ficha,
        ano_censo=ANO_CENSO,
        recorte=ind.recorte,
        nivel=nivel,
        filtros=FiltrosComposicao(
            **_filtros_resposta(filtros, dims),
            area=AREA_CINE[area][1] if area else None,
            grau=ROTULO_GRAU[grau] if grau else None,
        ),
        total=total,
        categorias=categorias,
        truncado=categorias > len(linhas),
        notas=[
            *eixo_info.notas,
            *([_NOTA_DIMENSAO_PARCIAL] if dimensao_parcial else []),
            *([_NOTA_PUBLICA] if filtros.rede == Rede.PUBLICA else []),
        ],
        linhas=linhas,
    )


_ORDEM_SQL: dict[OrdemInstituicoes, str] = {
    OrdemInstituicoes.MATRICULAS: "a.matriculas DESC NULLS LAST",
    OrdemInstituicoes.CURSOS: "a.cursos DESC NULLS LAST",
    OrdemInstituicoes.INGRESSANTES: "a.ingressantes DESC NULLS LAST",
    OrdemInstituicoes.CONCLUINTES: "a.concluintes DESC NULLS LAST",
    OrdemInstituicoes.DOCENTES: "s.qt_doc_total DESC",
    OrdemInstituicoes.TECNICOS: "s.qt_tec_total DESC",
    OrdemInstituicoes.NOME: "lower(strip_accents(s.no_ies)) ASC",
}


def listar_instituicoes(
    base: BaseAnalitica,
    dimensoes: list[Dimensao],
    filtros: FiltrosConsulta | None = None,
    ordem: OrdemInstituicoes = OrdemInstituicoes.MATRICULAS,
    limite: int = 25,
    pagina: int = 1,
) -> RespostaInstituicoes:
    """Tabela detalhada de IES: atributos e pessoal (tabela de IES) + oferta (cursos agregada).

    Os filtros territoriais e institucionais selecionam IES pela sede; as dimensoes de oferta
    so delimitam as metricas de curso.
    """
    filtros = filtros or FiltrosConsulta()
    ies = CATALOGO["ies"]
    validar(ies, nivel_dos_filtros(filtros), Recorte.SEDE, [], filtros)
    dims = sorted(set(dimensoes))
    if not dims:
        raise ParametroInvalido(
            "As métricas de curso exigem 'dimensao' declarada (tp_dimensao não tem padrão)."
        )

    condicoes, params = _where(ies, [], filtros)
    params["dims"] = [ROTULO_DIMENSAO[d] for d in dims]
    cte = f"""
        WITH s AS (
            SELECT * FROM {_TABELA["ies"]} WHERE {" AND ".join(condicoes)}
        ),
        a AS (
            SELECT co_ies,
                   CAST(SUM(qt_curso) AS BIGINT) AS cursos,
                   CAST(SUM(qt_mat) AS BIGINT) AS matriculas,
                   CAST(SUM(qt_ing) AS BIGINT) AS ingressantes,
                   CAST(SUM(qt_conc) AS BIGINT) AS concluintes
            FROM {_TABELA["cursos"]}
            WHERE nu_ano_censo = $ano AND list_contains($dims, tp_dimensao)
            GROUP BY co_ies
        )
    """
    juncao = "FROM s LEFT JOIN a ON a.co_ies = s.co_ies"

    t = base.consultar(
        f"""{cte}
        SELECT COUNT(*), COUNT(a.co_ies),
               coalesce(SUM(s.qt_doc_total), 0), coalesce(SUM(s.qt_tec_total), 0),
               coalesce(SUM(a.cursos), 0), coalesce(SUM(a.matriculas), 0),
               coalesce(SUM(a.ingressantes), 0), coalesce(SUM(a.concluintes), 0)
        {juncao}""",
        params,
    )[0]
    totais = TotaisInstituicoes(
        ies=int(t[0]),
        ies_com_oferta=int(t[1]),
        docentes=int(t[2]),
        tecnicos=int(t[3]),
        # Com territorio (sede) filtrado, a soma da oferta das IES nao e um numero do territorio.
        cursos=None if filtros.territorial else int(t[4]),
        matriculas=None if filtros.territorial else int(t[5]),
        ingressantes=None if filtros.territorial else int(t[6]),
        concluintes=None if filtros.territorial else int(t[7]),
    )

    rows = base.consultar(
        f"""{cte}
        SELECT s.co_ies, s.no_ies, nullif(trim(s.sg_ies), ''), s.sg_uf_ies,
               s.co_municipio_ies, s.no_municipio_ies, s.ds_rede,
               s.tp_categoria_administrativa, s.tp_organizacao_academica,
               CAST(s.qt_doc_total AS BIGINT), CAST(s.qt_tec_total AS BIGINT),
               a.cursos, a.matriculas, a.ingressantes, a.concluintes
        {juncao}
        ORDER BY {_ORDEM_SQL[ordem]}, s.co_ies
        LIMIT $limite OFFSET $deslocamento""",
        {**params, "limite": limite, "deslocamento": (pagina - 1) * limite},
    )

    return RespostaInstituicoes(
        ano_censo=ANO_CENSO,
        recorte=Recorte.SEDE,
        filtros=Filtros(**_filtros_resposta(filtros, dims)),
        ordem=ordem,
        pagina=pagina,
        limite=limite,
        paginas=ceil(totais.ies / limite),
        totais=totais,
        notas=[
            _NOTA_OFERTA_DA_IES,
            _NOTA_SEM_RAZAO,
            *([] if _COM_MARCADOR_DE_CURSO & set(dims) else [_NOTA_SEM_MARCADOR]),
            *([] if _COM_MATRICULA & set(dims) else [_NOTA_SEM_MATRICULA]),
            *([_NOTA_PUBLICA] if filtros.rede == Rede.PUBLICA else []),
        ],
        linhas=[
            LinhaInstituicao(
                co_ies=r[0],
                nome=r[1],
                sigla=r[2],
                uf=r[3],
                municipio_codigo=r[4],
                municipio=r[5],
                rede=r[6],
                categoria=r[7],
                organizacao=r[8],
                docentes=r[9],
                tecnicos=r[10],
                cursos=r[11],
                matriculas=r[12],
                ingressantes=r[13],
                concluintes=r[14],
            )
            for r in rows
        ],
    )
