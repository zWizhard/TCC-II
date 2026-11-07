"""Dimensoes da camada semantica.

Os valores vem de `api/indicadores.py` (enums e rotulos ja conferidos contra a base em teste);
aqui so se acrescenta o que la nao existe — a coluna e o tipo do literal em cada tabela,
sinonimos e limitacoes. Os ids das dimensoes que sao eixo de composicao sao os de `Eixo`.
"""

from api.indicadores import (
    AREA_CINE,
    CODIGO_REGIAO,
    CODIGO_UF,
    EIXOS,
    PERFIS,
    PREFIXO_BASE,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_GRAU,
    ROTULO_ORGANIZACAO,
    ROTULO_REDE,
    ROTULO_REGIAO,
    TIPOS_INGRESSO,
    TITULACOES,
    UF_INFO,
    Categoria,
    Dimensao,
    Eixo,
    Grau,
    Nivel,
    Organizacao,
    Recorte,
    Rede,
)
from api.semantica.fontes import VERIFICACOES_CSV
from api.semantica.modelos import (
    ColunaDimensao,
    Componente,
    DimensaoSemantica,
    LiteralColuna,
    Sinonimo,
    StatusSinonimo,
    ValorDimensao,
)
from api.semantica.texto import STOPWORDS, chave

_INVENTARIO = VERIFICACOES_CSV


def ver(*termos: str) -> tuple[Sinonimo, ...]:
    return tuple(Sinonimo(termo=t, status=StatusSinonimo.VERIFICADO) for t in termos)


def prop(*termos: str) -> tuple[Sinonimo, ...]:
    return tuple(Sinonimo(termo=t, status=StatusSinonimo.PROPOSTO) for t in termos)


def alias(terminologia: str, *termos: str) -> tuple[Sinonimo, ...]:
    """Alias de intencao: direciona ao conceito canonico; a resposta usa `terminologia`."""
    return tuple(
        Sinonimo(termo=t, status=StatusSinonimo.ALIAS, terminologia=terminologia) for t in termos
    )


def _lit(entidade: str, coluna: str, valor: str | int) -> LiteralColuna:
    return LiteralColuna(entidade=entidade, coluna=coluna, valor=valor)


def _col(entidade: str, coluna: str, rotulo: str | None = None) -> ColunaDimensao:
    return ColunaDimensao(entidade=entidade, coluna=coluna, coluna_rotulo=rotulo)


def _nas_duas(coluna: str, valor: str | int) -> tuple[LiteralColuna, ...]:
    return (_lit("ies", coluna, valor), _lit("cursos", coluna, valor))


# --- territorio -----------------------------------------------------------------------------------

_NIVEL = DimensaoSemantica(
    id="nivel_territorial",
    nome="Nível territorial",
    descricao="Nível em que o resultado é agregado: Brasil, região, UF ou município.",
    tipo="virtual",
    valores=(
        ValorDimensao(id=Nivel.BRASIL, rotulo="Brasil"),
        ValorDimensao(id=Nivel.REGIAO, rotulo="Região"),
        ValorDimensao(id=Nivel.UF, rotulo="UF", sinonimos=ver("estado", "unidade da federação")),
        ValorDimensao(
            id=Nivel.MUNICIPIO,
            rotulo="Município",
            sinonimos=prop("cidade"),
            limitacoes=(
                "As 5.571 unidades de nível municipal são 5.570 municípios mais Fernando de "
                "Noronha (distrito estadual): o nome correto é 'municípios e equivalentes'.",
            ),
        ),
    ),
    limitacoes=(
        "Mesorregião e microrregião não são níveis servidos (IND-Q-05).",
        "Dimensões de oferta sem território (EAD 'somente nível Brasil' e exterior) só existem "
        "no nível Brasil.",
    ),
    proveniencia="api/indicadores.py (Nivel); INDICADORES.md, regras transversais",
)

_RECORTE = DimensaoSemantica(
    id="recorte",
    nome="Recorte territorial",
    descricao=(
        "A que município uma instituição ou matrícula é atribuída: à sede da IES ou ao local "
        "de oferta do curso (inclui polos EAD). Dimensão obrigatória de todo indicador."
    ),
    tipo="virtual",
    valores=(
        ValorDimensao(
            id=Recorte.SEDE,
            rotulo="Sede da IES",
            sinonimos=ver("sede"),
            limitacoes=("698 unidades territoriais; é o único recorte da tabela de IES.",),
        ),
        ValorDimensao(
            id=Recorte.OFERTA,
            rotulo="Local de oferta",
            sinonimos=ver("oferta"),
            limitacoes=(
                "3.551 unidades territoriais; equipara campus físico a polo EAD. É o único "
                "recorte das métricas de curso.",
            ),
        ),
    ),
    limitacoes=(
        "Números de recortes diferentes não se comparam nem se dividem sem sinalização (IND-Q-06).",
    ),
    proveniencia="ADR-0004; api/indicadores.py (Recorte)",
)

_REGIAO = DimensaoSemantica(
    id="regiao",
    nome="Região",
    nome_no_lexico=False,  # o termo 'região' designa o nivel territorial
    descricao="Grande região do IBGE da sede da IES ou do local de oferta do curso.",
    tipo="categorica",
    territorial=True,
    colunas=(
        _col("ies", "co_regiao_ies", "no_regiao_ies"),
        _col("cursos", "co_regiao", "no_regiao"),
    ),
    valores=tuple(
        ValorDimensao(
            id=r,
            rotulo=ROTULO_REGIAO[r],
            literais=(
                # SMALLINT em ies, VARCHAR em cursos: o literal acompanha o tipo da coluna.
                _lit("ies", "co_regiao_ies", int(CODIGO_REGIAO[r])),
                _lit("ies", "no_regiao_ies", ROTULO_REGIAO[r]),
                _lit("cursos", "co_regiao", CODIGO_REGIAO[r]),
                _lit("cursos", "no_regiao", ROTULO_REGIAO[r]),
            ),
        )
        for r in ROTULO_REGIAO
    ),
    limitacoes=(
        "co_regiao_ies é SMALLINT e cursos.co_regiao é VARCHAR: comparar coluna com coluna "
        "exige CAST(i.co_regiao_ies AS VARCHAR).",
        "Em cursos, 11.778 linhas trazem 'Cursos a distância' no lugar da região: filtrar pelos "
        "7 dígitos de co_municipio antes de agrupar.",
    ),
    proveniencia="api/indicadores.py (CODIGO_REGIAO, ROTULO_REGIAO)",
)

_UF = DimensaoSemantica(
    id="uf",
    nome="UF",
    nome_no_lexico=False,
    descricao="Unidade da federação da sede da IES ou do local de oferta do curso.",
    tipo="categorica",
    territorial=True,
    colunas=(
        _col("ies", "sg_uf_ies", "no_uf_ies"),
        _col("ies", "co_uf_ies"),
        _col("cursos", "sg_uf", "no_uf"),
        _col("cursos", "co_uf"),
        _col("municipio", "cd_uf"),
    ),
    valores=tuple(
        ValorDimensao(
            id=uf,
            rotulo=nome,
            # 'Pará' sem acento e a preposicao 'para': a recuperacao decide pelo acento.
            rotulo_no_lexico=chave(nome) not in STOPWORDS,
            literais=(
                _lit("ies", "sg_uf_ies", str(uf)),
                _lit("ies", "no_uf_ies", nome),
                _lit("ies", "co_uf_ies", CODIGO_UF[uf]),
                _lit("cursos", "sg_uf", str(uf)),
                _lit("cursos", "no_uf", nome),
                _lit("cursos", "co_uf", CODIGO_UF[uf]),
                _lit("municipio", "cd_uf", CODIGO_UF[uf]),
            ),
        )
        for uf, (nome, _) in sorted(UF_INFO.items())
    ),
    limitacoes=(
        "GROUP BY sg_uf em cursos sem o filtro de 7 dígitos devolve 28 'UFs'.",
        "A sigla só é reconhecida na pergunta quando escrita em maiúsculas (SP, não sp). "
        "'Pará' é reconhecido pelo acento, em qualquer caixa; 'para' sem o acento depois "
        "de preposição de lugar pede esclarecimento.",
    ),
    proveniencia="api/indicadores.py (UF, UF_INFO, CODIGO_UF)",
)

_MUNICIPIO = DimensaoSemantica(
    id="municipio",
    nome="Município",
    nome_no_lexico=False,
    descricao="Município (código IBGE de 7 dígitos) da sede da IES ou do local de oferta.",
    tipo="categorica",
    territorial=True,
    colunas=(
        _col("ies", "co_municipio_ies"),
        _col("cursos", "co_municipio"),
        _col("municipio", "codigo_municipio_dv"),
    ),
    valores_enumerados=False,
    n_valores=5571,
    limitacoes=(
        "Identidade é o código IBGE de 7 dígitos; nunca o nome. A resolução de um município "
        "citado por nome não é feita pela camada semântica.",
        "5.571 unidades reais em `municipio` (28 sentinelas excluídas); 698 sediam IES e 3.551 "
        "têm oferta.",
    ),
    proveniencia="JOIN_STRATEGY.md; ADR-0004",
)

_SIM_NAO = "Sim", "Não"

_CAPITAL = DimensaoSemantica(
    id="capital",
    nome="Capital",
    nome_no_lexico=False,  # o termo 'capital' e o filtro capital = sim
    descricao=(
        "Se o município é capital de UF (dimensão territorial). É atributo do município de "
        "SEDE na tabela de IES e do município de OFERTA na tabela de cursos: obedece ao "
        "recorte territorial vigente, que é sempre declarado na resposta."
    ),
    tipo="categorica",
    territorial=True,
    colunas=(
        _col("ies", "in_capital_ies"),
        _col("cursos", "in_capital"),
        _col("municipio", "municipio_capital"),
    ),
    valores=tuple(
        ValorDimensao(
            id=slug,
            rotulo=rotulo,
            rotulo_no_lexico=False,
            sinonimos=ver("capital") if slug == "sim" else (),
            literais=(
                _lit("ies", "in_capital_ies", rotulo),
                _lit("cursos", "in_capital", rotulo),
                _lit("municipio", "municipio_capital", rotulo),
            ),
        )
        for slug, rotulo in zip(("sim", "nao"), _SIM_NAO, strict=True)
    ),
    limitacoes=(
        "As três colunas designam os mesmos 27 municípios.",
        "cursos.in_capital traz 'Cursos a distância' nas 11.778 linhas sem município, e "
        "municipio.municipio_capital traz '0' na sentinela 9999999: comparar com = 'Sim'.",
    ),
    proveniencia=f"{_INVENTARIO} (bloco capital)",
)

# --- oferta e instituicao -------------------------------------------------------------------------

_SIN_DIMENSAO: dict[Dimensao, tuple[Sinonimo, ...]] = {
    Dimensao.PRESENCIAL: ver("presencial"),
    Dimensao.EAD_POLO: ver("polo", "polo EAD"),
    Dimensao.EAD_NACIONAL: (),
    Dimensao.EAD_EXTERIOR: ver("EAD no exterior"),
}
_LIM_DIMENSAO: dict[Dimensao, tuple[str, ...]] = {
    Dimensao.PRESENCIAL: (),
    Dimensao.EAD_POLO: (
        "Carrega matrículas, ingressos e concluintes da EAD; o marcador de curso é zero.",
        "9 linhas não têm município: o filtro de 7 dígitos continua obrigatório.",
    ),
    Dimensao.EAD_NACIONAL: (
        "Carrega o marcador de curso, as vagas e as inscrições da EAD; matrículas são zero.",
        "Não tem município, UF nem região em nenhuma linha: só existe no nível Brasil.",
    ),
    Dimensao.EAD_EXTERIOR: ("Não tem município, UF nem região: só existe no nível Brasil.",),
}

_DIMENSAO = DimensaoSemantica(
    id=Eixo.DIMENSAO,
    nome=EIXOS[Eixo.DIMENSAO].nome,
    descricao=(
        "Dimensão de dados da oferta do curso (tp_dimensao): presencial, EAD em polo, EAD "
        "'somente nível Brasil' e EAD no exterior. É como a modalidade é medida, e é "
        "obrigatória em toda métrica de cursos."
    ),
    tipo="categorica",
    colunas=(_col("cursos", "tp_dimensao"),),
    valores=tuple(
        ValorDimensao(
            id=d,
            rotulo=ROTULO_DIMENSAO[d],
            sinonimos=_SIN_DIMENSAO[d],
            literais=(_lit("cursos", "tp_dimensao", ROTULO_DIMENSAO[d]),),
            limitacoes=_LIM_DIMENSAO[d],
        )
        for d in Dimensao
    ),
    sinonimos=ver("modalidade", "modalidade de ensino"),
    ficha=EIXOS[Eixo.DIMENSAO].ficha,
    limitacoes=(
        *EIXOS[Eixo.DIMENSAO].notas,
        "tp_modalidade_ensino é função de tp_dimensao e não é usada como filtro.",
    ),
    proveniencia="INDICADORES.md, regra transversal 2; api/indicadores.py (ROTULO_DIMENSAO)",
)

_REDE = DimensaoSemantica(
    id=Eixo.REDE,
    nome=EIXOS[Eixo.REDE].nome,
    descricao="Rede da IES ofertante: pública ou privada.",
    tipo="categorica",
    colunas=(_col("ies", "ds_rede"), _col("cursos", "tp_rede")),
    valores=(
        ValorDimensao(
            id=Rede.PUBLICA,
            rotulo=ROTULO_REDE[Rede.PUBLICA],
            sinonimos=ver("rede pública"),
            literais=(
                _lit("ies", "ds_rede", ROTULO_REDE[Rede.PUBLICA]),
                _lit("cursos", "tp_rede", ROTULO_REDE[Rede.PUBLICA]),
            ),
            limitacoes=(
                "Inclui as 28 IES de categoria 'Especial' (45.400 matrículas): não é sinônimo "
                "das três categorias 'Pública …'.",
            ),
        ),
        ValorDimensao(
            id=Rede.PRIVADA,
            rotulo=ROTULO_REDE[Rede.PRIVADA],
            sinonimos=ver("rede privada", "rede particular"),
            literais=(
                _lit("ies", "ds_rede", ROTULO_REDE[Rede.PRIVADA]),
                _lit("cursos", "tp_rede", ROTULO_REDE[Rede.PRIVADA]),
            ),
        ),
    ),
    ficha=EIXOS[Eixo.REDE].ficha,
    limitacoes=(
        "Entre tabelas, a rede compara-se por ies.ds_rede e cursos.tp_rede (ADR-0007); "
        "ies.tp_rede é código inteiro e não é usada.",
        "Descreve a IES ofertante, não o financiamento do estudante.",
    ),
    proveniencia="ADR-0007; api/indicadores.py (ROTULO_REDE)",
)

_SIN_CATEGORIA: dict[Categoria, tuple[Sinonimo, ...]] = {
    Categoria.PUBLICA_FEDERAL: (),
    Categoria.PUBLICA_ESTADUAL: (),
    Categoria.PUBLICA_MUNICIPAL: (),
    Categoria.PRIVADA_COM_FINS: ver("com fins lucrativos"),
    Categoria.PRIVADA_SEM_FINS: ver("sem fins lucrativos"),
    Categoria.ESPECIAL: ver("categoria especial"),
}

_CATEGORIA = DimensaoSemantica(
    id=Eixo.CATEGORIA,
    nome=EIXOS[Eixo.CATEGORIA].nome,
    descricao="Categoria administrativa da IES; constante por IES e idêntica nas duas tabelas.",
    tipo="categorica",
    colunas=(
        _col("ies", "tp_categoria_administrativa"),
        _col("cursos", "tp_categoria_administrativa"),
    ),
    valores=tuple(
        ValorDimensao(
            id=c,
            rotulo=ROTULO_CATEGORIA[c],
            sinonimos=_SIN_CATEGORIA[c],
            literais=_nas_duas("tp_categoria_administrativa", ROTULO_CATEGORIA[c]),
        )
        for c in Categoria
    ),
    sinonimos=ver("categoria"),
    limitacoes=(
        "A composição por categoria é servida pela API, mas ainda não tem ficha no Bloco B.",
    ),
    proveniencia="api/indicadores.py (ROTULO_CATEGORIA, REDE_DA_CATEGORIA)",
)

_SIN_ORGANIZACAO: dict[Organizacao, tuple[Sinonimo, ...]] = {
    Organizacao.UNIVERSIDADE: (),
    Organizacao.CENTRO_UNIVERSITARIO: (),
    Organizacao.FACULDADE: (),
    Organizacao.INSTITUTO_FEDERAL: ver("instituto federal"),
    Organizacao.CEFET: ver("CEFET"),
}

_ORGANIZACAO = DimensaoSemantica(
    id=Eixo.ORGANIZACAO,
    nome=EIXOS[Eixo.ORGANIZACAO].nome,
    descricao="Organização acadêmica da IES; constante por IES e idêntica nas duas tabelas.",
    tipo="categorica",
    colunas=(
        _col("ies", "tp_organizacao_academica"),
        _col("cursos", "tp_organizacao_academica"),
    ),
    valores=tuple(
        ValorDimensao(
            id=o,
            rotulo=ROTULO_ORGANIZACAO[o],
            sinonimos=_SIN_ORGANIZACAO[o],
            literais=_nas_duas("tp_organizacao_academica", ROTULO_ORGANIZACAO[o]),
        )
        for o in Organizacao
    ),
    sinonimos=ver("organização"),
    limitacoes=(
        "'Universidade' e 'Faculdade' são categorias oficiais (206 e 1.897 IES), não o uso "
        "informal de 'qualquer instituição de ensino superior' (2.561).",
    ),
    proveniencia="api/indicadores.py (ROTULO_ORGANIZACAO)",
)


def _indicador(coluna: str, termo: str) -> tuple[ValorDimensao, ...]:
    """Valores de um indicador SMALLINT 0/1 presente nas duas tabelas."""
    return tuple(
        ValorDimensao(
            id=slug,
            rotulo=rotulo,
            rotulo_no_lexico=False,
            sinonimos=ver(termo) if slug == "sim" else (),
            literais=_nas_duas(coluna, valor),
        )
        for slug, rotulo, valor in (("sim", "Sim", 1), ("nao", "Não", 0))
    )


_LIM_SEM_API = "Domínio medido; a API ainda não tem indicador nem filtro por esta dimensão."

_COMUNITARIA = DimensaoSemantica(
    id="comunitaria",
    nome="IES comunitária",
    nome_no_lexico=False,  # 'comunitária' e o filtro = sim; o nome engoliria 'IES'
    descricao=(
        "IES classificada como comunitária na fonte (atributo da IES, repetido em cursos). Base "
        "conceitual oficial: Lei nº 12.881/2013."
    ),
    tipo="categorica",
    colunas=(_col("ies", "in_comunitaria"), _col("cursos", "in_comunitaria")),
    valores=_indicador("in_comunitaria", "comunitária"),
    limitacoes=(
        "É a classificação registrada na fonte (86 IES): não inferir a partir de rede, categoria "
        "administrativa, gratuidade, natureza jurídica ou qualquer outra variável.",
        _LIM_SEM_API,
    ),
    proveniencia=f"{_INVENTARIO} (bloco dominio); decisão do autor (Fase 12)",
)

_CONFESSIONAL = DimensaoSemantica(
    id="confessional",
    nome="IES confessional",
    nome_no_lexico=False,
    descricao=(
        "IES classificada como confessional na fonte (atributo da IES, repetido em cursos). Base "
        "conceitual oficial: art. 19 da LDB, com a redação da Lei nº 13.868/2019."
    ),
    tipo="categorica",
    colunas=(_col("ies", "in_confessional"), _col("cursos", "in_confessional")),
    valores=_indicador("in_confessional", "confessional"),
    limitacoes=(
        "É a classificação registrada na fonte (56 IES): não inferir a partir do nome da "
        "instituição, da mantenedora, de religião ou de qualquer outra variável.",
        _LIM_SEM_API,
    ),
    proveniencia=f"{_INVENTARIO} (bloco dominio); decisão do autor (Fase 12)",
)

# --- curso ----------------------------------------------------------------------------------------

_SIN_GRAU: dict[Grau, tuple[Sinonimo, ...]] = {
    Grau.BACHARELADO: (),
    Grau.LICENCIATURA: (),
    Grau.TECNOLOGICO: ver("tecnólogo"),
    Grau.NAO_APLICAVEL: (),
}

_GRAU = DimensaoSemantica(
    id=Eixo.GRAU,
    nome=EIXOS[Eixo.GRAU].nome,
    descricao="Grau acadêmico do curso; constante por curso.",
    tipo="categorica",
    colunas=(_col("cursos", "tp_grau_academico"),),
    valores=tuple(
        ValorDimensao(
            id=g,
            rotulo=ROTULO_GRAU[g],
            sinonimos=_SIN_GRAU[g],
            literais=(_lit("cursos", "tp_grau_academico", ROTULO_GRAU[g]),),
        )
        for g in Grau
    ),
    sinonimos=ver("grau"),
    ficha=EIXOS[Eixo.GRAU].ficha,
    limitacoes=EIXOS[Eixo.GRAU].notas,
    proveniencia="INDICADORES.md IND-R-05; api/indicadores.py (ROTULO_GRAU)",
)

_BLOQUEIO_CINE = (
    "Bloqueio provisório: não servida no nível municipal enquanto o piso de supressão para "
    "células pequenas não é definido (IND-R-06)."
)

_AREA = DimensaoSemantica(
    id=Eixo.AREA,
    nome=EIXOS[Eixo.AREA].nome,
    descricao="Área geral da classificação CINE do curso (11 áreas, pares código/nome 1:1).",
    tipo="categorica",
    colunas=(_col("cursos", "co_cine_area_geral", "no_cine_area_geral"),),
    valores=tuple(
        ValorDimensao(
            id=a,
            rotulo=nome,
            literais=(
                _lit("cursos", "co_cine_area_geral", codigo),
                _lit("cursos", "no_cine_area_geral", nome),
            ),
        )
        for a, (codigo, nome) in AREA_CINE.items()
    ),
    sinonimos=ver("área", "área do conhecimento", "área CINE", "CINE"),
    niveis_bloqueados=(Nivel.MUNICIPIO,),
    ficha=EIXOS[Eixo.AREA].ficha,
    limitacoes=(
        *EIXOS[Eixo.AREA].notas,
        "É a classificação do INEP, não a divisão administrativa das instituições.",
        _BLOQUEIO_CINE,
    ),
    proveniencia="INDICADORES.md IND-R-06; api/indicadores.py (AREA_CINE)",
)

_ROTULO_CINE = DimensaoSemantica(
    id=Eixo.ROTULO_CINE,
    nome=EIXOS[Eixo.ROTULO_CINE].nome,
    descricao="Rótulo CINE do curso (353 rótulos, pares código/nome 1:1).",
    tipo="categorica",
    colunas=(_col("cursos", "co_cine_rotulo", "no_cine_rotulo"),),
    valores_enumerados=False,
    n_valores=353,
    niveis_bloqueados=(Nivel.MUNICIPIO,),
    ficha=EIXOS[Eixo.ROTULO_CINE].ficha,
    limitacoes=(
        *EIXOS[Eixo.ROTULO_CINE].notas,
        "co_cine_rotulo vem com aspas literais ('\"0113P01\"'): removê-las só para exibir.",
        "A resolução de um curso citado por nome não é feita pela camada semântica.",
        _BLOQUEIO_CINE,
    ),
    proveniencia="INDICADORES.md IND-R-06",
)

_LIM_GRATUITO = (
    "Gratuidade é atributo do CURSO e independe da rede: 74.228 matrículas da rede pública "
    "estão em curso não gratuito e 2.216 matrículas em curso gratuito estão na rede privada. "
    "Nunca tratar 'gratuito' como 'rede pública'."
)

_GRATUITO = DimensaoSemantica(
    id="gratuito",
    nome="Curso gratuito",
    nome_no_lexico=False,  # o nome engoliria 'curso'; o termo e o filtro gratuito = sim
    descricao="Curso marcado como gratuito na fonte; atributo do curso, constante por curso.",
    tipo="categorica",
    colunas=(_col("cursos", "in_gratuito"),),
    valores=tuple(
        ValorDimensao(
            id=slug,
            rotulo=rotulo,
            rotulo_no_lexico=False,
            sinonimos=ver("gratuito", "gratuita", "gratuidade") if slug == "sim" else (),
            literais=(_lit("cursos", "in_gratuito", rotulo),),
            limitacoes=(
                ("A resposta diz 'curso gratuito' (1.993.055 matrículas).", _LIM_GRATUITO)
                if slug == "sim"
                else ()
            ),
        )
        for slug, rotulo in zip(("sim", "nao"), _SIM_NAO, strict=True)
    ),
    limitacoes=(_LIM_GRATUITO, _LIM_SEM_API),
    proveniencia=f"{_INVENTARIO} (bloco gratuito); decisão do autor (Fase 12)",
)

# --- decomposicoes por coluna ---------------------------------------------------------------------

_BLOQUEIO_PERFIL = (
    "Bloqueio provisório: não servido no nível municipal enquanto o piso de supressão para "
    "células pequenas não é definido (IND-R-07)."
)
_SIN_PERFIL: dict[Eixo, tuple[Sinonimo, ...]] = {
    Eixo.SEXO: prop("gênero"),
    Eixo.COR_RACA: ver("cor", "raça", "cor/raça"),
    Eixo.FAIXA_ETARIA: prop("idade"),
    Eixo.NACIONALIDADE: (),
    Eixo.PROCEDENCIA_ESCOLAR: ver("procedência escolar"),
}
_SIN_VALOR_PERFIL: dict[str, tuple[Sinonimo, ...]] = {
    "feminino": prop("mulher"),
    "masculino": prop("homem"),
    "estrangeira": ver("estrangeiro"),
}


def _perfil(eixo: Eixo) -> DimensaoSemantica:
    info = EIXOS[eixo]
    return DimensaoSemantica(
        id=eixo,
        nome=info.nome,
        descricao=(
            f"{info.nome} das matrículas, ingressos e conclusões: uma coluna por categoria, "
            "partição exata da coluna-total (0 divergências em 720.349 linhas)."
        ),
        tipo="decomposicao",
        valores=tuple(
            ValorDimensao(
                id=slug,
                rotulo=nome,
                sinonimos=_SIN_VALOR_PERFIL.get(slug, ()),
                componentes=tuple(
                    Componente(entidade="cursos", coluna=f"{prefixo}_{sufixo}", metrica=base)
                    for base, prefixo in PREFIXO_BASE.items()
                ),
            )
            for slug, nome, sufixo in PERFIS[eixo]
        ),
        sinonimos=_SIN_PERFIL[eixo],
        filtravel=False,  # decomposicao: a coluna ja e a metrica restrita ao valor
        so_metricas=tuple(sorted(info.so_indicadores)),
        niveis_bloqueados=(Nivel.MUNICIPIO,),
        ficha=info.ficha,
        limitacoes=(*info.notas, _BLOQUEIO_PERFIL),
        proveniencia="INDICADORES.md IND-R-07; api/indicadores.py (PERFIS)",
    )


_SIN_TITULACAO: dict[str, tuple[Sinonimo, ...]] = {
    "mestrado": prop("mestre"),
    "doutorado": prop("doutor"),
}

_TITULACAO = DimensaoSemantica(
    id=Eixo.TITULACAO,
    nome=EIXOS[Eixo.TITULACAO].nome,
    descricao=(
        "Maior titulação dos docentes em exercício: cinco colunas da tabela de IES que "
        "particionam qt_doc_total exatamente."
    ),
    tipo="decomposicao",
    valores=tuple(
        ValorDimensao(
            id=slug,
            rotulo=nome,
            # 'Graduação' sozinho e escopo dos cursos, nao titulacao docente.
            sinonimos=_SIN_TITULACAO.get(slug, ()),
            componentes=(Componente(entidade="ies", coluna=coluna, metrica="docentes"),),
        )
        for slug, nome, coluna in TITULACOES
    ),
    sinonimos=ver("titulação", "titulação docente"),
    filtravel=False,
    so_metricas=tuple(sorted(EIXOS[Eixo.TITULACAO].so_indicadores)),
    ficha=EIXOS[Eixo.TITULACAO].ficha,
    limitacoes=EIXOS[Eixo.TITULACAO].notas,
    proveniencia="INDICADORES.md IND-R-12; api/indicadores.py (TITULACOES)",
)

_TIPO_INGRESSO = DimensaoSemantica(
    id=Eixo.TIPO_INGRESSO,
    nome=EIXOS[Eixo.TIPO_INGRESSO].nome,
    descricao=(
        "Tipo de vaga ocupada pelo ingressante: quatro colunas que particionam qt_ing "
        "exatamente (0 divergências em 720.349 linhas)."
    ),
    tipo="decomposicao",
    valores=tuple(
        ValorDimensao(
            id=slug,
            rotulo=nome,
            componentes=(Componente(entidade="cursos", coluna=coluna, metrica="ingressantes"),),
        )
        for slug, nome, coluna in TIPOS_INGRESSO
    ),
    sinonimos=ver("tipo de ingresso"),
    filtravel=False,
    so_metricas=tuple(sorted(EIXOS[Eixo.TIPO_INGRESSO].so_indicadores)),
    limitacoes=(
        *EIXOS[Eixo.TIPO_INGRESSO].notas,
        "Composição servida pela API, ainda sem ficha no Bloco B de INDICADORES.md.",
    ),
    proveniencia="INDICADORES.md IND-D-04 (nota da Fase 9); api/indicadores.py (TIPOS_INGRESSO)",
)

DIMENSOES: tuple[DimensaoSemantica, ...] = (
    _NIVEL,
    _RECORTE,
    _REGIAO,
    _UF,
    _MUNICIPIO,
    _CAPITAL,
    _DIMENSAO,
    _REDE,
    _CATEGORIA,
    _ORGANIZACAO,
    _COMUNITARIA,
    _CONFESSIONAL,
    _GRAU,
    _AREA,
    _ROTULO_CINE,
    _GRATUITO,
    *(_perfil(e) for e in PERFIS),
    _TITULACAO,
    _TIPO_INGRESSO,
)

# Dimensoes cuja presenca torna a pergunta territorial (nivel abaixo do Brasil ou filtro).
DIMENSOES_TERRITORIAIS: frozenset[str] = frozenset(d.id for d in DIMENSOES if d.territorial)
