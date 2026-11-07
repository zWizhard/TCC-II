"""Termos vedados e ambiguidades da camada semantica.

Termo vedado devolve uma RECUSA explicada, com a ficha da quarentena (Bloco C de
INDICADORES.md) — nunca um mapeamento. Ambiguidade e objeto de primeira classe: leituras
possiveis, magnitude medida da diferenca, pergunta ao usuario e `padrao` (None quando nao pode
ser resolvida em silencio).

Magnitudes medidas no DuckDB local em 2026-10-07 (`fontes.VERIFICACOES_CSV`) e
reconferidas contra a base em tests/test_semantica.py.
"""

from api.indicadores import (
    UF,
    UF_INFO,
    Categoria,
    Dimensao,
    Eixo,
    Nivel,
    Organizacao,
    Recorte,
    Rede,
)
from api.semantica.dimensoes import DIMENSOES_TERRITORIAIS, prop, ver
from api.semantica.fontes import VERIFICACOES_CSV
from api.semantica.modelos import Alvo, Ambiguidade, Leitura, Medida, TermoVedado, ValorMedido

_VERIFICACOES = VERIFICACOES_CSV


def metrica(id_: str) -> Alvo:
    return Alvo(tipo="metrica", id=id_)


def dimensao(id_: str) -> Alvo:
    return Alvo(tipo="dimensao", id=str(id_))


def valor(id_: str, v: str) -> Alvo:
    return Alvo(tipo="valor", id=str(id_), valor=str(v))


# --- termos vedados -------------------------------------------------------------------------------

TERMOS_VEDADOS: tuple[TermoVedado, ...] = (
    TermoVedado(
        id="variacao_temporal",
        nome="Evolução, tendência, crescimento",
        categoria="quarentena",
        termos=(
            *ver("evolução", "tendência", "crescimento", "queda"),
            *ver("série histórica", "ao longo dos anos"),
            *prop("aumento", "cresceu", "aumentou"),
        ),
        motivo=(
            "A base tem um único ano, 2024: é um retrato transversal. Nenhum indicador de "
            "variação temporal é possível, e esses termos estão vedados na plataforma."
        ),
        ficha="IND-Q-04",
        proveniencia="INDICADORES.md IND-Q-04",
    ),
    TermoVedado(
        id="taxa_de_conclusao",
        nome="Taxa de conclusão, de sucesso, eficiência",
        categoria="quarentena",
        termos=(
            *ver("taxa de conclusão", "taxa de sucesso", "eficiência"),
            *ver("concluintes por ingressante", "concluintes por matrícula"),
        ),
        motivo=(
            "Concluintes e ingressantes de 2024 pertencem a coortes diferentes observadas no "
            "mesmo ano; com um único ano não há como acompanhar uma turma. Qualquer razão entre "
            "eles seria lida como taxa de conclusão e estaria errada."
        ),
        ficha="IND-Q-01",
        alternativas=(metrica("concluintes"), metrica("ingressantes")),
        proveniencia="INDICADORES.md IND-Q-01",
    ),
    TermoVedado(
        id="evasao",
        nome="Evasão",
        categoria="quarentena",
        termos=(
            *ver("evasão", "taxa de evasão"),
            *ver("trancamento", "matrícula trancada"),
            *prop("abandono", "desistência"),
        ),
        motivo=(
            "Evasão é conceito de coorte e só há 2024; além disso as colunas de situação "
            "não são subconjunto das matrículas — excedem-nas em 267.780 linhas. "
            "Não há denominador válido nesta base."
        ),
        ficha="IND-Q-02",
        proveniencia="INDICADORES.md IND-Q-02",
    ),
    TermoVedado(
        id="aluno_por_docente",
        nome="Razão aluno/docente",
        categoria="quarentena",
        termos=(
            *ver("aluno por docente", "razão aluno docente", "aluno/docente"),
            *ver(
                "aluno por professor",
                "estudante por professor",
                "estudante por docente",
                "matrículas por docente",
                "matrículas por professor",
            ),
        ),
        motivo=(
            "O numerador está no grain de curso (local de oferta) e o denominador no grain de "
            "IES (sede); 93,5% das linhas de curso são polos EAD. Atribuir matrículas à sede "
            "fabricaria uma razão que o dado não sustenta."
        ),
        ficha="IND-Q-03",
        alternativas=(metrica("matriculas"), metrica("docentes")),
        proveniencia="INDICADORES.md IND-Q-03",
    ),
    TermoVedado(
        id="meso_microrregiao",
        nome="Mesorregião e microrregião",
        categoria="quarentena",
        termos=ver("mesorregião", "microrregião"),
        motivo=(
            "Os códigos de mesorregião e microrregião são locais à UF (15 códigos para 131 "
            "mesorregiões) e, na microrregião, nem o par (UF, código) identifica: agrupar funde "
            "estados ou regiões homônimas."
        ),
        ficha="IND-Q-05",
        alternativas=(
            valor("nivel_territorial", Nivel.UF),
            valor("nivel_territorial", Nivel.MUNICIPIO),
        ),
        proveniencia="INDICADORES.md IND-Q-05",
    ),
    TermoVedado(
        id="pib_densidade",
        nome="PIB e densidade populacional",
        categoria="quarentena",
        termos=(
            *ver("PIB", "densidade populacional"),
            *prop("densidade demográfica", "renda per capita"),
        ),
        motivo=(
            "PIB e densidade são contexto socioeconômico fora do escopo; a densidade é de 2010, "
            "e correlação com PIB seria lida como causalidade."
        ),
        ficha="IND-Q-07",
        alternativas=(metrica("matriculas_por_100_mil_habitantes"),),
        proveniencia="INDICADORES.md IND-Q-07",
    ),
    TermoVedado(
        id="comparacao_entre_recortes",
        nome="Razão entre recortes territoriais (sede × oferta)",
        categoria="quarentena",
        estrutural=True,
        motivo=(
            "Um número de sede e um de oferta respondem a perguntas diferentes (698 × 3.551 "
            "unidades territoriais): aparecem lado a lado, rotulados, e nunca são divididos um "
            "pelo outro."
        ),
        ficha="IND-Q-06",
        alternativas=(metrica("municipios_com_sede"), metrica("municipios_com_oferta")),
        regras=("nao_cruzar_recortes",),
        proveniencia="INDICADORES.md IND-Q-06; ADR-0004",
    ),
    TermoVedado(
        id="financiamento_por_tipo",
        nome="FIES, ProUni e tipos de financiamento como composição",
        categoria="quarentena",
        termos=(
            *ver("FIES", "ProUni"),
            *ver(
                "tipo de financiamento", "financiamento por tipo", "bolsa integral", "bolsa parcial"
            ),
        ),
        motivo=(
            "As subcolunas de financiamento se sobrepõem — a mesma matrícula pode ter mais de "
            "um instrumento — e excedem o total: FIES, ProUni e outros não formam composição. "
            "Só o agregado (IND-R-08) é servido."
        ),
        ficha="IND-Q-08",
        alternativas=(metrica("financiamento"),),
        proveniencia="INDICADORES.md IND-Q-08",
    ),
    TermoVedado(
        id="reserva_por_subtipo",
        nome="Cotas por subtipo",
        categoria="quarentena",
        termos=(
            *ver(
                "tipo de cota",
                "cota por tipo",
                "tipo de reserva de vagas",
                "cota racial",
                "cota social",
            ),
            *prop("PPI", "quilombola"),
        ),
        motivo=(
            "Os 12 subtipos de reserva somam 1.116.988 contra 648.225 e divergem nos dois "
            "sentidos (8.490 linhas acima, 391 abaixo): não são fatias de um todo. Só o "
            "agregado (IND-R-09) é servido."
        ),
        ficha="IND-Q-09",
        alternativas=(metrica("reserva_vagas"),),
        proveniencia="INDICADORES.md IND-Q-09",
    ),
    TermoVedado(
        id="ingresso_por_tipo_de_selecao",
        nome="Ingressos por tipo de seleção",
        categoria="quarentena",
        termos=(
            *ver("tipo de seleção", "vestibular", "Enem", "avaliação seriada"),
            *ver("seleção simplificada"),
        ),
        motivo=(
            "As colunas de tipo de seleção somam 4.646.792 contra 5.010.613 ingressos e divergem "
            "nos dois sentidos: um ingresso pode usar mais de um instrumento. Não é partição. A "
            "composição por tipo de vaga fecha e é servida."
        ),
        ficha="IND-Q-10",
        alternativas=(dimensao(Eixo.TIPO_INGRESSO),),
        proveniencia="INDICADORES.md IND-Q-10",
    ),
    TermoVedado(
        id="candidatos_por_vaga",
        nome="Candidatos por vaga, concorrência",
        categoria="denominacao_vedada",
        termos=(
            *ver("candidatos por vaga", "concorrência", "seletividade"),
            *ver("relação candidato vaga", "candidato/vaga"),
        ),
        motivo=(
            "A base registra inscrições, não pessoas: uma pessoa pode inscrever-se em vários "
            "cursos e instituições. 'Candidatos por vaga' é denominação vedada, e a razão não "
            "mede seletividade nem concorrência."
        ),
        ficha="IND-R-11",
        alternativas=(metrica("inscricoes_por_vaga"),),
        proveniencia="INDICADORES.md IND-R-11 e IND-D-07",
    ),
    TermoVedado(
        id="taxa_de_ocupacao",
        nome="Taxa de ocupação de vagas",
        categoria="denominacao_vedada",
        termos=(
            *ver("taxa de ocupação", "ocupação de vagas", "ociosidade"),
            *ver("vagas ociosas", "vagas não preenchidas"),
        ),
        motivo=(
            "A base não garante que os ingressos do ano venham das vagas do mesmo ano, nem que "
            "vaga não preenchida seja ociosidade: 'taxa de ocupação' foi recusada como nome."
        ),
        ficha="IND-R-10",
        alternativas=(metrica("ingressantes_por_vaga"),),
        proveniencia="INDICADORES.md IND-R-10",
    ),
    TermoVedado(
        id="taxa_de_escolarizacao",
        nome="Taxa de escolarização",
        categoria="denominacao_vedada",
        termos=ver("taxa de escolarização", "escolarização"),
        motivo=(
            "A base não tem a população em idade de cursar o ensino superior, e a matrícula é "
            "contada no local de oferta: a razão por habitante não é taxa de escolarização."
        ),
        ficha="IND-R-01",
        alternativas=(metrica("matriculas_por_100_mil_habitantes"),),
        proveniencia="INDICADORES.md IND-R-01",
    ),
    TermoVedado(
        id="turno",
        nome="Turno (diurno, noturno)",
        categoria="nao_servido",
        termos=ver("turno", "diurno", "noturno"),
        motivo=(
            "O turno só existe no presencial (em EAD é zero) e ainda não tem ficha em "
            "INDICADORES.md: é candidato futuro, não um indicador servido."
        ),
        regras=("turno_so_no_presencial",),
        proveniencia="INDICADORES.md, fato transversal de turno e pendências",
    ),
    TermoVedado(
        id="campus",
        nome="Campus e unidades da IES",
        categoria="nao_servido",
        termos=ver("campus", "campi"),
        motivo=(
            "A base não tem campus nem unidade acadêmica: a IES conta 1, no município da sede. "
            "O que existe por local é a oferta de cursos (inclui polos EAD)."
        ),
        ficha="IND-D-01",
        alternativas=(metrica("ies"), metrica("municipios_com_oferta")),
        proveniencia="INDICADORES.md IND-D-01",
    ),
)

# --- ambiguidades ---------------------------------------------------------------------------------


def _medida(id_: str, descricao: str, *valores: tuple[str, int, str | None]) -> Medida:
    return Medida(
        id=id_,
        descricao=descricao,
        valores=tuple(ValorMedido(rotulo=r, valor=v, leitura=lt) for r, v, lt in valores),
    )


_ORG = str(Eixo.ORGANIZACAO)
_REDE = str(Eixo.REDE)
_CAT = str(Eixo.CATEGORIA)
_DIM = str(Eixo.DIMENSAO)
_PUBLICAS_ESTRITAS = (
    Categoria.PUBLICA_FEDERAL,
    Categoria.PUBLICA_ESTADUAL,
    Categoria.PUBLICA_MUNICIPAL,
)
_EAD = (Dimensao.EAD_POLO, Dimensao.EAD_NACIONAL, Dimensao.EAD_EXTERIOR)

# Nomes de UF que tambem sao nome de municipio em `municipio` (medido em 2026-10-07).
UFS_HOMONIMAS: tuple[UF, ...] = (UF.AP, UF.ES, UF.GO, UF.MT, UF.PR, UF.RJ, UF.SP, UF.TO)

AMBIGUIDADES: tuple[Ambiguidade, ...] = (
    Ambiguidade(
        id="universidade",
        nome="'Universidade': IES em geral ou organização acadêmica",
        descricao=(
            "No uso informal, 'universidade' é qualquer instituição de ensino superior; na "
            "base, é uma das cinco organizações acadêmicas."
        ),
        gatilhos=ver("universidade"),
        leituras=(
            Leitura(
                id="ies_em_geral",
                descricao="Qualquer instituição de ensino superior (todas as organizações).",
                alvos=(metrica("ies"),),
            ),
            Leitura(
                id="organizacao_universidade",
                descricao="Só as IES de organização acadêmica 'Universidade'.",
                alvos=(metrica("ies"), valor(_ORG, Organizacao.UNIVERSIDADE)),
                resolve_se=(dimensao(_ORG),),
            ),
        ),
        medidas=(
            _medida(
                "ies",
                "IES",
                ("todas as IES", 2_561, "ies_em_geral"),
                ("organização = Universidade", 206, "organizacao_universidade"),
            ),
            _medida(
                "municipios_de_sede",
                "Municípios de sede com ao menos uma",
                ("ao menos 1 IES", 698, "ies_em_geral"),
                ("ao menos 1 Universidade", 130, "organizacao_universidade"),
            ),
            _medida(
                "municipios_com_mais_de_20",
                "Municípios de sede com mais de 20 ('quantos municípios possuem mais de 20 "
                "universidades')",
                ("mais de 20 IES", 17, "ies_em_geral"),
                ("mais de 20 Universidades", 0, "organizacao_universidade"),
            ),
            _medida(
                "matriculas",
                "Matrículas",
                ("todas as IES", 10_227_266, "ies_em_geral"),
                ("organização = Universidade", 5_420_049, "organizacao_universidade"),
            ),
        ),
        pergunta=(
            "Por 'universidade' você quer dizer qualquer instituição de ensino superior (2.561) "
            "ou só as de organização acadêmica 'Universidade' (206)?"
        ),
        regra_resolucao=(
            "Só se resolve se a pergunta citar 'organização acadêmica'. Quem escreve 'IES' ou "
            "'instituições' não dispara a ambiguidade."
        ),
        proveniencia=f"AI_ANALYST.md; {_VERIFICACOES} (bloco universidade)",
    ),
    Ambiguidade(
        id="faculdade",
        nome="'Faculdade': IES em geral ou organização acadêmica",
        descricao=(
            "Mesmo caso de 'universidade': informalmente qualquer IES; na base, a organização "
            "acadêmica 'Faculdade'."
        ),
        gatilhos=ver("faculdade"),
        leituras=(
            Leitura(
                id="ies_em_geral",
                descricao="Qualquer instituição de ensino superior.",
                alvos=(metrica("ies"),),
            ),
            Leitura(
                id="organizacao_faculdade",
                descricao="Só as IES de organização acadêmica 'Faculdade'.",
                alvos=(metrica("ies"), valor(_ORG, Organizacao.FACULDADE)),
                resolve_se=(dimensao(_ORG),),
            ),
        ),
        medidas=(
            _medida(
                "ies",
                "IES",
                ("todas as IES", 2_561, "ies_em_geral"),
                ("organização = Faculdade", 1_897, "organizacao_faculdade"),
            ),
        ),
        pergunta=(
            "Por 'faculdade' você quer dizer qualquer instituição de ensino superior (2.561) ou "
            "só as de organização acadêmica 'Faculdade' (1.897)?"
        ),
        regra_resolucao="Só se resolve se a pergunta citar 'organização acadêmica'.",
        proveniencia=f"{_VERIFICACOES} (bloco dominio: tp_organizacao_academica)",
    ),
    Ambiguidade(
        id="publica",
        nome="'Pública': rede ou categorias administrativas públicas",
        descricao=(
            "A rede 'Pública' da base inclui as 28 IES de categoria 'Especial'; as três "
            "categorias 'Pública Federal/Estadual/Municipal' não."
        ),
        gatilhos=ver("pública", "público"),
        leituras=(
            Leitura(
                id="rede_publica",
                descricao="Rede = 'Pública' (inclui as 28 IES de categoria Especial).",
                alvos=(valor(_REDE, Rede.PUBLICA),),
                resolve_se=(dimensao(_REDE),),
            ),
            Leitura(
                id="categorias_publicas",
                descricao="Categorias Pública Federal, Estadual e Municipal (sem as Especial).",
                alvos=tuple(valor(_CAT, c) for c in _PUBLICAS_ESTRITAS),
                resolve_se=(dimensao(_CAT),),
            ),
        ),
        medidas=(
            _medida(
                "ies",
                "IES",
                ("rede Pública", 317, "rede_publica"),
                ("três categorias Pública", 289, "categorias_publicas"),
            ),
            _medida(
                "matriculas",
                "Matrículas",
                ("rede Pública", 2_065_067, "rede_publica"),
                ("três categorias Pública", 2_019_667, "categorias_publicas"),
            ),
        ),
        pergunta=(
            "Por 'pública' você quer a rede pública como a base a registra (317 IES, inclui 28 "
            "de categoria Especial) ou só as federais, estaduais e municipais (289)?"
        ),
        regra_resolucao=(
            "'Rede pública' é o rótulo literal da rede e não dispara a ambiguidade; 'pública "
            "federal/estadual/municipal' são categorias e também não. 'Pública' sozinho só se "
            "resolve se a pergunta citar 'rede' ou 'categoria administrativa'."
        ),
        proveniencia=f"ADR-0007; {_VERIFICACOES} (bloco publica)",
    ),
    Ambiguidade(
        id="curso",
        nome="'Curso': cursos contabilizados, cursos com registro ou linhas",
        descricao=(
            "A tabela de cursos não tem uma linha por curso, e a base marca com qt_curso os "
            "cursos que contabiliza."
        ),
        gatilhos_itens=(metrica("cursos"),),
        leituras=(
            Leitura(
                id="cursos_contabilizados",
                descricao="Cursos contabilizados pela base na oferta (IND-D-02).",
                alvos=(metrica("cursos"),),
            ),
            Leitura(
                id="cursos_com_registro",
                descricao=(
                    "Códigos de curso distintos: inclui os 374 Programas básicos sem marcador. "
                    "Conceito distinto, não servido."
                ),
                servida=False,
            ),
            Leitura(
                id="linhas",
                descricao="Linhas curso × município × dimensão. Nunca é contagem de cursos.",
                servida=False,
            ),
        ),
        medidas=(
            _medida(
                "contagem",
                "Contagem nacional",
                ("cursos contabilizados", 45_776, "cursos_contabilizados"),
                ("códigos de curso distintos", 46_150, "cursos_com_registro"),
                ("linhas da tabela", 720_349, "linhas"),
            ),
        ),
        pergunta=(
            "A contagem de cursos disponível é a dos cursos contabilizados pela base (45.776); "
            "ela não inclui os 374 'Programas básicos'. Serve?"
        ),
        padrao="cursos_contabilizados",
        justificativa_padrao=(
            "Regra de domínio 1 de AI_ANALYST.md e ficha IND-D-02: contar cursos é "
            "a soma do marcador de curso; o outro conceito não é servido."
        ),
        regra_resolucao=(
            "Dispara quando a contagem de cursos entra no contexto; resolve pelo padrão, e a "
            "resposta declara que são 'cursos contabilizados', não 'todos os cursos'."
        ),
        proveniencia=f"INDICADORES.md IND-D-02; {_VERIFICACOES} (bloco curso)",
    ),
    Ambiguidade(
        id="ead",
        nome="'EAD': modalidade inteira, só polo ou só a dimensão nacional",
        descricao=(
            "A EAD está repartida em três dimensões de oferta que medem coisas diferentes: "
            "matrícula e contagem de curso de EAD nunca coexistem na mesma dimensão."
        ),
        gatilhos=(
            *ver("EAD", "a distância", "educação a distância", "ensino a distância"),
            *ver("curso a distância", "online"),
        ),
        leituras=(
            Leitura(
                id="modalidade_inteira",
                descricao="As três dimensões de EAD: polo, 'somente nível Brasil' e exterior.",
                alvos=tuple(valor(_DIM, d) for d in _EAD),
            ),
            Leitura(
                id="so_polo",
                descricao=(
                    "Só a dimensão de polo: a única de EAD com município, UF e região; tem as "
                    "matrículas, os ingressos e os concluintes."
                ),
                alvos=(valor(_DIM, Dimensao.EAD_POLO),),
                resolve_se=(valor(_DIM, Dimensao.EAD_POLO),),
            ),
            Leitura(
                id="so_nacional",
                descricao=(
                    "Só a dimensão 'somente nível Brasil': tem o marcador de curso, as vagas e "
                    "as inscrições da EAD, sem território."
                ),
                alvos=(valor(_DIM, Dimensao.EAD_NACIONAL),),
            ),
        ),
        medidas=(
            _medida(
                "matriculas",
                "Matrículas EAD",
                ("modalidade inteira", 5_189_391, "modalidade_inteira"),
                ("só polo", 5_186_852, "so_polo"),
                ("só 'nível Brasil'", 0, "so_nacional"),
            ),
            _medida(
                "cursos",
                "Cursos EAD contabilizados",
                ("modalidade inteira", 11_297, "modalidade_inteira"),
                ("só polo", 0, "so_polo"),
                ("só 'nível Brasil'", 11_297, "so_nacional"),
            ),
            _medida(
                "vagas_sem_territorio",
                "Vagas EAD na dimensão sem território",
                ("só 'nível Brasil'", 18_583_348, "so_nacional"),
            ),
        ),
        pergunta=(
            "Em EAD, os dados estão em dimensões diferentes: matrículas, ingressos e concluintes "
            "ficam nos polos (5.186.852 matrículas, com município) e no exterior (2.539); a "
            "contagem de cursos (11.297), as vagas e as inscrições só existem no agregado "
            "nacional, sem território. Qual recorte de EAD você quer?"
        ),
        regra_resolucao=(
            "Resolve por termo se a pergunta citar 'polo'. Resolve por restrição quando a "
            "pergunta é territorial (região, UF, município): só o polo tem território — e, se "
            "a métrica não existe no polo (cursos, vagas, inscrições), a pergunta é inviável "
            "e é dito por quê. No nível Brasil nunca é resolvida em silêncio."
        ),
        proveniencia=f"INDICADORES.md, regra transversal 2 e IND-R-04; {_VERIFICACOES} (bloco ead)",
    ),
    Ambiguidade(
        id="recorte",
        nome="Recorte territorial: sede da IES ou local de oferta",
        descricao=(
            "O território de uma instituição, matrícula ou curso é a sede da IES ou o local de "
            "oferta (inclui polos EAD). São respostas diferentes."
        ),
        gatilhos_itens=(
            dimensao("recorte"),
            dimensao("nivel_territorial"),
            *(dimensao(d) for d in sorted(DIMENSOES_TERRITORIAIS)),
        ),
        leituras=(
            Leitura(
                id=Recorte.SEDE,
                descricao="Município de sede da IES (698 unidades territoriais).",
                alvos=(valor("recorte", Recorte.SEDE),),
                resolve_se=(valor("recorte", Recorte.SEDE),),
            ),
            Leitura(
                id=Recorte.OFERTA,
                descricao="Município de oferta do curso, inclusive polos EAD (3.551).",
                alvos=(valor("recorte", Recorte.OFERTA),),
                resolve_se=(valor("recorte", Recorte.OFERTA), valor(_DIM, Dimensao.EAD_POLO)),
            ),
        ),
        medidas=(
            _medida(
                "unidades_territoriais",
                "Unidades territoriais de nível municipal",
                ("com sede de IES", 698, Recorte.SEDE),
                ("com oferta de curso", 3_551, Recorte.OFERTA),
            ),
        ),
        pergunta=(
            "Você quer o território pela sede da instituição (698 municípios) ou pelo local "
            "onde os cursos são ofertados, incluindo polos EAD (3.551)?"
        ),
        padrao=Recorte.SEDE,
        justificativa_padrao=(
            "ADR-0004: o recorte é dimensão obrigatória, com padrão inicial 'sede' — sempre "
            "declarado na resposta."
        ),
        regra_resolucao=(
            "Nesta ordem: termo explícito ('sede'; 'oferta' ou 'polo'); restrição da métrica "
            "(as de IES só existem na sede, as de curso só na oferta); padrão 'sede'. Métricas "
            "de recortes diferentes na mesma pergunta ficam cada uma no seu, rotuladas."
        ),
        proveniencia=f"ADR-0004; {_VERIFICACOES} (bloco municipio)",
    ),
    Ambiguidade(
        id="capital",
        nome="'Capital': da sede ou do local de oferta",
        descricao=(
            "'Capital' é atributo do município de sede na tabela de IES e do município de "
            "oferta na tabela de cursos. Os 27 municípios são os mesmos; o que muda é o que se "
            "conta neles."
        ),
        gatilhos_itens=(dimensao("capital"),),
        leituras=(
            Leitura(
                id="capital_da_sede",
                descricao="IES com sede em capital.",
                alvos=(valor("recorte", Recorte.SEDE),),
                resolve_se=(valor("recorte", Recorte.SEDE),),
            ),
            Leitura(
                id="capital_da_oferta",
                descricao="Cursos e matrículas ofertados em capital.",
                alvos=(valor("recorte", Recorte.OFERTA),),
                resolve_se=(valor("recorte", Recorte.OFERTA),),
            ),
        ),
        medidas=(
            _medida("municipios", "Municípios designados como capital", ("capitais", 27, None)),
            _medida(
                "ies_com_sede_em_capital",
                "IES com sede em capital",
                ("IES", 919, "capital_da_sede"),
            ),
            _medida(
                "matriculas_ofertadas_em_capital",
                "Matrículas ofertadas em capital",
                ("matrículas", 3_794_080, "capital_da_oferta"),
            ),
        ),
        pergunta=(
            "'Em capitais' pela sede da instituição (919 IES) ou pelo local de oferta dos "
            "cursos (3.794.080 matrículas)?"
        ),
        regra_resolucao=(
            "Nunca bloqueia por si: segue o recorte territorial (da métrica ou o padrão), que é "
            "sempre declarado na resposta."
        ),
        proveniencia=f"{_VERIFICACOES} (bloco capital)",
    ),
    Ambiguidade(
        id="uf_ou_municipio",
        nome="Nome que é UF e também município",
        descricao=(
            "Oito nomes de UF são também nome de município (o município de São Paulo, o de "
            "Rio de Janeiro, Goiás-GO, Amapá-AP, Tocantins-MG, Paraná-RN, Mato Grosso-PB e "
            "Espírito Santo-RN)."
        ),
        gatilhos=tuple(s for uf in UFS_HOMONIMAS for s in ver(UF_INFO[uf][0])),
        leituras=(
            Leitura(
                id="uf",
                descricao="A unidade da federação.",
                alvos=tuple(valor("uf", uf) for uf in UFS_HOMONIMAS),
                resolve_se=(valor("nivel_territorial", Nivel.UF),),
            ),
            Leitura(
                id="municipio",
                descricao="O município de mesmo nome (a resolver pelo código IBGE).",
                alvos=(dimensao("municipio"),),
                resolve_se=(valor("nivel_territorial", Nivel.MUNICIPIO),),
            ),
        ),
        medidas=(
            _medida(
                "homonimos",
                "Nomes de UF que também são nome de município",
                ("nomes", len(UFS_HOMONIMAS), None),
            ),
        ),
        pergunta="Você se refere ao estado ou ao município de mesmo nome?",
        regra_resolucao=(
            "Só a palavra colada ao nome desambigua: 'estado de X'/'UF X' → UF; 'município "
            "de X'/'cidade de X' → município. 'Por município', 'municípios de X' e 'por "
            "estado' são nível de agregação e não desambiguam: fica pendente. A sigla em "
            "maiúsculas (SP) é sempre a UF e não dispara."
        ),
        proveniencia="municipio.nome_municipio × api/indicadores.py (UF_INFO), medido em 2026-10-07",
    ),
)
