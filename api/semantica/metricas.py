"""Metricas da camada semantica: as fichas de INDICADORES.md, e so elas.

Expressao, recorte, dimensoes territoriais e limitacoes das diretas (IND-D-01 a D-09) e das
razoes (IND-R-01, R-08 a R-11) sao LIDAS de `api/indicadores.py`; nada e redigitado. O que a API
nao tem em catalogo (IND-D-10, D-11 e as composicoes IND-R-03 a R-07 e R-12) vem das fichas.

Fora desta fase, de proposito: IND-R-02 (cobertura territorial) e IND-R-13 (concentracao).
"""

from api.indicadores import (
    CATALOGO,
    DIMENSOES_COM_TERRITORIO,
    EIXOS,
    MATRICULAS_POR_HABITANTE,
    PERFIS,
    PREFIXO_BASE,
    RAZOES,
    ROTULO_REDE,
    TITULACOES,
    Dimensao,
    Eixo,
    Indicador,
    Nivel,
    Recorte,
    Rede,
)
from api.semantica.dimensoes import DIMENSOES, alias, prop, ver
from api.semantica.modelos import AgregacaoProibida, Metrica, Razao, RefColuna, Sinonimo

_GRAIN: dict[str, str] = {
    "ies": "IES (uma linha por instituição; atribuída ao município de sede)",
    "cursos": "curso × município de oferta × dimensão de oferta (não é uma linha por curso)",
}
_NIVEIS = tuple(Nivel)
_SEM_MUNICIPIO = (Nivel.BRASIL, Nivel.REGIAO, Nivel.UF)
_VIRTUAIS = ("recorte", "nivel_territorial")
_TERRITORIAIS = ("regiao", "uf", "municipio")
_ORDEM_DIMENSAO = tuple(Dimensao)


def _ordenadas(dims: frozenset[Dimensao] | set[Dimensao]) -> tuple[Dimensao, ...]:
    return tuple(d for d in _ORDEM_DIMENSAO if d in dims)


def _obrigatorias(entidade: str) -> tuple[str, ...]:
    return ("recorte", "dimensao") if entidade == "cursos" else ("recorte",)


def _permitidas(entidade: str, metrica: str, fora: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """Dimensoes que existem na entidade e nao sao restritas a outra metrica."""
    ids = list(_VIRTUAIS)
    for d in DIMENSOES:
        if d.tipo == "virtual" or d.id in fora or entidade not in d.entidades:
            continue
        if d.so_metricas and metrica not in d.so_metricas:
            continue
        ids.append(d.id)
    return tuple(ids)


def _ref(entidade: str, coluna: str) -> RefColuna:
    return RefColuna(entidade=entidade, coluna=coluna)


def _proibida(expressao: str, motivo: str) -> AgregacaoProibida:
    return AgregacaoProibida(expressao=expressao, motivo=motivo)


_P_LINHAS = _proibida(
    "COUNT(*)",
    "Conta linhas curso × município × dimensão (720.349), 93,5% delas polos EAD: não é curso, "
    "matrícula nem instituição.",
)
_P_MEDIA = _proibida(
    "AVG(...)",
    "Média de linhas pondera cada polo como uma unidade; a métrica é soma no recorte declarado.",
)
_P_JOIN = _proibida(
    "SUM(...) após JOIN com cursos",
    "O valor da IES se repete em cada linha de curso (até 1.197 por curso EAD) e o total infla "
    "em ordens de grandeza: agregar na tabela de IES.",
)

# Onde a soma nao e zero por construcao da base (INDICADORES.md, regra transversal 2).
_COM_FLUXO = (Dimensao.PRESENCIAL, Dimensao.EAD_POLO, Dimensao.EAD_EXTERIOR)
_COM_MARCADOR = (Dimensao.PRESENCIAL, Dimensao.EAD_NACIONAL)
_COM_VAGA = (Dimensao.PRESENCIAL, Dimensao.EAD_POLO, Dimensao.EAD_NACIONAL)

_FICHAS = "INDICADORES.md"
_CATALOGO = "api/indicadores.py (CATALOGO)"


def _direta(
    ind: Indicador,
    *,
    descricao: str,
    colunas: tuple[str, ...],
    controle: int,
    com_registro: tuple[Dimensao, ...] = (),
    proibidas: tuple[AgregacaoProibida, ...],
    sinonimos: tuple[Sinonimo, ...] = (),
    limitacoes: tuple[str, ...] = (),
    fora: frozenset[str] = frozenset(),
) -> Metrica:
    de_cursos = ind.tabela == "cursos"
    return Metrica(
        id=ind.slug,
        ficha=ind.codigo,
        nome=ind.nome,
        descricao=descricao,
        tipo="direta",
        entidade=ind.tabela,
        grain=_GRAIN[ind.tabela],
        expressao=ind.expressao,
        colunas=tuple(_ref(ind.tabela, c) for c in colunas),
        unidade=ind.unidade,
        recortes=(ind.recorte,),
        exige_dimensao_oferta=ind.exige_dimensao,
        dimensoes_oferta=_ORDEM_DIMENSAO if de_cursos else (),
        dimensoes_oferta_territoriais=_ordenadas(ind.dimensoes_territoriais),
        dimensoes_oferta_com_registro=com_registro,
        dimensoes_obrigatorias=_obrigatorias(ind.tabela),
        dimensoes_permitidas=_permitidas(ind.tabela, ind.slug, fora),
        niveis=_NIVEIS,
        agregacoes_permitidas=(ind.expressao,),
        agregacoes_proibidas=proibidas,
        limitacoes=(*ind.limitacoes, *limitacoes),
        sinonimos=sinonimos,
        controle_nacional=controle,
        origem_definicao=_CATALOGO,
        proveniencia=f"{_FICHAS} {ind.codigo}; {_CATALOGO}",
    )


_DIRETAS: tuple[Metrica, ...] = (
    _direta(
        CATALOGO["ies"],
        descricao="Número de IES com registro no Censo 2024, contadas no município de sede.",
        colunas=("co_ies",),
        controle=2_561,
        proibidas=(
            _proibida(
                "COUNT(*) após JOIN com cursos",
                "Depois do JOIN cada IES vira uma linha por curso × município × dimensão.",
            ),
            _proibida(
                "COUNT(DISTINCT no_ies) ou sg_ies",
                "no_ies tem 14 homônimos e sg_ies está vazia em 459 linhas: a IES é co_ies.",
            ),
        ),
        sinonimos=ver("IES", "instituição de ensino superior", "instituição"),
    ),
    _direta(
        CATALOGO["cursos"],
        descricao=(
            "Cursos contabilizados pela base, que marca exatamente uma linha por curso "
            "contabilizado (45.776). Não é 'todos os cursos com registro' (46.150)."
        ),
        colunas=("qt_curso",),
        controle=45_776,
        com_registro=_COM_MARCADOR,
        proibidas=(
            _P_LINHAS,
            _proibida(
                "COUNT(DISTINCT co_curso)",
                "46.150: outro conceito ('cursos com registro no Censo'), que inclui os 374 "
                "Programas básicos (ABI) sem marcador. Não é servido e não substitui este.",
            ),
        ),
        sinonimos=ver("número de cursos", "cursos contabilizados"),
        limitacoes=(
            "Os 374 cursos sem marcador são os 'Programas básicos' (área CINE 0): têm 61.053 "
            "matrículas e ficam fora da contagem. A regra oficial do INEP é A confirmar.",
            "A contagem de cursos EAD (11.297) está na dimensão 'somente nível Brasil', sem "
            "município, UF nem região.",
        ),
    ),
    _direta(
        CATALOGO["matriculas"],
        descricao="Vínculos de matrícula em cursos de graduação informados ao Censo 2024.",
        colunas=("qt_mat",),
        controle=10_227_266,
        com_registro=_COM_FLUXO,
        proibidas=(_P_LINHAS, _P_MEDIA),
        sinonimos=alias(
            "A resposta fala em matrículas (vínculos), nunca em número de alunos, estudantes ou pessoas.",
            "aluno",
            "estudante",
            "matriculado",
            "universitário",
        ),
        limitacoes=(
            "O filtro territorial deixa de fora 2.580 matrículas (2.539 do exterior e 41 de "
            "polo sem município): territorializável = 10.224.686.",
        ),
    ),
    _direta(
        CATALOGO["ingressantes"],
        descricao="Ingressos em cursos de graduação no ano de referência.",
        colunas=("qt_ing",),
        controle=5_010_613,
        com_registro=_COM_FLUXO,
        proibidas=(_P_LINHAS, _P_MEDIA),
        sinonimos=(
            *ver("ingresso"),
            *alias(
                "A resposta fala em ingressantes (ingressos no ano), não em pessoas distintas.",
                "calouro",
            ),
        ),
    ),
    _direta(
        CATALOGO["concluintes"],
        descricao="Conclusões de curso de graduação registradas no ano de referência.",
        colunas=("qt_conc",),
        controle=1_333_988,
        com_registro=_COM_FLUXO,
        proibidas=(_P_LINHAS, _P_MEDIA),
        sinonimos=alias(
            "A resposta fala em concluintes (conclusões no ano), não em pessoas distintas.",
            "formado",
        ),
    ),
    _direta(
        CATALOGO["vagas"],
        descricao="Vagas oferecidas em processos seletivos para cursos de graduação.",
        colunas=("qt_vg_total",),
        controle=23_665_419,
        com_registro=_COM_VAGA,
        proibidas=(_P_LINHAS, _P_MEDIA),
        sinonimos=ver("vaga"),
        limitacoes=(
            "Nas linhas de polo EAD com município, qt_vg_total é zero em todas; as 6.925 vagas "
            "dessa dimensão estão nas 9 linhas sem município.",
        ),
    ),
    _direta(
        CATALOGO["inscricoes"],
        descricao="Inscrições registradas em processos seletivos (não são pessoas).",
        colunas=("qt_inscrito_total",),
        controle=15_723_085,
        com_registro=_COM_VAGA,
        proibidas=(_P_LINHAS, _P_MEDIA),
        sinonimos=(
            *ver("inscrição", "inscrito"),
            *alias(
                "A resposta fala em inscrições em processo seletivo, nunca em candidatos ou pessoas.",
                "candidato",
            ),
        ),
    ),
    _direta(
        CATALOGO["docentes"],
        descricao="Docentes em exercício informados pelas IES no Censo 2024.",
        colunas=("qt_doc_total",),
        controle=374_501,
        proibidas=(
            _P_JOIN,
            _proibida(
                "SUM(qt_doc_total) + SUM(qt_doc_exe)",
                "As duas colunas são a mesma medida: somá-las duplica o total.",
            ),
        ),
        sinonimos=(
            # 'universitario' aqui e adjetivo de docente, nao a medida de matriculas.
            *ver("docente", "docente universitário"),
            *alias(
                "A resposta fala em docentes em exercício, no grain da IES e atribuídos ao município de sede.",
                "professor",
                "professor universitário",
            ),
        ),
        limitacoes=(
            "Não existe grain de docente nem vínculo docente-curso: não há docentes por curso, "
            "por área nem por modalidade.",
        ),
    ),
    _direta(
        CATALOGO["tecnicos"],
        descricao="Funcionários técnico-administrativos informados pelas IES.",
        colunas=("qt_tec_total",),
        controle=350_752,
        proibidas=(_P_JOIN,),
        sinonimos=ver("funcionário", "técnico-administrativo"),
    ),
)

# IND-D-10 e IND-D-11: contagens de territorio; nao existem no grain do proprio municipio.
_D10 = Metrica(
    id="municipios_com_sede",
    ficha="IND-D-10",
    nome="Unidades territoriais com sede de IES",
    descricao="Número de municípios e equivalentes que sediam ao menos uma IES.",
    tipo="direta",
    entidade="ies",
    grain=_GRAIN["ies"],
    expressao="COUNT(DISTINCT co_municipio_ies)",
    colunas=(_ref("ies", "co_municipio_ies"),),
    unidade="unidades territoriais",
    recortes=(Recorte.SEDE,),
    exige_dimensao_oferta=False,
    dimensoes_obrigatorias=("recorte",),
    dimensoes_permitidas=(*_VIRTUAIS, "regiao", "uf", "rede", "categoria", "organizacao"),
    niveis=_SEM_MUNICIPIO,
    agregacoes_permitidas=("COUNT(DISTINCT co_municipio_ies)",),
    agregacoes_proibidas=(
        _proibida("COUNT(*)", "Conta instituições (IND-D-01), não territórios."),
    ),
    limitacoes=(
        "Contagem de territórios, não de instituições: não comparar com IND-D-01.",
        "Não comparar com IND-D-11 sem sinalizar: são recortes diferentes (IND-Q-06).",
        "Ausência de linha é ausência de sede, não zero registrado.",
    ),
    sinonimos=prop("municípios com sede de IES", "municípios com IES"),
    controle_nacional=698,
    origem_definicao=f"{_FICHAS} (ficha; fora do catálogo da API)",
    proveniencia=f"{_FICHAS} IND-D-10",
)

_D11 = Metrica(
    id="municipios_com_oferta",
    ficha="IND-D-11",
    nome="Unidades territoriais com oferta de curso",
    descricao=(
        "Número de municípios e equivalentes onde há ao menos um curso presencial ou um polo EAD."
    ),
    tipo="direta",
    entidade="cursos",
    grain=_GRAIN["cursos"],
    expressao="COUNT(DISTINCT co_municipio)",
    filtro_obrigatorio="regexp_full_match(co_municipio, '[0-9]{7}')",
    colunas=(_ref("cursos", "co_municipio"),),
    unidade="unidades territoriais",
    recortes=(Recorte.OFERTA,),
    exige_dimensao_oferta=True,
    dimensoes_oferta=_ordenadas(DIMENSOES_COM_TERRITORIO),
    dimensoes_oferta_territoriais=_ordenadas(DIMENSOES_COM_TERRITORIO),
    dimensoes_oferta_com_registro=_ordenadas(DIMENSOES_COM_TERRITORIO),
    dimensoes_obrigatorias=("recorte", "dimensao"),
    dimensoes_permitidas=(*_VIRTUAIS, "regiao", "uf", "dimensao", "rede", "grau", "area"),
    niveis=_SEM_MUNICIPIO,
    agregacoes_permitidas=("COUNT(DISTINCT co_municipio)",),
    agregacoes_proibidas=(
        _proibida(
            "COUNT(DISTINCT co_municipio) sem o filtro de 7 dígitos",
            "Conta 'Cursos a distância' como se fosse um município (3.552 em vez de 3.551).",
        ),
    ),
    limitacoes=(
        "Equipara campus físico a polo EAD: um município com um único polo conta igual a um "
        "com uma universidade federal. Não é proxy de infraestrutura acadêmica.",
        "Não comparar com IND-D-10 sem sinalizar: são recortes diferentes (IND-Q-06).",
        "Presencial e polo EAD dão respostas muito diferentes (1.121 e 3.524 unidades).",
    ),
    sinonimos=prop("municípios com oferta", "municípios com curso"),
    controle_nacional=3_551,
    origem_definicao=f"{_FICHAS} (ficha; fora do catálogo da API)",
    proveniencia=f"{_FICHAS} IND-D-11",
)

# --- razoes ---------------------------------------------------------------------------------------

_P_MEDIA_DE_RAZOES = _proibida(
    "AVG das razões de um nível inferior",
    "A razão de um nível é a razão das somas, não a média das razões: numerador e denominador "
    "são reagregados em cada nível.",
)
_FORA_DAS_RAZOES = frozenset({"gratuito", "comunitaria", "confessional", "capital", "rotulo_cine"})
_FORA_DAS_RAZOES |= frozenset(str(e) for e in PERFIS) | {str(Eixo.TIPO_INGRESSO)}

_R01 = Metrica(
    id=MATRICULAS_POR_HABITANTE.slug,
    ficha=MATRICULAS_POR_HABITANTE.codigo,
    nome=MATRICULAS_POR_HABITANTE.nome,
    descricao=(
        "Matrículas (local de oferta) divididas pela população residente estimada pelo IBGE "
        "para 2024, por 100 mil habitantes."
    ),
    tipo="razao",
    entidade="cursos",
    grain="unidade territorial (numerador pré-agregado por município antes do JOIN)",
    expressao="SUM(qt_mat) / NULLIF(SUM(populacao), 0) * 100000",
    colunas=(_ref("cursos", "qt_mat"), _ref("populacao", "populacao")),
    unidade=MATRICULAS_POR_HABITANTE.unidade,
    recortes=(MATRICULAS_POR_HABITANTE.recorte,),
    exige_dimensao_oferta=True,
    dimensoes_oferta=_ordenadas(MATRICULAS_POR_HABITANTE.dimensoes_territoriais),
    dimensoes_oferta_territoriais=_ordenadas(MATRICULAS_POR_HABITANTE.dimensoes_territoriais),
    dimensoes_oferta_com_registro=_ordenadas(MATRICULAS_POR_HABITANTE.dimensoes_territoriais),
    dimensoes_obrigatorias=("recorte", "dimensao"),
    dimensoes_permitidas=(
        *_VIRTUAIS,
        *_TERRITORIAIS,
        "dimensao",
        "rede",
        "categoria",
        "organizacao",
        "grau",
        "area",
    ),
    niveis=_NIVEIS,
    agregacoes_permitidas=("razão das somas, com a população reagregada em cada nível",),
    agregacoes_proibidas=(
        _P_MEDIA_DE_RAZOES,
        _proibida(
            "JOIN direto de cursos com a população",
            "O Censo usa código de 7 dígitos e a população de 6: o JOIN direto devolve zero "
            "linhas em silêncio. `municipio` é a tabela-ponte.",
        ),
    ),
    razoes=(
        Razao(
            numerador=_ref("cursos", "qt_mat"),
            denominador=_ref("populacao", "populacao"),
            nome_numerador="Matrículas",
            nome_denominador="População estimada (IBGE, 2024)",
            fator=100_000,
        ),
    ),
    bases=("matriculas",),
    relacionamentos=("cursos_municipio", "municipio_populacao"),
    limitacoes=(
        *MATRICULAS_POR_HABITANTE.limitacoes,
        "Filtro institucional (rede, categoria…) restringe só o numerador; o denominador é "
        "sempre a população total.",
    ),
    sinonimos=(*ver("matrículas por habitante"), *prop("matrículas per capita")),
    origem_definicao="api/indicadores.py (MATRICULAS_POR_HABITANTE)",
    proveniencia=f"{_FICHAS} IND-R-01",
)

_SIN_RAZAO: dict[str, tuple[Sinonimo, ...]] = {
    "financiamento": ver("financiamento estudantil", "financiamento"),
    "reserva_vagas": (
        *ver("reserva de vagas"),
        *alias(
            "A resposta fala em reserva de vagas, só como participação agregada (IND-R-09); subtipos de cota não são servidos.",
            "cota",
            "cotista",
        ),
    ),
    "ingressantes_por_vaga": ver("ingressantes por vaga", "ingressos por vaga"),
    "inscricoes_por_vaga": ver("inscrições por vaga", "inscritos por vaga"),
}
_BASE_DA_COLUNA = {coluna: base for base, coluna in PREFIXO_BASE.items()}


def _de_razao(slug: str) -> Metrica:
    d = RAZOES[slug]
    ind = d.ind
    if d.usa_base:
        bases = tuple(PREFIXO_BASE)
        razoes = tuple(
            Razao(
                base=base,
                numerador=_ref("cursos", f"{prefixo}_{d.numerador}"),
                denominador=_ref("cursos", prefixo),
                nome_numerador=f"{CATALOGO[base].nome} {d.nome_numerador}",
                nome_denominador=CATALOGO[base].nome,
                fator=100 if d.percentual else 1,
            )
            for base, prefixo in PREFIXO_BASE.items()
        )
    else:
        bases = (_BASE_DA_COLUNA.get(d.numerador, "inscricoes"), "vagas")
        razoes = (
            Razao(
                numerador=_ref("cursos", d.numerador),
                denominador=_ref("cursos", d.denominador),
                nome_numerador=d.nome_numerador,
                nome_denominador=d.nome_denominador,
                fator=100 if d.percentual else 1,
            ),
        )
    return Metrica(
        id=ind.slug,
        ficha=ind.codigo,
        nome=ind.nome,
        descricao=f"{razoes[0].nome_numerador} ÷ {razoes[0].nome_denominador}, no mesmo recorte.",
        tipo="razao",
        entidade="cursos",
        grain=_GRAIN["cursos"],
        expressao=razoes[0].expressao,
        colunas=tuple(
            sorted(
                {r.numerador for r in razoes} | {r.denominador for r in razoes},
                key=lambda r: r.coluna,
            )
        ),
        unidade=ind.unidade,
        recortes=(ind.recorte,),
        exige_dimensao_oferta=True,
        dimensoes_oferta=_ordenadas(d.dimensoes),
        dimensoes_oferta_territoriais=_ordenadas(ind.dimensoes_territoriais),
        dimensoes_oferta_com_registro=_ordenadas(d.dimensoes),
        dimensao_oferta_unica=d.dimensao_unica,
        dimensoes_obrigatorias=("recorte", "dimensao"),
        dimensoes_permitidas=_permitidas("cursos", ind.slug, _FORA_DAS_RAZOES),
        niveis=_NIVEIS,
        niveis_bloqueados=() if d.municipal else (Nivel.MUNICIPIO,),
        agregacoes_permitidas=("razão das somas no recorte declarado",),
        agregacoes_proibidas=(_P_MEDIA_DE_RAZOES,),
        razoes=razoes,
        bases=bases,
        limitacoes=(
            *ind.limitacoes,
            *(
                ()
                if d.municipal
                else (
                    "Bloqueio provisório: não servido no nível municipal enquanto o piso de "
                    "supressão para células pequenas não é definido.",
                )
            ),
        ),
        sinonimos=_SIN_RAZAO[slug],
        origem_definicao="api/indicadores.py (RAZOES)",
        proveniencia=f"{_FICHAS} {ind.codigo}",
    )


# --- composicoes ----------------------------------------------------------------------------------

_FLUXO = tuple(PREFIXO_BASE)  # matriculas, ingressantes, concluintes
_P_CONTAR_LINHAS = _proibida(
    "contagem de linhas por categoria",
    "A distribuição por linhas não é a distribuição pela métrica: sempre ponderar pela soma.",
)


def _composicao(
    id_: str,
    ficha: str,
    nome: str,
    descricao: str,
    expressao: str,
    eixos: tuple[str, ...],
    bases: tuple[str, ...],
    entidade: str = "cursos",
    limitacoes: tuple[str, ...] = (),
    sinonimos: tuple[Sinonimo, ...] = (),
    bloqueado_no_municipio: bool = False,
    recortes: tuple[Recorte, ...] = (Recorte.OFERTA,),
    fora: frozenset[str] = frozenset(),
) -> Metrica:
    de_cursos = entidade == "cursos"
    permitidas = tuple(
        dict.fromkeys(
            (
                *_VIRTUAIS,
                *(
                    d
                    for d in _permitidas(entidade, bases[0], _FORA_DAS_RAZOES - set(eixos))
                    if d not in fora
                ),
            )
        )
    )
    return Metrica(
        id=id_,
        ficha=ficha,
        nome=nome,
        descricao=descricao,
        tipo="composicao",
        entidade=entidade,
        grain=_GRAIN[entidade],
        expressao=expressao,
        unidade="%",
        recortes=recortes,
        exige_dimensao_oferta=de_cursos,
        dimensoes_oferta=_ORDEM_DIMENSAO if de_cursos else (),
        dimensoes_oferta_territoriais=_ordenadas(DIMENSOES_COM_TERRITORIO) if de_cursos else (),
        dimensoes_obrigatorias=_obrigatorias(entidade),
        dimensoes_permitidas=permitidas,
        niveis=_NIVEIS,
        niveis_bloqueados=(Nivel.MUNICIPIO,) if bloqueado_no_municipio else (),
        agregacoes_permitidas=("parcela da soma da métrica-base sobre a soma do recorte",),
        agregacoes_proibidas=(_P_CONTAR_LINHAS,),
        bases=bases,
        eixos=eixos,
        limitacoes=limitacoes,
        sinonimos=sinonimos,
        origem_definicao=f"{_FICHAS} (ficha; a API serve como composição ou comparação)",
        proveniencia=f"{_FICHAS} {ficha}",
    )


_PRIVADA = ROTULO_REDE[Rede.PRIVADA]

_COMPOSICOES: tuple[Metrica, ...] = (
    _composicao(
        "participacao_privada",
        "IND-R-03",
        "Participação da rede privada",
        "Proporção de uma métrica (matrículas, por padrão) atribuída a IES da rede privada.",
        f"SUM(qt_mat) FILTER (WHERE tp_rede = '{_PRIVADA}') / NULLIF(SUM(qt_mat), 0) * 100",
        (str(Eixo.REDE),),
        ("matriculas",),
        limitacoes=(
            "O complemento é a rede Pública, que inclui as 28 IES de categoria Especial.",
            "Descreve a rede da IES ofertante, não o financiamento do estudante (IND-R-08).",
        ),
    ),
    _composicao(
        "participacao_ead",
        "IND-R-04",
        "Participação da educação a distância",
        "Proporção de uma métrica atribuída a cursos a distância, medida pela dimensão de oferta.",
        "SUM(qt_mat) nas dimensões de EAD / NULLIF(SUM(qt_mat), 0) * 100",
        (str(Eixo.DIMENSAO),),
        ("matriculas",),
        limitacoes=(
            *EIXOS[Eixo.DIMENSAO].notas,
            "tp_dimensao é o próprio eixo: não pode vir pré-filtrada, e cada publicação declara "
            "as dimensões incluídas (com o exterior, 50,74%; só polo, 50,72%).",
            "Não se aplica a vagas e inscrições em recorte territorial.",
        ),
        sinonimos=ver("participação da EAD"),
    ),
    _composicao(
        "composicao_grau",
        "IND-R-05",
        "Composição por grau acadêmico",
        "Distribuição percentual de uma métrica entre bacharelado, licenciatura, tecnológico "
        "e 'não aplicável'.",
        "SUM(qt_mat) por tp_grau_academico / NULLIF(SUM(qt_mat) do recorte, 0) * 100",
        (str(Eixo.GRAU),),
        ("matriculas", "cursos", "ingressantes", "concluintes"),
        limitacoes=EIXOS[Eixo.GRAU].notas,
    ),
    _composicao(
        "composicao_area",
        "IND-R-06",
        "Composição por área do conhecimento (CINE)",
        "Distribuição percentual de uma métrica entre as áreas da classificação CINE.",
        "SUM(qt_mat) por co_cine_area_geral / NULLIF(SUM(qt_mat) do recorte, 0) * 100",
        (str(Eixo.AREA), str(Eixo.ROTULO_CINE)),
        ("matriculas", "cursos", "ingressantes", "concluintes"),
        limitacoes=(
            *EIXOS[Eixo.AREA].notas,
            "Bloqueio provisório: recortes CINE não são servidos no nível municipal.",
        ),
        bloqueado_no_municipio=True,
    ),
    _composicao(
        "perfil",
        "IND-R-07",
        "Perfil das matrículas, ingressos e conclusões",
        "Distribuição percentual de matrículas, ingressos ou conclusões por sexo, cor ou raça, "
        "faixa etária, nacionalidade ou procedência escolar.",
        "SUM(subcoluna do perfil) / NULLIF(SUM(coluna-total), 0) * 100",
        tuple(str(e) for e in PERFIS),
        _FLUXO,
        limitacoes=(
            "'Não declarada' e 'não informada' são ausência de informação: aparecem no "
            "resultado e nunca saem do denominador.",
            "Turno não pertence a este indicador: só existe no presencial.",
            "Bloqueio provisório: o perfil não é servido no nível municipal.",
        ),
        sinonimos=ver("perfil"),
        bloqueado_no_municipio=True,
    ),
    _composicao(
        "titulacao_docente",
        "IND-R-12",
        "Titulação do corpo docente",
        "Distribuição percentual dos docentes em exercício por maior titulação.",
        f"SUM({TITULACOES[-1][2]}) / NULLIF(SUM(qt_doc_total), 0) * 100 (análogo para as demais)",
        (str(Eixo.TITULACAO),),
        ("docentes",),
        entidade="ies",
        recortes=(Recorte.SEDE,),
        limitacoes=(
            *EIXOS[Eixo.TITULACAO].notas,
            "Agregado no grain da IES: nunca calcular após JOIN com cursos.",
            "Três IES declaram zero docentes: denominador zero é célula não aplicável.",
        ),
    ),
)

METRICAS: tuple[Metrica, ...] = (
    *_DIRETAS,
    _D10,
    _D11,
    _R01,
    *(_de_razao(slug) for slug in RAZOES),
    *_COMPOSICOES,
)
