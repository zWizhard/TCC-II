"""Catalogo das 318 colunas das quatro tabelas, cada uma com tipo real e um unico papel.

Lastro: o inventario de colunas (`fontes.INVENTARIO_CSV`; inventario medido no DuckDB
local por scripts/analise/auditar_schema_semantico.py). `tests/test_semantica.py` confere este
catalogo contra o inventario — nome, tipo e familia — e, com a base presente, contra o DuckDB.

O tipo e o do DuckDB, nao o da documentacao antiga: `ies.tp_rede` e INTEGER, `in_comunitaria` e
SMALLINT, `nu_ano_censo` e VARCHAR.
"""

from api.indicadores import PERFIS, PREFIXO_BASE, TIPOS_INGRESSO, TITULACOES
from api.semantica.fontes import INVENTARIO_CSV
from api.semantica.modelos import Coluna, Papel
from api.semantica.texto import palavras

_INVENTARIO = INVENTARIO_CSV
_FAMILIAS = "2026-09-19_familias_metricas.csv (auditar_familias_metricas.py)"
_FLUXO = "2026-10-07_fluxo.csv (auditar_fluxo.py)"

# Tipo mais frequente de cada tabela e as excecoes (inventario de 2026-10-07).
_TIPO_PADRAO: dict[str, str] = {
    "ies": "INTEGER",
    "cursos": "SMALLINT",
    "municipio": "VARCHAR",
    "populacao": "VARCHAR",
}
_VARCHAR_IES = palavras(
    "nu_ano_censo no_regiao_ies no_uf_ies sg_uf_ies co_uf_ies no_municipio_ies co_municipio_ies "
    "in_capital_ies no_mesorregiao_ies no_microrregiao_ies tp_organizacao_academica "
    "tp_categoria_administrativa no_mantenedora no_ies sg_ies ds_endereco_ies nu_cep_ies "
    "in_acesso_portal_capes in_acesso_outras_bases in_assina_outra_base "
    "in_repositorio_institucional in_busca_integrada in_servico_internet "
    "in_participa_rede_social in_catalogo_online ds_rede"
)
_SMALLINT_IES = palavras(
    "co_regiao_ies co_mesorregiao_ies co_microrregiao_ies in_comunitaria in_confessional "
    "co_mantenedora co_ies"
)
_VARCHAR_CURSOS = palavras(
    "nu_ano_censo no_regiao co_regiao no_uf sg_uf co_uf no_municipio co_municipio in_capital "
    "tp_dimensao tp_organizacao_academica tp_rede tp_categoria_administrativa no_curso "
    "no_cine_rotulo co_cine_rotulo no_cine_area_geral no_cine_area_especifica "
    "no_cine_area_detalhada tp_grau_academico in_gratuito tp_modalidade_ensino tp_nivel_academico"
)
_INTEGER_CURSOS = palavras(
    "co_ies co_curso qt_vg_total qt_vg_total_ead qt_vg_nova qt_vg_remanesc qt_inscrito_total "
    "qt_inscrito_total_diurno qt_inscrito_total_noturno qt_inscrito_total_ead qt_insc_vg_nova "
    "qt_insc_vg_remanesc qt_mat qt_mat_fem qt_mat_nacbras qt_mat_procescpublica "
    "qt_ativ_extracurricular qt_mat_ativ_extracurricular"
)
_TIPO_EXCECAO: dict[str, dict[str, str]] = {
    "ies": {**dict.fromkeys(_VARCHAR_IES, "VARCHAR"), **dict.fromkeys(_SMALLINT_IES, "SMALLINT")},
    "cursos": {
        **dict.fromkeys(_VARCHAR_CURSOS, "VARCHAR"),
        **dict.fromkeys(_INTEGER_CURSOS, "INTEGER"),
    },
    "municipio": {"longitude": "DECIMAL(15,7)", "latitude": "DECIMAL(15,7)"},
    "populacao": {"populacao": "DECIMAL(9,0)"},
}


def _grupo(
    entidade: str,
    papel: Papel,
    familia: str,
    nomes: str | list[str],
    proveniencia: str,
    motivo: str = "",
    ficha: str | None = None,
) -> list[Coluna]:
    lista = palavras(nomes) if isinstance(nomes, str) else nomes
    return [
        Coluna(
            entidade=entidade,
            nome=n,
            datatype=_TIPO_EXCECAO[entidade].get(n, _TIPO_PADRAO[entidade]),
            papel=papel,
            familia=familia,
            motivo=motivo,
            ficha=ficha,
            proveniencia=proveniencia,
        )
        for n in lista
    ]


_BASES = tuple(PREFIXO_BASE.values())  # qt_mat, qt_ing, qt_conc

_M_NOME = (
    "Rótulo de exibição, não é chave: homônimos e vazios medidos. Nunca juntar, filtrar nem "
    "agrupar por nome; usar o código."
)
_M_SEM_INDICADOR = (
    "Auditada, mas sem ficha em INDICADORES.md: nenhum indicador a usa e a ADR-0009 não a "
    "admitiu. Não exposta ao Analista IA."
)
_M_NAO_AUDITADA = (
    "Família nunca auditada: semântica, fechamento e domínio desconhecidos (A confirmar). "
    "Não exposta."
)

# --- IES (82) -------------------------------------------------------------------------------------

_IES: list[Coluna] = [
    *_grupo("ies", Papel.ESTRUTURAL, "particao_ano", "nu_ano_censo", "DATA_DICTIONARY.md"),
    *_grupo(
        "ies",
        Papel.DIMENSAO,
        "territorio",
        "no_regiao_ies co_regiao_ies no_uf_ies sg_uf_ies co_uf_ies",
        "DATA_DICTIONARY.md; api/indicadores.py (UF e região conferidas em teste)",
    ),
    *_grupo(
        "ies", Papel.IRRELEVANTE, "territorio", "no_municipio_ies", "DATA_DICTIONARY.md", _M_NOME
    ),
    *_grupo("ies", Papel.CHAVE, "chave_municipal", "co_municipio_ies", "JOIN_STRATEGY.md"),
    *_grupo("ies", Papel.DIMENSAO, "capital", "in_capital_ies", f"{_INVENTARIO} (bloco capital)"),
    *_grupo(
        "ies",
        Papel.QUARENTENA,
        "territorio_meso_micro",
        "no_mesorregiao_ies co_mesorregiao_ies no_microrregiao_ies co_microrregiao_ies",
        "INDICADORES.md IND-Q-05",
        "Códigos locais à UF (15 códigos para 131 mesorregiões); na microrregião nem o par "
        "(UF, código) identifica. Agrupar funde estados.",
        "IND-Q-05",
    ),
    *_grupo(
        "ies",
        Papel.DIMENSAO,
        "atributo_institucional",
        "tp_organizacao_academica tp_categoria_administrativa ds_rede in_comunitaria in_confessional",
        "DATA_DICTIONARY.md; literais em api/indicadores.py conferidos em teste",
    ),
    *_grupo(
        "ies",
        Papel.IRRELEVANTE,
        "atributo_institucional",
        "tp_rede",
        "ADR-0007",
        "Código inteiro (1/2) redundante com ds_rede. A rede é lida de ds_rede, que tem os "
        "mesmos rótulos de cursos.tp_rede; comparar os tp_rede crus dá ConversionException.",
    ),
    *_grupo(
        "ies",
        Papel.SEM_INDICADOR,
        "mantenedora",
        "no_mantenedora co_mantenedora",
        "DATA_DICTIONARY.md (só contagem de distintos)",
        _M_SEM_INDICADOR,
    ),
    *_grupo("ies", Papel.CHAVE, "chave_entidade", "co_ies", "DATA_GRAIN.md; JOIN_STRATEGY.md"),
    *_grupo(
        "ies",
        Papel.IRRELEVANTE,
        "identificacao_textual_endereco",
        "no_ies sg_ies ds_endereco_ies nu_cep_ies",
        "DATA_DICTIONARY.md",
        "Identificação textual e endereço: no_ies tem 14 homônimos e sg_ies está vazia em 459 "
        "linhas. Não são chave nem dimensão; a IES é identificada por co_ies.",
    ),
    *_grupo("ies", Papel.METRICA, "tecnicos_total", "qt_tec_total", "INDICADORES.md IND-D-09"),
    *_grupo(
        "ies",
        Papel.SEM_INDICADOR,
        "tecnicos_escolaridade_sexo",
        [
            f"qt_tec_{nivel}_{sexo}"
            for nivel in (
                "fundamental_incomp",
                "fundamental_comp",
                "medio",
                "superior",
                "especializacao",
                "mestrado",
                "doutorado",
            )
            for sexo in ("fem", "masc")
        ],
        _FAMILIAS,
        _M_SEM_INDICADOR + " (Partição exata de qt_tec_total, cruzando escolaridade com sexo.)",
    ),
    *_grupo(
        "ies",
        Papel.NAO_AUDITADA,
        "biblioteca",
        "in_acesso_portal_capes in_acesso_outras_bases in_assina_outra_base "
        "in_repositorio_institucional in_busca_integrada in_servico_internet "
        "in_participa_rede_social in_catalogo_online qt_periodico_eletronico qt_livro_eletronico",
        _INVENTARIO,
        _M_NAO_AUDITADA,
    ),
    *_grupo("ies", Papel.METRICA, "docentes_total", "qt_doc_total", "INDICADORES.md IND-D-08"),
    *_grupo(
        "ies",
        Papel.IRRELEVANTE,
        "docentes_total",
        "qt_doc_exe",
        "INDICADORES.md IND-D-08",
        "Mesma medida que qt_doc_total sob outro nome (0 divergências em 2.561 linhas): somar "
        "as duas duplica o total.",
    ),
    *_grupo(
        "ies",
        Papel.COMPONENTE,
        "docentes_titulacao",
        [coluna for _, _, coluna in TITULACOES],
        "INDICADORES.md IND-R-12",
        ficha="IND-R-12",
    ),
    *_grupo(
        "ies",
        Papel.SEM_INDICADOR,
        "docentes_decomposicao",
        [
            f"qt_doc_ex_{s}"
            for s in palavras(
                "femi masc int int_de int_sem_de parc hor 0_29 30_34 35_39 40_44 45_49 50_54 "
                "55_59 60_mais branca preta parda amarela indigena cor_nd bra est com_deficiencia"
            )
        ],
        _FAMILIAS,
        _M_SEM_INDICADOR + " (Sexo, regime, faixa etária, cor/raça e nacionalidade dos docentes.)",
    ),
]

# --- Cursos (223) ---------------------------------------------------------------------------------

_SUFIXOS_FINANC = palavras(
    "financ_reemb fies rpfies financ_reemb_outros financ_nreemb prounii prounip nrpfies "
    "financ_nreemb_outros"
)
_SUFIXOS_RESERVA = palavras(
    "rvredepublica rvppi rvquilo rvrefu rvpovt rvpdef rvsocial_rf rvidoso rvintern rvmedal "
    "rvtrans rvoutros"
)


def _por_base(sufixos: list[str]) -> list[str]:
    return [f"{base}_{s}" for base in _BASES for s in sufixos]


def _nao_auditada(familia: str, nomes: str) -> list[Coluna]:
    return _grupo("cursos", Papel.NAO_AUDITADA, familia, nomes, _INVENTARIO, _M_NAO_AUDITADA)


_CURSOS: list[Coluna] = [
    *_grupo("cursos", Papel.ESTRUTURAL, "particao_ano", "nu_ano_censo", "DATA_DICTIONARY.md"),
    *_grupo(
        "cursos",
        Papel.DIMENSAO,
        "territorio",
        "no_regiao co_regiao no_uf sg_uf co_uf",
        "DATA_DICTIONARY.md (contaminação 'Cursos a distância' em 8 colunas)",
    ),
    *_grupo(
        "cursos", Papel.IRRELEVANTE, "territorio", "no_municipio", "DATA_DICTIONARY.md", _M_NOME
    ),
    *_grupo("cursos", Papel.CHAVE, "chave_municipal", "co_municipio", "JOIN_STRATEGY.md"),
    *_grupo("cursos", Papel.DIMENSAO, "capital", "in_capital", f"{_INVENTARIO} (bloco capital)"),
    *_grupo("cursos", Papel.DIMENSAO, "dimensao_oferta", "tp_dimensao", "INDICADORES.md IND-R-04"),
    *_grupo(
        "cursos",
        Papel.IRRELEVANTE,
        "dimensao_oferta",
        "tp_modalidade_ensino",
        "INDICADORES.md IND-R-04; api/indicadores.py (MODALIDADE_DA_DIMENSAO)",
        "Função de tp_dimensao (as três dimensões de EAD dão sempre 'Curso a distância'): como "
        "filtro, soma dimensões que não coexistem. A modalidade é lida de tp_dimensao.",
    ),
    *_grupo(
        "cursos",
        Papel.DIMENSAO,
        "atributo_institucional",
        "tp_organizacao_academica tp_rede tp_categoria_administrativa in_comunitaria in_confessional",
        "DATA_DICTIONARY.md; literais em api/indicadores.py conferidos em teste",
    ),
    *_grupo("cursos", Papel.CHAVE, "chave_entidade", "co_ies co_curso", "DATA_GRAIN.md"),
    *_grupo(
        "cursos",
        Papel.IRRELEVANTE,
        "identificacao_textual_endereco",
        "no_curso",
        _INVENTARIO,
        "Nome do curso dado pela IES: 1.497 nomes para 46.150 cursos, não identifica curso. A "
        "classificação servida é o rótulo CINE.",
    ),
    *_grupo(
        "cursos",
        Papel.DIMENSAO,
        "classificacao_cine",
        "no_cine_rotulo co_cine_rotulo co_cine_area_geral no_cine_area_geral",
        "INDICADORES.md IND-R-06",
    ),
    *_grupo(
        "cursos",
        Papel.SEM_INDICADOR,
        "classificacao_cine",
        "co_cine_area_especifica no_cine_area_especifica co_cine_area_detalhada no_cine_area_detalhada",
        "DATA_DICTIONARY.md (só contagem de distintos: 39 e 89)",
        "Níveis intermediários da hierarquia CINE: só a contagem de distintos foi medida; os "
        "pares código/nome não foram conferidos e a API não os serve. Não expostos.",
    ),
    *_grupo(
        "cursos", Papel.DIMENSAO, "atributo_curso", "tp_grau_academico", "INDICADORES.md IND-R-05"
    ),
    *_grupo(
        "cursos", Papel.DIMENSAO, "atributo_curso", "in_gratuito", f"{_INVENTARIO} (bloco gratuito)"
    ),
    *_grupo(
        "cursos",
        Papel.SEM_INDICADOR,
        "atributo_curso",
        "tp_nivel_academico",
        f"{_INVENTARIO} (bloco dominio)",
        "Domínio medido ('Graduação' em 720.345 linhas; 'Sequencial de Formação Específica' em "
        "4 linhas, 393 matrículas), mas sem indicador nem filtro definidos. Não exposta.",
    ),
    *_grupo("cursos", Papel.METRICA, "marcador_curso", "qt_curso", "INDICADORES.md IND-D-02"),
    *_grupo("cursos", Papel.METRICA, "vagas", "qt_vg_total", "INDICADORES.md IND-D-06"),
    *_grupo(
        "cursos",
        Papel.SEM_INDICADOR,
        "vagas",
        "qt_vg_total_diurno qt_vg_total_noturno qt_vg_total_ead qt_vg_nova qt_vg_proc_seletivo "
        "qt_vg_remanesc qt_vg_prog_especial",
        _FAMILIAS,
        _M_SEM_INDICADOR + " (Duas partições exatas e ortogonais de qt_vg_total.)",
    ),
    *_grupo("cursos", Papel.METRICA, "inscritos", "qt_inscrito_total", "INDICADORES.md IND-D-07"),
    *_grupo(
        "cursos",
        Papel.SEM_INDICADOR,
        "inscritos",
        "qt_inscrito_total_diurno qt_inscrito_total_noturno qt_inscrito_total_ead qt_insc_vg_nova "
        "qt_insc_proc_seletivo qt_insc_vg_remanesc qt_insc_vg_prog_especial",
        _FAMILIAS,
        _M_SEM_INDICADOR + " (Duas partições exatas e ortogonais de qt_inscrito_total.)",
    ),
    *_grupo(
        "cursos",
        Papel.METRICA,
        "metrica_total_fluxo",
        "qt_ing qt_mat qt_conc",
        "INDICADORES.md IND-D-03/04/05",
    ),
    *(
        coluna
        for eixo, valores in PERFIS.items()
        for coluna in _grupo(
            "cursos",
            Papel.COMPONENTE,
            f"perfil_{eixo}",
            _por_base([sufixo for _, _, sufixo in valores]),
            f"INDICADORES.md IND-R-07; {_FLUXO}",
            ficha="IND-R-07",
        )
    ),
    *_grupo(
        "cursos",
        Papel.SEM_INDICADOR,
        "turno",
        _por_base(["diurno", "noturno"]),
        _FAMILIAS,
        "Partição exata só no presencial (o turno declarado em EAD é zero). Candidato futuro "
        "sem ficha em INDICADORES.md: não exposta.",
    ),
    *_grupo(
        "cursos",
        Papel.COMPONENTE,
        "ingresso_tipo_vaga",
        [coluna for _, _, coluna in TIPOS_INGRESSO],
        _FLUXO,
    ),
    *_grupo(
        "cursos",
        Papel.IRRELEVANTE,
        "ingresso_tipo_vaga",
        "qt_ing_proc_seletivo",
        _FLUXO,
        "Zero em todas as 720.349 linhas: não carrega informação.",
    ),
    *_grupo(
        "cursos",
        Papel.QUARENTENA,
        "ingresso_tipo_selecao",
        "qt_ing_vestibular qt_ing_enem qt_ing_avaliacao_seriada qt_ing_selecao_simplifica "
        "qt_ing_egr qt_ing_outro_tipo_selecao",
        "INDICADORES.md IND-Q-10",
        "Não é partição de qt_ing: somam 4.646.792 contra 5.010.613 e divergem nos dois "
        "sentidos (40.050 linhas acima, 130.209 abaixo).",
        "IND-Q-10",
    ),
    *_nao_auditada(
        "deficiencia", "qt_aluno_deficiente qt_ing_deficiente qt_mat_deficiente qt_conc_deficiente"
    ),
    *_nao_auditada("parfor", "qt_parfor qt_ing_parfor qt_mat_parfor qt_conc_parfor"),
    *_nao_auditada(
        "apoio_social",
        "qt_apoio_social qt_ing_apoio_social qt_mat_apoio_social qt_conc_apoio_social",
    ),
    *_nao_auditada(
        "ativ_extracurricular",
        "qt_ativ_extracurricular qt_ing_ativ_extracurricular qt_mat_ativ_extracurricular "
        "qt_conc_ativ_extracurricular",
    ),
    *_nao_auditada(
        "mob_academica",
        "qt_mob_academica qt_ing_mob_academica qt_mat_mob_academica qt_conc_mob_academica",
    ),
    *_grupo(
        "cursos",
        Papel.METRICA,
        "financiamento_agregado",
        _por_base(["financ"]),
        "INDICADORES.md IND-R-08",
        ficha="IND-R-08",
    ),
    *_grupo(
        "cursos",
        Papel.QUARENTENA,
        "financiamento_subtipo",
        _por_base(_SUFIXOS_FINANC),
        "INDICADORES.md IND-Q-08",
        "As subcolunas se sobrepõem (reembolsável + não reembolsável excede o total em 78.502 "
        "matrículas): FIES, ProUni e outros não formam composição. Só o agregado é servido.",
        "IND-Q-08",
    ),
    *_grupo(
        "cursos",
        Papel.METRICA,
        "reserva_vagas_agregado",
        _por_base(["reserva_vaga"]),
        "INDICADORES.md IND-R-09",
        ficha="IND-R-09",
    ),
    *_grupo(
        "cursos",
        Papel.QUARENTENA,
        "reserva_vagas_subtipo",
        _por_base(_SUFIXOS_RESERVA),
        "INDICADORES.md IND-Q-09",
        "Os 12 subtipos somam 1.116.988 contra 648.225 e divergem nos dois sentidos (8.490 "
        "linhas acima, 391 abaixo). Só o agregado é servido.",
        "IND-Q-09",
    ),
    *_grupo(
        "cursos",
        Papel.QUARENTENA,
        "situacao",
        "qt_sit_trancada qt_sit_desvinculado qt_sit_transferido qt_sit_falecido",
        "INDICADORES.md IND-Q-02",
        "As situações não são subconjunto das matrículas (excedem qt_mat em 267.780 linhas) e "
        "evasão é conceito de coorte: não há denominador válido nesta base.",
        "IND-Q-02",
    ),
]

# --- Municipio (7) e populacao (6) ----------------------------------------------------------------

_MUNICIPIO: list[Coluna] = [
    *_grupo(
        "municipio",
        Papel.CHAVE,
        "chave_municipal",
        "codigo_municipio_dv codigo_municipio",
        "JOIN_STRATEGY.md (7 dígitos para o Censo; 6 dígitos para a população)",
    ),
    *_grupo(
        "municipio",
        Papel.IRRELEVANTE,
        "territorio",
        "nome_municipio",
        "DATA_DICTIONARY.md",
        _M_NOME,
    ),
    *_grupo("municipio", Papel.DIMENSAO, "territorio", "cd_uf", "api/indicadores.py (CODIGO_UF)"),
    *_grupo(
        "municipio",
        Papel.DIMENSAO,
        "capital",
        "municipio_capital",
        f"{_INVENTARIO} (bloco capital)",
    ),
    *_grupo(
        "municipio",
        Papel.ESTRUTURAL,
        "geometria",
        "longitude latitude",
        "DATA_DICTIONARY.md (coordenadas do mapa; não são dimensão nem métrica)",
    ),
]

_POPULACAO: list[Coluna] = [
    *_grupo("populacao", Papel.ESTRUTURAL, "particao_ano", "ano", "INDICADORES.md IND-R-01"),
    *_grupo(
        "populacao",
        Papel.IRRELEVANTE,
        "territorio",
        "uf cod_uf nome_municipio",
        _INVENTARIO,
        "Redundantes com a tabela-ponte `municipio`: UF e nome vêm dela; a população só é "
        "alcançada por cod_municipio (6 dígitos) e ano.",
    ),
    *_grupo("populacao", Papel.CHAVE, "chave_municipal", "cod_municipio", "JOIN_STRATEGY.md"),
    *_grupo("populacao", Papel.METRICA, "populacao", "populacao", "INDICADORES.md IND-R-01"),
]

COLUNAS: tuple[Coluna, ...] = (*_IES, *_CURSOS, *_MUNICIPIO, *_POPULACAO)
