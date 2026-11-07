"""Entidades, relacionamentos e regras de dominio da camada semantica.

Fatos medidos no DuckDB local em 2026-10-07 (scripts/analise/auditar_schema_semantico.py ->
`fontes.VERIFICACOES_CSV`), mais as regras transversais de
INDICADORES.md e as cinco regras de dominio de AI_ANALYST.md.
"""

from api.indicadores import PERFIS, RAZOES, Eixo
from api.semantica.dimensoes import DIMENSOES_TERRITORIAIS, ver
from api.semantica.fontes import VERIFICACOES_CSV
from api.semantica.modelos import Entidade, RefColuna, RegraDominio, Relacionamento

_VERIFICACOES = VERIFICACOES_CSV

ENTIDADES: tuple[Entidade, ...] = (
    Entidade(
        id="ies",
        nome="Instituição de ensino superior (IES)",
        descricao="Instituições com registro no Censo da Educação Superior 2024.",
        tabela="inep_educacao_superior_ies",
        linhas=2_561,
        grain="uma linha por IES",
        chave=("nu_ano_censo", "co_ies"),
        metrica_de_contagem="ies",
        limitacoes=(
            "Todo atributo territorial é o da SEDE: uma IES com várias unidades conta 1, no "
            "município da sede. A base não tem campus nem unidade acadêmica.",
            "Métricas de IES (docentes, técnicos) só se agregam nesta tabela, nunca após JOIN "
            "com cursos.",
        ),
        proveniencia=f"DATA_GRAIN.md; {_VERIFICACOES} (bloco inventario)",
    ),
    Entidade(
        id="cursos",
        nome="Oferta de curso",
        descricao=(
            "Cursos de graduação do Censo 2024, no grain em que a base os registra: uma linha "
            "por curso, município de oferta e dimensão de oferta."
        ),
        tabela="inep_educacao_superior_cursos",
        linhas=720_349,
        grain=(
            "curso × município de oferta × dimensão de oferta. NÃO é uma linha por curso: 720.349 "
            "linhas para 46.150 "
            "cursos, 93,5% delas EAD replicadas por polo."
        ),
        chave=("nu_ano_censo", "co_curso", "co_municipio", "tp_dimensao"),
        sinonimos=ver("curso"),
        metrica_de_contagem="cursos",
        limitacoes=(
            "Contar cursos é SUM(qt_curso) (45.776); nunca COUNT(*) nem COUNT(DISTINCT co_curso).",
            "As métricas são distribuídas entre os polos de um curso EAD, não replicadas: SUM é "
            "válido.",
            "11.778 linhas não têm município e trazem 'Cursos a distância' em oito colunas "
            "territoriais.",
            "Não existe coluna de situação nem de turno do curso; 4 linhas (393 matrículas) são "
            "de nível 'Sequencial de Formação Específica', não de graduação.",
        ),
        proveniencia=f"DATA_GRAIN.md; {_VERIFICACOES} (blocos curso e relacao)",
    ),
    Entidade(
        id="municipio",
        nome="Município (tabela-ponte)",
        descricao=(
            "Cadastro de municípios e equivalentes: liga o código de 7 dígitos do Censo ao de "
            "6 dígitos da população."
        ),
        tabela="municipio",
        linhas=5_599,
        grain="uma linha por código municipal (5.571 unidades reais + 28 sentinelas)",
        chave=("codigo_municipio_dv",),
        limitacoes=(
            "28 sentinelas ('Município Ignorado - <UF>', 9900000 e 9999999) devem ser "
            "excluídas antes de qualquer denominador ou mapa; o Censo não referencia nenhuma.",
            "As 5.571 unidades são 5.570 municípios mais Fernando de Noronha.",
        ),
        proveniencia=f"JOIN_STRATEGY.md; {_VERIFICACOES} (bloco relacao)",
    ),
    Entidade(
        id="populacao",
        nome="População estimada (IBGE)",
        descricao="População residente estimada por município e ano; só 2024 é usado.",
        tabela="ibge_populacao_estimada",
        linhas=144_678,
        grain=(
            "uma linha por (ano, município de 6 dígitos), em 26 anos — o par só é único em "
            "2024 (5.571 linhas); há 50 pares duplicados entre 2000 e 2020"
        ),
        chave=("ano", "cod_municipio"),
        sinonimos=ver("população", "habitante"),
        limitacoes=(
            "Há 50 pares (ano, município) duplicados com valores divergentes entre 2000 e 2020; "
            "2024 está limpo: o filtro de ano é obrigatório.",
            "É denominador de IND-R-01, não um indicador por si: população total, não a "
            "população em idade de cursar o ensino superior.",
        ),
        proveniencia=f"INDICADORES.md IND-R-01; {_VERIFICACOES} (bloco relacao)",
    ),
)


def _ref(entidade: str, coluna: str) -> RefColuna:
    return RefColuna(entidade=entidade, coluna=coluna)


FILTRO_7_DIGITOS = "regexp_full_match(c.co_municipio, '[0-9]{7}')"
FILTRO_SENTINELAS = (
    "right(m.codigo_municipio_dv, 5) <> '00000' AND m.codigo_municipio_dv <> '9999999'"
)

RELACIONAMENTOS: tuple[Relacionamento, ...] = (
    Relacionamento(
        id="cursos_ies",
        de="cursos",
        para="ies",
        cardinalidade="N:1",
        alias_de="c",
        alias_para="i",
        predicado="i.co_ies = c.co_ies",
        colunas=(_ref("cursos", "co_ies"), _ref("ies", "co_ies")),
        pre_condicoes=(
            "Pré-agregar cursos por co_ies ANTES de juntar qualquer métrica de IES: depois do "
            "JOIN, qt_doc_* e qt_tec_* repetem-se em cada linha de curso.",
            "Rede entre as tabelas compara-se por i.ds_rede = c.tp_rede, nunca pelos tp_rede.",
        ),
        limitacoes=(
            "O território da IES é a sede; o das linhas de curso é a oferta: o JOIN não torna "
            "os dois recortes comparáveis.",
        ),
        proveniencia=f"{_VERIFICACOES} (relacao: 720.349 linhas antes e depois, 0 órfãos)",
    ),
    Relacionamento(
        id="cursos_municipio",
        de="cursos",
        para="municipio",
        cardinalidade="N:1",
        alias_de="c",
        alias_para="m",
        predicado="m.codigo_municipio_dv = c.co_municipio",
        filtro=FILTRO_7_DIGITOS,
        colunas=(_ref("cursos", "co_municipio"), _ref("municipio", "codigo_municipio_dv")),
        pre_condicoes=(
            "Filtrar os 7 dígitos de co_municipio: 11.778 linhas trazem 'Cursos a distância'.",
            "A chave é codigo_municipio_dv (7 dígitos); codigo_municipio (6) devolve 0 linhas.",
        ),
        proveniencia=f"{_VERIFICACOES} (relacao: 708.571 linhas antes e depois, 0 órfãos)",
    ),
    Relacionamento(
        id="ies_municipio",
        de="ies",
        para="municipio",
        cardinalidade="N:1",
        alias_de="i",
        alias_para="m",
        predicado="m.codigo_municipio_dv = i.co_municipio_ies",
        colunas=(_ref("ies", "co_municipio_ies"), _ref("municipio", "codigo_municipio_dv")),
        proveniencia=f"{_VERIFICACOES} (relacao: 2.561 linhas antes e depois, 0 órfãos)",
    ),
    Relacionamento(
        id="municipio_populacao",
        de="municipio",
        para="populacao",
        cardinalidade="1:1",
        alias_de="m",
        alias_para="p",
        predicado="p.cod_municipio = m.codigo_municipio AND p.ano = '2024'",
        filtro=FILTRO_SENTINELAS,
        colunas=(
            _ref("municipio", "codigo_municipio"),
            _ref("municipio", "codigo_municipio_dv"),
            _ref("populacao", "cod_municipio"),
            _ref("populacao", "ano"),
        ),
        pre_condicoes=(
            "Filtrar p.ano = '2024' (texto): sem o filtro o JOIN devolve 144.678 linhas.",
            "Excluir as 28 sentinelas de `municipio`.",
            "A chave da população tem 6 dígitos: pela chave de 7 o JOIN devolve 0 linhas.",
        ),
        proveniencia=f"{_VERIFICACOES} (relacao: 5.571 antes e depois; soma 212.583.750)",
    ),
)

_DE_FLUXO = ("matriculas", "ingressantes", "concluintes")

REGRAS: tuple[RegraDominio, ...] = (
    # --- as cinco de AI_ANALYST.md ---
    RegraDominio(
        id="contagem_de_cursos",
        nome="Contar cursos é somar o marcador de curso",
        enunciado=(
            "Contar cursos é somar o marcador de curso contabilizado da base (IND-D-02) — nunca "
            "contar linhas da tabela nem códigos de curso distintos."
        ),
        predicado="SUM(qt_curso)",
        metricas=("cursos",),
        entidades=("cursos",),
        proveniencia="AI_ANALYST.md, regra 1; INDICADORES.md IND-D-02",
    ),
    RegraDominio(
        id="filtro_7_digitos",
        nome="Filtro de 7 dígitos em toda agregação territorial de cursos",
        enunciado=(
            "Agregação ou junção por território na tabela de cursos, em qualquer nível, exige o "
            "descarte das linhas sem código de município de 7 dígitos — inclusive só no polo EAD "
            "(9 linhas de polo não têm município)."
        ),
        predicado="regexp_full_match(co_municipio, '[0-9]{7}')",
        entidades=("cursos",),
        so_territorial=True,
        proveniencia="AI_ANALYST.md, regra 2; INDICADORES.md, regra transversal 4",
    ),
    RegraDominio(
        id="dimensao_de_oferta_declarada",
        nome="tp_dimensao declarada em toda métrica de cursos",
        enunciado=(
            "Toda métrica de cursos declara explicitamente as dimensões de oferta incluídas; "
            "não há padrão universal e as quatro não se somam sem declaração."
        ),
        entidades=("cursos",),
        proveniencia="AI_ANALYST.md, regra 3; ADR-0009",
    ),
    RegraDominio(
        id="grain_de_ies",
        nome="Métrica de IES só agrega no grain de IES",
        enunciado=(
            "Docentes e técnicos agregam-se na tabela de IES, nunca depois de juntá-la à de "
            "cursos; e não se dividem por métrica de curso (IND-Q-03)."
        ),
        entidades=("ies",),
        metricas=("docentes", "tecnicos", "titulacao_docente"),
        proveniencia="AI_ANALYST.md, regra 4; INDICADORES.md, regra transversal 5",
    ),
    RegraDominio(
        id="declarar_recorte_e_dimensao",
        nome="Toda resposta declara o recorte territorial e a dimensão usados",
        enunciado=(
            "A resposta declara o recorte (sede ou oferta) e as dimensões de oferta usadas, "
            "mesmo quando vieram de um padrão. Plano que omita o recorte é inválido."
        ),
        sempre=True,
        proveniencia="AI_ANALYST.md, regra 5; ADR-0004",
    ),
    # --- regras transversais de INDICADORES.md e fatos medidos ---
    RegraDominio(
        id="ano_texto_2024",
        nome="Ano é o texto '2024'",
        enunciado=(
            "O ano é guardado como texto nas tabelas do Censo e na de população: o filtro é "
            "sempre o texto '2024', nunca o número 2024."
        ),
        predicado="nu_ano_censo = '2024'",
        sempre=True,
        proveniencia=f"INDICADORES.md, regra transversal 1; {_VERIFICACOES} (bloco comparacao)",
    ),
    RegraDominio(
        id="retrato_transversal",
        nome="Só existe 2024: retrato transversal",
        enunciado=(
            "A base tem um único ano. Nenhuma resposta fala em evolução, tendência, "
            "crescimento ou queda (IND-Q-04), e nenhuma razão entre concluintes e ingressantes "
            "ou matrículas é calculada (IND-Q-01)."
        ),
        sempre=True,
        proveniencia="INDICADORES.md IND-Q-04 e IND-Q-01",
    ),
    RegraDominio(
        id="sentinelas_de_municipio",
        nome="Excluir as sentinelas de `municipio`",
        enunciado=(
            "Antes de usar o cadastro de municípios como denominador, universo ou mapa, excluir as 28 "
            "sentinelas; restam 5.571 unidades reais."
        ),
        predicado="right(codigo_municipio_dv, 5) <> '00000' AND codigo_municipio_dv <> '9999999'",
        entidades=("municipio", "populacao"),
        proveniencia=f"INDICADORES.md IND-R-02; {_VERIFICACOES} (bloco relacao)",
    ),
    RegraDominio(
        id="chave_municipal",
        nome="Chave municipal é o código IBGE de 7 dígitos",
        enunciado=(
            "Município identifica-se pelo código de 7 dígitos, nunca pelo nome. A população usa "
            "6 dígitos: o cadastro de municípios é a ponte obrigatória, e só o ano de 2024 entra."
        ),
        entidades=("municipio", "populacao"),
        dimensoes=("municipio",),
        proveniencia="INDICADORES.md, regra transversal 6; JOIN_STRATEGY.md",
    ),
    RegraDominio(
        id="sem_territorio_so_no_brasil",
        nome="Dimensões sem território só no nível Brasil",
        enunciado=(
            "As dimensões EAD 'somente nível Brasil' e 'exterior' não têm município, UF nem "
            "região em nenhuma linha: em região, UF ou município só entram presencial e polo "
            "EAD. Por território, cursos, vagas e inscrições só existem no presencial."
        ),
        entidades=("cursos",),
        so_territorial=True,
        proveniencia="INDICADORES.md, regra transversal 2; api/indicadores.py",
    ),
    RegraDominio(
        id="ead_em_dimensoes_distintas",
        nome="Matrícula e contagem de curso de EAD não coexistem na mesma dimensão",
        enunciado=(
            "Em EAD, matrículas, ingressos e concluintes estão na dimensão de polo; o marcador "
            "de curso, as vagas e as inscrições estão na dimensão 'somente nível Brasil'. "
            "Nenhuma razão cruza as duas."
        ),
        dimensoes=(str(Eixo.DIMENSAO),),
        proveniencia="INDICADORES.md, regra transversal 2 e IND-R-10",
    ),
    RegraDominio(
        id="turno_so_no_presencial",
        nome="Turno só existe no presencial",
        enunciado=(
            "O turno (diurno/noturno) só fecha no universo presencial; o turno declarado "
            "em EAD é zero. Não há indicador de turno publicado."
        ),
        proveniencia="INDICADORES.md, fato transversal de turno",
    ),
    RegraDominio(
        id="rede_por_ds_rede",
        nome="Rede entre tabelas por ds_rede",
        enunciado=(
            "A rede compara-se entre IES e cursos pelo rótulo 'Pública'/'Privada', nunca pelo código. 'Pública' "
            "inclui as 28 IES de categoria Especial; 'pública' em sentido estrito são as três "
            "categorias administrativas 'Pública …'."
        ),
        dimensoes=(str(Eixo.REDE), str(Eixo.CATEGORIA)),
        proveniencia="ADR-0007; INDICADORES.md, regra transversal 7",
    ),
    RegraDominio(
        id="bloqueio_municipal_provisorio",
        nome="Bloqueios provisórios no nível municipal",
        enunciado=(
            "No nível municipal não são servidos: recortes por área ou rótulo CINE, o perfil "
            "(sexo, cor ou raça, faixa etária, nacionalidade, procedência escolar), a "
            "participação de financiamento e a de reserva de vagas — enquanto o piso de "
            "supressão para células pequenas não é definido."
        ),
        dimensoes=(str(Eixo.AREA), str(Eixo.ROTULO_CINE), *(str(e) for e in PERFIS)),
        metricas=(
            "composicao_area",
            "perfil",
            *(slug for slug, d in RAZOES.items() if not d.municipal),
        ),
        proveniencia="api/analises.py e api/fluxo.py (bloqueios); INDICADORES.md, pendências",
    ),
    RegraDominio(
        id="nao_cruzar_recortes",
        nome="Recortes diferentes não se comparam",
        enunciado=(
            "Um número de sede e um de oferta são respostas a perguntas diferentes: aparecem "
            "rotulados, nunca divididos um pelo outro nem somados (IND-Q-06)."
        ),
        dimensoes=("recorte", *sorted(DIMENSOES_TERRITORIAIS)),
        proveniencia="INDICADORES.md IND-Q-06; ADR-0004",
    ),
    RegraDominio(
        id="vinculos_nao_pessoas",
        nome="A base conta vínculos, não pessoas",
        enunciado=(
            "Matrículas, ingressos e concluintes são vínculos; inscrições não são candidatos. "
            "Nenhuma resposta os chama de alunos distintos, pessoas ou candidatos."
        ),
        metricas=(*_DE_FLUXO, "inscricoes", "inscricoes_por_vaga"),
        proveniencia="INDICADORES.md IND-D-03 e IND-D-07",
    ),
)
