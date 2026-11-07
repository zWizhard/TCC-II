#!/usr/bin/env python3
"""Auditoria da Fase 12 (camada semantica do Analista IA): o lastro verificado de schema.

Le SOMENTE o DuckDB local (ADR-0003), aberto com read_only=True. Nao cria tabela, view nem indice.

Grava dois CSVs de evidencia em docs/data/raw/diagnostics/:

1. `2026-10-07_schema_duckdb.csv` — UMA LINHA POR COLUNA das quatro tabelas do escopo: tipo
   DuckDB (information_schema), distintos, nulos, vazios, familia e se a semantica da familia
   ja foi auditada.
2. `2026-10-07_semantica_verificacoes.csv` — bloco/teste/resultado/detalhe com o que a camada
   semantica vai afirmar: tipos das chaves, dominios literais das dimensoes, magnitude das
   ambiguidades ("universidade", "publica", "curso", "EAD", "municipio", "gratuito", "capital")
   e as quatro relacoes entre tabelas.

CRITERIO DA COLUNA `familia`
----------------------------
A familia e atribuida pela PRIMEIRA regra de `REGRAS` cujo padrao (regex, `fullmatch`) casa com o
nome da coluna, na tabela indicada. E uma ORGANIZACAO DO INVENTARIO POR NOME: nao afirma o que a
coluna significa. O que se sabe da semantica esta nas colunas `auditada` / `auditada_onde`:

- `sim`            — a familia foi medida numa fase anterior e FECHOU (dominio, particao ou
                     contencao), no lugar citado.
- `sim_nao_fechou` — foi medida e NAO fechou: esta na quarentena de INDICADORES.md. Existe, mas
                     nao pode ser usada como composicao/denominador.
- `parcial`        — so ha contagem/dominio documentados; nenhuma auditoria de semantica.
- `nao`            — nunca auditada. A camada semantica nao deve expor.

Coluna que nao casa com nenhuma regra recebe `nao_classificada` e o script acusa.

`n_vazios` = linhas com string vazia apos trim; so se aplica a VARCHAR (demais tipos: `n/a`).
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "data" / "analytics" / "censo_2024.duckdb"
DIAG = RAIZ / "docs" / "data" / "raw" / "diagnostics"
SAIDA_SCHEMA = DIAG / "2026-10-07_schema_duckdb.csv"
SAIDA = DIAG / "2026-10-07_semantica_verificacoes.csv"

sys.path.insert(0, str(RAIZ))
from api.indicadores import (  # noqa: E402  (catalogo: so enums e literais, sem I/O)
    MODALIDADE_DA_DIMENSAO,
    ROTULO_CATEGORIA,
    ROTULO_DIMENSAO,
    ROTULO_GRAU,
    ROTULO_ORGANIZACAO,
    ROTULO_REDE,
    Dimensao,
)

CURSOS = "inep_educacao_superior_cursos"
IES = "inep_educacao_superior_ies"
MUN = "municipio"
POP = "ibge_populacao_estimada"
ESPERADO = {IES: 82, CURSOS: 223, MUN: 7, POP: 6}

PRESENCIAL = ROTULO_DIMENSAO[Dimensao.PRESENCIAL]
POLO = ROTULO_DIMENSAO[Dimensao.EAD_POLO]
ANO = "nu_ano_censo = '2024'"
# Linha de cursos com territorio: 7 digitos exatos (exclui o literal 'Cursos a distância').
SETE = "regexp_full_match(co_municipio, '[0-9]{7}')"
OFERTA = f"{ANO} AND tp_dimensao IN ('{PRESENCIAL}', '{POLO}') AND {SETE}"
# Unidade territorial real de `municipio` (exclui 'Município Ignorado - UF' e os dois 99*).
REAL = "right(m.codigo_municipio_dv, 5) <> '00000' AND m.codigo_municipio_dv <> '9999999'"
PUBLICAS = "('Pública Federal', 'Pública Estadual', 'Pública Municipal')"

FAM = "2026-09-19_familias_metricas.csv (auditar_familias_metricas.py)"
FLUXO = "2026-10-07_fluxo.csv (auditar_fluxo.py)"
DIC = "DATA_DICTIONARY.md"
_FLUXO3 = "qt_(ing|mat|conc)"

# (familia, tabela ou None = qualquer, regex fullmatch, auditada, onde)
REGRAS: tuple[tuple[str, str | None, str, str, str], ...] = (
    # ---- comuns
    ("particao_ano", None, r"nu_ano_censo|ano", "sim", f"{DIC}: texto; Censo so 2024"),
    ("chave_entidade", None, r"co_ies|co_curso", "sim", "DATA_GRAIN.md / JOIN_STRATEGY.md"),
    (
        "chave_municipal",
        None,
        r"co_municipio(_ies)?|codigo_municipio(_dv)?|cod_municipio",
        "sim",
        "JOIN_STRATEGY.md (7 digitos; ponte de 6 digitos para a populacao)",
    ),
    (
        "territorio_meso_micro",
        IES,
        r"(co|no)_(meso|micro)rregiao_ies",
        "sim_nao_fechou",
        "INDICADORES.md IND-Q-05 (codigo local a UF)",
    ),
    (
        "capital",
        None,
        r"in_capital(_ies)?|municipio_capital",
        "parcial",
        f"{DIC} (dominio de in_capital*); coerencia entre as tres medida neste script",
    ),
    (
        "territorio",
        IES,
        r"(no|co)_regiao_ies|(no|sg|co)_uf_ies|no_municipio_ies",
        "sim",
        f"{DIC}; api/indicadores.py (UF, regiao conferidas em teste)",
    ),
    (
        "territorio",
        CURSOS,
        r"(no|co)_regiao|(no|sg|co)_uf|no_municipio",
        "sim",
        f"{DIC} (contaminacao 'Cursos a distância' em 8 colunas)",
    ),
    ("territorio", MUN, r"cd_uf", "sim", "2026-10-07_comparacoes.csv (codigo de UF identico)"),
    ("territorio", MUN, r"nome_municipio", "parcial", f"{DIC} (listada); usada so como rotulo"),
    ("territorio", POP, r"uf|cod_uf|nome_municipio", "parcial", f"{DIC} (listada); nao usada"),
    ("geometria", MUN, r"longitude|latitude", "sim", "2026-10-07_mapas.csv (auditar_mapas.py)"),
    ("populacao", POP, r"populacao", "sim", "INDICADORES.md IND-R-01; 2026-10-07_comparacoes.csv"),
    (
        "atributo_institucional",
        None,
        r"tp_organizacao_academica|tp_rede|ds_rede|tp_categoria_administrativa",
        "sim",
        f"{DIC}; literais em api/indicadores.py conferidos em teste",
    ),
    (
        "atributo_institucional",
        None,
        r"in_comunitaria|in_confessional",
        "parcial",
        f"{DIC} (dominio 0/1); sem indicador nem filtro na API",
    ),
    ("mantenedora", IES, r"(co|no)_mantenedora", "parcial", f"{DIC} (contagem de distintos)"),
    (
        "identificacao_textual_endereco",
        None,
        r"no_ies|sg_ies|ds_endereco_ies|nu_cep_ies|no_curso",
        "parcial",
        f"{DIC} (nao sao chave: homonimos e vazios medidos)",
    ),
    # ---- ies: metricas
    ("tecnicos_total", IES, r"qt_tec_total", "sim", f"INDICADORES.md IND-D-09; {FAM}"),
    (
        "tecnicos_escolaridade_sexo",
        IES,
        r"qt_tec_.+",
        "sim",
        f"{FAM}: particao exata de qt_tec_total; sem indicador publicado",
    ),
    (
        "biblioteca",
        IES,
        r"in_(acesso_.+|assina_outra_base|repositorio_institucional|busca_integrada"
        r"|servico_internet|participa_rede_social|catalogo_online)"
        r"|qt_(periodico|livro)_eletronico",
        "nao",
        "nunca auditada (so citada como 'infraestrutura de biblioteca' no dicionario)",
    ),
    (
        "docentes_total",
        IES,
        r"qt_doc_total|qt_doc_exe",
        "sim",
        f"INDICADORES.md IND-D-08; {FAM} (qt_doc_exe identica a qt_doc_total)",
    ),
    (
        "docentes_titulacao",
        IES,
        r"qt_doc_ex_(sem_grad|grad|esp|mest|dout)",
        "sim",
        f"INDICADORES.md IND-R-12; {FAM}: particao exata",
    ),
    (
        "docentes_decomposicao",
        IES,
        r"qt_doc_ex_.+",
        "sim",
        f"{FAM}: sexo, regime, faixa etaria, cor/raca, nacionalidade (particoes exatas) e "
        "deficiencia (contida); sem indicador publicado",
    ),
    # ---- cursos: atributos
    (
        "dimensao_oferta",
        CURSOS,
        r"tp_dimensao|tp_modalidade_ensino",
        "sim",
        "INDICADORES.md IND-R-04; api/indicadores.py",
    ),
    (
        "classificacao_cine",
        CURSOS,
        r"(co|no)_cine_(rotulo|area_geral)",
        "sim",
        "INDICADORES.md IND-R-06; api/indicadores.py (11 areas 1:1, 353 rotulos)",
    ),
    (
        "classificacao_cine",
        CURSOS,
        r"(co|no)_cine_area_(especifica|detalhada)",
        "parcial",
        f"{DIC} (so contagem de distintos: 39 e 89)",
    ),
    ("atributo_curso", CURSOS, r"tp_grau_academico", "sim", "INDICADORES.md IND-R-05"),
    (
        "atributo_curso",
        CURSOS,
        r"tp_nivel_academico|in_gratuito",
        "parcial",
        f"{DIC} (dominio); sem indicador nem filtro na API",
    ),
    # ---- cursos: metricas
    ("marcador_curso", CURSOS, r"qt_curso", "sim", f"INDICADORES.md IND-D-02; {FAM}"),
    ("vagas", CURSOS, r"qt_vg_.+", "sim", f"INDICADORES.md IND-D-06; {FAM}"),
    ("inscritos", CURSOS, r"qt_(inscrito|insc)_.+", "sim", f"INDICADORES.md IND-D-07; {FAM}"),
    ("metrica_total_fluxo", CURSOS, _FLUXO3, "sim", "INDICADORES.md IND-D-03/04/05"),
    (
        "turno",
        CURSOS,
        rf"{_FLUXO3}_(diurno|noturno)",
        "sim",
        f"{FAM}: particao exata so no presencial; sem indicador (candidato futuro)",
    ),
    ("perfil_sexo", CURSOS, rf"{_FLUXO3}_(fem|masc)", "sim", f"INDICADORES.md IND-R-07; {FLUXO}"),
    (
        "perfil_faixa_etaria",
        CURSOS,
        rf"{_FLUXO3}_(0_17|18_24|25_29|30_34|35_39|40_49|50_59|60_mais)",
        "sim",
        f"INDICADORES.md IND-R-07; {FLUXO}",
    ),
    (
        "perfil_cor_raca",
        CURSOS,
        rf"{_FLUXO3}_(branca|preta|parda|amarela|indigena|cornd)",
        "sim",
        f"INDICADORES.md IND-R-07; {FLUXO}",
    ),
    (
        "perfil_nacionalidade",
        CURSOS,
        rf"{_FLUXO3}_nac(bras|estrang)",
        "sim",
        f"INDICADORES.md IND-R-07; {FLUXO}",
    ),
    (
        "perfil_procedencia_escolar",
        CURSOS,
        rf"{_FLUXO3}_proc(escpublica|escprivada|naoinformada)",
        "sim",
        f"INDICADORES.md IND-R-07; {FLUXO}",
    ),
    (
        "ingresso_tipo_vaga",
        CURSOS,
        r"qt_ing_(vg_nova|vg_remanesc|vg_prog_especial|outra_forma|proc_seletivo)",
        "sim",
        f"{FLUXO}: particao exata de qt_ing; definicao oficial de cada tipo A confirmar",
    ),
    (
        "ingresso_tipo_selecao",
        CURSOS,
        r"qt_ing_(vestibular|enem|avaliacao_seriada|selecao_simplifica|egr|outro_tipo_selecao)",
        "sim_nao_fechou",
        "INDICADORES.md IND-Q-10",
    ),
    (
        "deficiencia",
        CURSOS,
        r"qt_aluno_deficiente|qt_(ing|mat|conc)_deficiente",
        "nao",
        "nunca auditada em cursos (so a de docentes foi)",
    ),
    (
        "financiamento_agregado",
        CURSOS,
        rf"{_FLUXO3}_financ",
        "sim",
        f"INDICADORES.md IND-R-08; {FAM}",
    ),
    (
        "financiamento_subtipo",
        CURSOS,
        rf"{_FLUXO3}_(financ_.+|fies|rpfies|nrpfies|prounii|prounip)",
        "sim_nao_fechou",
        "INDICADORES.md IND-Q-08 (subcolunas se sobrepoem)",
    ),
    (
        "reserva_vagas_agregado",
        CURSOS,
        rf"{_FLUXO3}_reserva_vaga",
        "sim",
        f"INDICADORES.md IND-R-09; {FAM}",
    ),
    (
        "reserva_vagas_subtipo",
        CURSOS,
        rf"{_FLUXO3}_rv.+",
        "sim_nao_fechou",
        "INDICADORES.md IND-Q-09",
    ),
    ("situacao", CURSOS, r"qt_sit_.+", "sim_nao_fechou", "INDICADORES.md IND-Q-02"),
    ("parfor", CURSOS, r"qt_((ing|mat|conc)_)?parfor", "nao", "INDICADORES.md, pendencias"),
    (
        "apoio_social",
        CURSOS,
        r"qt_((ing|mat|conc)_)?apoio_social",
        "nao",
        "INDICADORES.md, pendencias",
    ),
    (
        "ativ_extracurricular",
        CURSOS,
        r"qt_((ing|mat|conc)_)?ativ_extracurricular",
        "nao",
        "INDICADORES.md, pendencias",
    ),
    (
        "mob_academica",
        CURSOS,
        r"qt_((ing|mat|conc)_)?mob_academica",
        "nao",
        "INDICADORES.md, pendencias",
    ),
)

resultados: list[dict[str, str]] = []


def registrar(bloco: str, teste: str, resultado: str, detalhe: str = "") -> None:
    resultados.append({"bloco": bloco, "teste": teste, "resultado": resultado, "detalhe": detalhe})
    print(f"[{bloco}] {teste}\n    -> {resultado}" + (f"  ({detalhe})" if detalhe else ""))


def n(valor: float | None) -> str:
    return f"{int(valor or 0):,}".replace(",", ".")


def classificar(tabela: str, coluna: str) -> tuple[str, str, str]:
    for familia, alvo, padrao, auditada, onde in REGRAS:
        if alvo in (None, tabela) and re.fullmatch(padrao, coluna):
            return familia, auditada, onde
    return "nao_classificada", "nao", "sem regra"


def tentar(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """Executa um escalar e devolve o valor ou a classe do erro — para medir casts implicitos."""
    try:
        return f"executa -> {con.execute(sql).fetchone()[0]}"
    except duckdb.Error as erro:
        return f"ERRO {type(erro).__name__}: {str(erro).splitlines()[0][:140]}"


# ---------------------------------------------------------------------------- 1. inventario
def inventario(con: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    linhas: list[dict[str, str]] = []
    for tabela in (IES, CURSOS, MUN, POP):
        colunas = con.execute(
            """SELECT column_name, ordinal_position, data_type FROM information_schema.columns
               WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position""",
            [tabela],
        ).fetchall()
        medidas: dict[str, tuple[int, int, str]] = {}
        for i in range(0, len(colunas), 40):  # lotes: 223 COUNT(DISTINCT) de uma vez pesa
            lote = colunas[i : i + 40]
            partes = []
            for nome, _pos, tipo in lote:
                vazio = (
                    f"""COUNT(*) FILTER (WHERE trim("{nome}") = '')"""
                    if tipo == "VARCHAR"
                    else "NULL"
                )
                partes.append(
                    f"""COUNT(DISTINCT "{nome}"), COUNT(*) FILTER (WHERE "{nome}" IS NULL), {vazio}"""
                )
            valores = con.execute(f"SELECT {', '.join(partes)} FROM {tabela}").fetchone()
            for j, (nome, _pos, _tipo) in enumerate(lote):
                dist, nulos, vazios = valores[3 * j : 3 * j + 3]
                medidas[nome] = (dist, nulos, "n/a" if vazios is None else str(vazios))
        for nome, pos, tipo in colunas:
            familia, auditada, onde = classificar(tabela, nome)
            dist, nulos, vazios = medidas[nome]
            linhas.append(
                {
                    "tabela": tabela,
                    "coluna": nome,
                    "posicao": str(pos),
                    "tipo": tipo,
                    "n_distintos": str(dist),
                    "n_nulos": str(nulos),
                    "n_vazios": vazios,
                    "familia": familia,
                    "auditada": auditada,
                    "auditada_onde": onde,
                }
            )
    return linhas


def resumir_inventario(con: duckdb.DuckDBPyConnection, linhas: list[dict[str, str]]) -> None:
    por_tabela = Counter(linha["tabela"] for linha in linhas)
    for tabela, esperado in ESPERADO.items():
        total = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        registrar(
            "inventario",
            f"{tabela}: colunas e linhas",
            "CONFERE" if por_tabela[tabela] == esperado else "DIVERGE",
            f"colunas={por_tabela[tabela]} (esperado {esperado}) linhas={n(total)}",
        )
    registrar(
        "inventario",
        "total de colunas nas quatro tabelas",
        "CONFERE" if len(linhas) == sum(ESPERADO.values()) else "DIVERGE",
        f"{len(linhas)} (esperado {sum(ESPERADO.values())})",
    )
    sem = [f"{linha['tabela']}.{linha['coluna']}" for linha in linhas if linha["familia"] == "nao_classificada"]
    registrar("inventario", "colunas sem familia", str(len(sem)), "; ".join(sem))
    for tabela in ESPERADO:
        fam = Counter(linha["familia"] for linha in linhas if linha["tabela"] == tabela)
        registrar(
            "inventario",
            f"{tabela}: colunas por familia",
            f"{len(fam)} familias",
            "; ".join(f"{k}={v}" for k, v in sorted(fam.items())),
        )
    for status in ("sim", "sim_nao_fechou", "parcial", "nao"):
        fam = sorted(
            {f"{linha['tabela'].split('_')[-1]}.{linha['familia']}" for linha in linhas if linha["auditada"] == status}
        )
        qtd = sum(1 for linha in linhas if linha["auditada"] == status)
        registrar("inventario", f"auditada = {status}", f"{qtd} colunas", "; ".join(fam))
    tipos = Counter((linha["tabela"], linha["tipo"]) for linha in linhas)
    for tabela in ESPERADO:
        registrar(
            "inventario",
            f"{tabela}: tipos DuckDB",
            "; ".join(f"{t}={q}" for (tb, t), q in sorted(tipos.items()) if tb == tabela),
        )
    com_nulo = [f"{linha['tabela']}.{linha['coluna']}={linha['n_nulos']}" for linha in linhas if linha["n_nulos"] != "0"]
    registrar("inventario", "colunas com NULL", str(len(com_nulo)), "; ".join(com_nulo))
    com_vazio = [
        f"{linha['tabela']}.{linha['coluna']}={linha['n_vazios']}"
        for linha in linhas
        if linha["n_vazios"] not in ("0", "n/a")
    ]
    registrar("inventario", "colunas VARCHAR com string vazia", str(len(com_vazio)), "; ".join(com_vazio))
    nao_nulas = con.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema = 'main' AND is_nullable = 'NO'"""
    ).fetchone()[0]
    registrar(
        "inventario",
        "colunas declaradas NOT NULL no DuckDB",
        str(nao_nulas),
        "a restricao NOT NULL do PostgreSQL nao foi levada pelo ETL; a ausencia de NULL e medida",
    )


# ---------------------------------------------------------------------------- 2a. tipos
def tipos_e_chaves(con: duckdb.DuckDBPyConnection, linhas: list[dict[str, str]]) -> None:
    tipo = {(linha["tabela"], linha["coluna"]): linha["tipo"] for linha in linhas}
    registrar("tipos", "versao do DuckDB", duckdb.__version__)
    alvos = (
        (IES, "nu_ano_censo"), (CURSOS, "nu_ano_censo"), (IES, "co_ies"), (CURSOS, "co_ies"),
        (CURSOS, "co_curso"), (IES, "co_municipio_ies"), (CURSOS, "co_municipio"),
        (IES, "co_uf_ies"), (CURSOS, "co_uf"), (IES, "co_regiao_ies"), (CURSOS, "co_regiao"),
        (IES, "tp_rede"), (CURSOS, "tp_rede"), (IES, "ds_rede"),
        (IES, "in_comunitaria"), (IES, "in_confessional"),
        (CURSOS, "in_comunitaria"), (CURSOS, "in_confessional"),
        (IES, "in_capital_ies"), (CURSOS, "in_capital"), (CURSOS, "in_gratuito"),
        (CURSOS, "co_cine_area_geral"), (CURSOS, "co_cine_rotulo"),
        (MUN, "codigo_municipio_dv"), (MUN, "codigo_municipio"), (MUN, "cd_uf"),
        (MUN, "municipio_capital"), (POP, "ano"), (POP, "cod_municipio"), (POP, "cod_uf"),
        (POP, "populacao"),
    )  # fmt: skip
    for tabela, coluna in alvos:
        if tipo[(tabela, coluna)] == "VARCHAR":
            comp = con.execute(
                f"""SELECT length("{coluna}"), COUNT(*) FROM {tabela} GROUP BY 1 ORDER BY 1"""
            ).fetchall()
            detalhe = "comprimentos: " + "; ".join(f"{c} car.={n(q)}" for c, q in comp)
        else:
            lo, hi = con.execute(f"""SELECT MIN("{coluna}"), MAX("{coluna}") FROM {tabela}""").fetchone()
            detalhe = f"min={lo} max={hi}"
        registrar("tipos", f"{tabela}.{coluna}", tipo[(tabela, coluna)], detalhe)

    # Como o DuckDB se comporta quando o tipo do literal ou do outro lado nao confere.
    casos = (
        ("ies.nu_ano_censo (VARCHAR) = '2024'", f"SELECT COUNT(*) FROM {IES} WHERE nu_ano_censo = '2024'"),
        ("ies.nu_ano_censo (VARCHAR) = 2024 [inteiro]", f"SELECT COUNT(*) FROM {IES} WHERE nu_ano_censo = 2024"),
        ("ibge.ano (VARCHAR) = 2024 [inteiro]", f"SELECT COUNT(*) FROM {POP} WHERE ano = 2024"),
        ("ies.tp_rede (INTEGER) = 1", f"SELECT COUNT(*) FROM {IES} WHERE tp_rede = 1"),
        ("ies.tp_rede (INTEGER) = '1' [texto]", f"SELECT COUNT(*) FROM {IES} WHERE tp_rede = '1'"),
        ("ies.tp_rede (INTEGER) = 'Pública' [rotulo]", f"SELECT COUNT(*) FROM {IES} WHERE tp_rede = 'Pública'"),
        ("ies.in_comunitaria (SMALLINT) = 1", f"SELECT COUNT(*) FROM {IES} WHERE in_comunitaria = 1"),
        ("ies.in_comunitaria (SMALLINT) = '1' [texto]", f"SELECT COUNT(*) FROM {IES} WHERE in_comunitaria = '1'"),
        ("ies.in_comunitaria (SMALLINT) = 'Sim'", f"SELECT COUNT(*) FROM {IES} WHERE in_comunitaria = 'Sim'"),
        ("ies.co_regiao_ies (SMALLINT) = 3", f"SELECT COUNT(*) FROM {IES} WHERE co_regiao_ies = 3"),
        ("ies.co_regiao_ies (SMALLINT) = '3' [texto]", f"SELECT COUNT(*) FROM {IES} WHERE co_regiao_ies = '3'"),
        ("cursos.co_regiao (VARCHAR) = '3'", f"SELECT COUNT(*) FROM {CURSOS} WHERE co_regiao = '3'"),
        ("cursos.co_regiao (VARCHAR) = 3 [inteiro]", f"SELECT COUNT(*) FROM {CURSOS} WHERE co_regiao = 3"),
        ("cursos.co_uf (VARCHAR) = 35 [inteiro]", f"SELECT COUNT(*) FROM {CURSOS} WHERE co_uf = 35"),
        ("cursos.co_municipio (VARCHAR) = 3550308 [inteiro]", f"SELECT COUNT(*) FROM {CURSOS} WHERE co_municipio = 3550308"),
        ("ies.co_municipio_ies (VARCHAR) = 3550308 [inteiro]", f"SELECT COUNT(*) FROM {IES} WHERE co_municipio_ies = 3550308"),
        ("ies.co_municipio_ies (VARCHAR) = '3550308'", f"SELECT COUNT(*) FROM {IES} WHERE co_municipio_ies = '3550308'"),
        (
            "coluna a coluna: cursos.co_regiao (VARCHAR) = ies.co_regiao_ies (SMALLINT)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_regiao FROM {CURSOS}) c
                JOIN (SELECT DISTINCT co_regiao_ies FROM {IES}) i ON c.co_regiao = i.co_regiao_ies""",
        ),
        (
            "coluna a coluna, forma segura: c.co_regiao = CAST(i.co_regiao_ies AS VARCHAR)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_regiao FROM {CURSOS}) c
                JOIN (SELECT DISTINCT co_regiao_ies FROM {IES}) i
                  ON c.co_regiao = CAST(i.co_regiao_ies AS VARCHAR)""",
        ),
        (
            "coluna a coluna: cursos.co_uf (VARCHAR) = ies.co_uf_ies (VARCHAR)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_uf FROM {CURSOS}) c
                JOIN (SELECT DISTINCT co_uf_ies FROM {IES}) i ON c.co_uf = i.co_uf_ies""",
        ),
        (
            "coluna a coluna: cursos.co_ies (INTEGER) = ies.co_ies (SMALLINT)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_ies FROM {CURSOS}) c
                JOIN {IES} i ON c.co_ies = i.co_ies""",
        ),
        (
            "coluna a coluna: cursos.tp_rede (VARCHAR) = ies.tp_rede (INTEGER)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT tp_rede FROM {CURSOS}) c
                JOIN (SELECT DISTINCT tp_rede FROM {IES}) i ON c.tp_rede = i.tp_rede""",
        ),
        (
            "coluna a coluna: cursos.tp_rede (VARCHAR) = ies.ds_rede (VARCHAR)",
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT tp_rede FROM {CURSOS}) c
                JOIN (SELECT DISTINCT ds_rede FROM {IES}) i ON c.tp_rede = i.ds_rede""",
        ),
    )
    for rotulo, sql in casos:
        registrar("comparacao", rotulo, tentar(con, sql))


# ---------------------------------------------------------------------------- 2b. dominios
def dominios(con: duckdb.DuckDBPyConnection) -> None:
    catalogo: dict[tuple[str, str], tuple[str, set[str]]] = {
        (IES, "tp_organizacao_academica"): ("ROTULO_ORGANIZACAO", set(ROTULO_ORGANIZACAO.values())),
        (CURSOS, "tp_organizacao_academica"): ("ROTULO_ORGANIZACAO", set(ROTULO_ORGANIZACAO.values())),
        (IES, "tp_categoria_administrativa"): ("ROTULO_CATEGORIA", set(ROTULO_CATEGORIA.values())),
        (CURSOS, "tp_categoria_administrativa"): ("ROTULO_CATEGORIA", set(ROTULO_CATEGORIA.values())),
        (IES, "ds_rede"): ("ROTULO_REDE", set(ROTULO_REDE.values())),
        (CURSOS, "tp_rede"): ("ROTULO_REDE", set(ROTULO_REDE.values())),
        (CURSOS, "tp_dimensao"): ("ROTULO_DIMENSAO", set(ROTULO_DIMENSAO.values())),
        (CURSOS, "tp_modalidade_ensino"): ("MODALIDADE_DA_DIMENSAO", set(MODALIDADE_DA_DIMENSAO.values())),
        (CURSOS, "tp_grau_academico"): ("ROTULO_GRAU", set(ROTULO_GRAU.values())),
    }
    alvos = (
        (IES, ("tp_organizacao_academica", "tp_categoria_administrativa", "tp_rede", "ds_rede",
               "in_capital_ies", "in_comunitaria", "in_confessional")),
        (CURSOS, ("tp_dimensao", "tp_modalidade_ensino", "tp_grau_academico", "tp_nivel_academico",
                  "tp_rede", "tp_categoria_administrativa", "tp_organizacao_academica",
                  "in_gratuito", "in_capital", "in_comunitaria", "in_confessional")),
        (MUN, ("municipio_capital",)),
    )  # fmt: skip
    for tabela, colunas in alvos:
        for coluna in colunas:
            if tabela == CURSOS:
                grupos = con.execute(
                    f"""SELECT "{coluna}", typeof("{coluna}"), COUNT(*), CAST(SUM(qt_mat) AS BIGINT),
                               CAST(SUM(qt_curso) AS BIGINT)
                        FROM {tabela} WHERE {ANO} GROUP BY 1, 2 ORDER BY 3 DESC"""
                ).fetchall()
                detalhe = "; ".join(
                    f"{v!r}: linhas={n(q)} mat={n(m)} cursos={n(c)}" for v, _t, q, m, c in grupos
                )
            else:
                grupos = con.execute(
                    f"""SELECT "{coluna}", typeof("{coluna}"), COUNT(*) FROM {tabela}
                        GROUP BY 1, 2 ORDER BY 3 DESC"""
                ).fetchall()
                detalhe = "; ".join(f"{v!r}: linhas={n(q)}" for v, _t, q in grupos)
            valores = {str(g[0]) for g in grupos}
            if (tabela, coluna) in catalogo:
                nome, esperado = catalogo[(tabela, coluna)]
                if valores == esperado:
                    veredito = f"IDENTICO a api.indicadores.{nome}"
                else:
                    veredito = (
                        f"DIVERGE de {nome}: so na base={sorted(valores - esperado)} "
                        f"so no catalogo={sorted(esperado - valores)}"
                    )
            else:
                veredito = "sem literal no catalogo da API"
            registrar(
                "dominio",
                f"{tabela}.{coluna} ({grupos[0][1]})",
                f"{len(grupos)} valores; {veredito}",
                detalhe,
            )
    pares = set(
        con.execute(f"SELECT DISTINCT tp_dimensao, tp_modalidade_ensino FROM {CURSOS}").fetchall()
    )
    esperado = {(ROTULO_DIMENSAO[d], m) for d, m in MODALIDADE_DA_DIMENSAO.items()}
    registrar(
        "dominio",
        "pares (tp_dimensao, tp_modalidade_ensino) contra MODALIDADE_DA_DIMENSAO",
        "IDENTICO" if pares == esperado else "DIVERGE",
        f"{len(pares)} pares na base",
    )
    for rotulo, sql in (
        (
            "ies: (tp_rede, ds_rede, tp_categoria_administrativa)",
            f"""SELECT tp_rede, ds_rede, tp_categoria_administrativa, COUNT(*) FROM {IES}
                WHERE {ANO} GROUP BY ALL ORDER BY 1, 3""",
        ),
        (
            "cursos: (tp_rede, tp_categoria_administrativa) em linhas",
            f"""SELECT tp_rede, tp_categoria_administrativa, COUNT(*) FROM {CURSOS}
                WHERE {ANO} GROUP BY ALL ORDER BY 1, 2""",
        ),
    ):
        grupos = con.execute(sql).fetchall()
        registrar(
            "dominio",
            rotulo,
            f"{len(grupos)} combinacoes",
            "; ".join(" | ".join(str(v) for v in g[:-1]) + f" = {n(g[-1])}" for g in grupos),
        )
    for coluna in ("tp_organizacao_academica", "tp_categoria_administrativa", "in_comunitaria", "in_confessional"):
        diverge = con.execute(
            f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_ies, "{coluna}" AS v FROM {CURSOS}) c
                JOIN {IES} i ON i.co_ies = c.co_ies WHERE c.v <> i."{coluna}" """
        ).fetchone()[0]
        varia = con.execute(
            f"""SELECT COUNT(*) FROM (SELECT co_ies FROM {CURSOS} GROUP BY 1
                                      HAVING COUNT(DISTINCT "{coluna}") > 1)"""
        ).fetchone()[0]
        registrar(
            "dominio",
            f"{coluna}: cursos repete o valor da IES?",
            "SIM" if diverge == 0 and varia == 0 else "NAO",
            f"IES com mais de um valor em cursos={varia}; pares (IES, valor) divergentes de ies={diverge}",
        )
    diverge = con.execute(
        f"""SELECT COUNT(*) FROM (SELECT DISTINCT co_ies, tp_rede FROM {CURSOS}) c
            JOIN {IES} i ON i.co_ies = c.co_ies WHERE c.tp_rede <> i.ds_rede"""
    ).fetchone()[0]
    registrar("dominio", "cursos.tp_rede = ies.ds_rede para toda IES", "SIM" if diverge == 0 else "NAO", f"divergentes={diverge}")


# ---------------------------------------------------------------------------- 2c. universidade
def universidade(con: duckdb.DuckDBPyConnection) -> None:
    total, distintas, univ = con.execute(
        f"""SELECT COUNT(*), COUNT(DISTINCT co_ies),
                   COUNT(*) FILTER (WHERE tp_organizacao_academica = 'Universidade')
            FROM {IES} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "universidade",
        "IES no total x IES com tp_organizacao_academica = 'Universidade'",
        f"{n(total)} x {n(univ)}",
        f"linhas={n(total)} co_ies distintos={n(distintas)} razao={total / univ:.1f}x",
    )
    sede, sede_univ = con.execute(
        f"""SELECT COUNT(DISTINCT co_municipio_ies),
                   COUNT(DISTINCT co_municipio_ies) FILTER (WHERE tp_organizacao_academica = 'Universidade')
            FROM {IES} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "universidade",
        "municipios de sede com ao menos 1 IES x com ao menos 1 'Universidade'",
        f"{n(sede)} x {n(sede_univ)}",
        "recorte sede",
    )
    por_mun = con.execute(
        f"""SELECT i.co_municipio_ies, any_value(m.nome_municipio), any_value(i.sg_uf_ies), COUNT(*),
                   COUNT(*) FILTER (WHERE i.tp_organizacao_academica = 'Universidade')
            FROM {IES} i LEFT JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies
            WHERE i.{ANO} GROUP BY 1 ORDER BY 4 DESC"""
    ).fetchall()
    mais20 = [r for r in por_mun if r[3] > 20]
    mais20_univ = [r for r in por_mun if r[4] > 20]
    topo_univ = sorted(por_mun, key=lambda r: -r[4])[:5]
    registrar(
        "universidade",
        "'quantos municipios possuem mais de 20 universidades' — leitura IES em geral (sede)",
        str(len(mais20)),
        "; ".join(f"{r[1]}/{r[2]}={r[3]}" for r in mais20),
    )
    registrar(
        "universidade",
        "'quantos municipios possuem mais de 20 universidades' — leitura organizacao = 'Universidade' (sede)",
        str(len(mais20_univ)),
        "maiores: " + "; ".join(f"{r[1]}/{r[2]}={r[4]}" for r in topo_univ),
    )
    for limiar in (1, 5, 10):
        registrar(
            "universidade",
            f"municipios de sede com mais de {limiar} — IES em geral x 'Universidade'",
            f"{sum(1 for r in por_mun if r[3] > limiar)} x {sum(1 for r in por_mun if r[4] > limiar)}",
        )
    oferta = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE ies > 20), COUNT(*) FILTER (WHERE univ > 20), COUNT(*),
                   COUNT(*) FILTER (WHERE univ > 0), MAX(ies), MAX(univ)
            FROM (SELECT co_municipio, COUNT(DISTINCT co_ies) AS ies,
                         COUNT(DISTINCT co_ies) FILTER (WHERE tp_organizacao_academica = 'Universidade') AS univ
                  FROM {CURSOS} WHERE {OFERTA} GROUP BY 1)"""
    ).fetchone()
    registrar(
        "universidade",
        "mesma pergunta no recorte OFERTA (IES distintas com linha de curso no municipio, presencial + polo)",
        f"mais de 20 IES={n(oferta[0])}; mais de 20 'Universidade'={n(oferta[1])}",
        f"municipios com oferta={n(oferta[2])}; com oferta de ao menos 1 'Universidade'={n(oferta[3])}; "
        f"maximo de IES={oferta[4]}; maximo de 'Universidade'={oferta[5]}",
    )
    grupos = con.execute(
        f"""SELECT tp_organizacao_academica, COUNT(DISTINCT co_ies), CAST(SUM(qt_mat) AS BIGINT),
                   CAST(SUM(qt_curso) AS BIGINT)
            FROM {CURSOS} WHERE {ANO} GROUP BY 1 ORDER BY 3 DESC"""
    ).fetchall()
    mat_total = sum(g[2] for g in grupos)
    mat_univ = next(g[2] for g in grupos if g[0] == "Universidade")
    registrar(
        "universidade",
        "cursos: SUM(qt_mat) total x so organizacao = 'Universidade'",
        f"{n(mat_total)} x {n(mat_univ)} ({mat_univ / mat_total * 100:.2f}%)",
        "; ".join(f"{g[0]}: ies={n(g[1])} mat={n(g[2])} cursos={n(g[3])}" for g in grupos),
    )
    ies_org = con.execute(
        f"SELECT tp_organizacao_academica, COUNT(*) FROM {IES} WHERE {ANO} GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    registrar(
        "universidade",
        "ies por tp_organizacao_academica",
        f"{len(ies_org)} categorias",
        "; ".join(f"{o}={n(q)}" for o, q in ies_org),
    )


# ---------------------------------------------------------------------------- 2d. outras
def outras_ambiguidades(con: duckdb.DuckDBPyConnection) -> None:
    # --- publica
    rede, categ, especial, tp1 = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE ds_rede = 'Pública'),
                   COUNT(*) FILTER (WHERE tp_categoria_administrativa IN {PUBLICAS}),
                   COUNT(*) FILTER (WHERE tp_categoria_administrativa = 'Especial'),
                   COUNT(*) FILTER (WHERE tp_rede = 1)
            FROM {IES} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "publica",
        "IES: ds_rede = 'Pública' x categoria em (Federal, Estadual, Municipal)",
        f"{n(rede)} x {n(categ)}",
        f"diferenca={n(rede - categ)}; 'Especial'={n(especial)}; tp_rede = 1 -> {n(tp1)}",
    )
    r = con.execute(
        f"""SELECT CAST(SUM(qt_mat) FILTER (WHERE tp_rede = 'Pública') AS BIGINT),
                   CAST(SUM(qt_mat) FILTER (WHERE tp_categoria_administrativa IN {PUBLICAS}) AS BIGINT),
                   CAST(SUM(qt_mat) FILTER (WHERE tp_categoria_administrativa = 'Especial') AS BIGINT),
                   CAST(SUM(qt_curso) FILTER (WHERE tp_rede = 'Pública') AS BIGINT),
                   CAST(SUM(qt_curso) FILTER (WHERE tp_categoria_administrativa IN {PUBLICAS}) AS BIGINT),
                   CAST(SUM(qt_mat) AS BIGINT)
            FROM {CURSOS} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "publica",
        "matriculas: tp_rede = 'Pública' x categoria em (Federal, Estadual, Municipal)",
        f"{n(r[0])} x {n(r[1])}",
        f"diferenca={n(r[0] - r[1])} (matriculas em 'Especial'={n(r[2])}); "
        f"cursos: {n(r[3])} x {n(r[4])}; total de matriculas={n(r[5])}",
    )
    grupos = con.execute(
        f"""SELECT tp_rede, tp_categoria_administrativa, COUNT(DISTINCT co_ies),
                   CAST(SUM(qt_mat) AS BIGINT), CAST(SUM(qt_curso) AS BIGINT)
            FROM {CURSOS} WHERE {ANO} GROUP BY ALL ORDER BY 1, 2"""
    ).fetchall()
    registrar(
        "publica",
        "cursos: rede x categoria em IES, matriculas e cursos",
        f"{len(grupos)} combinacoes",
        "; ".join(f"{g[0]} | {g[1]}: ies={n(g[2])} mat={n(g[3])} cursos={n(g[4])}" for g in grupos),
    )

    # --- curso
    soma, distintos, linhas, pares = con.execute(
        f"""SELECT CAST(SUM(qt_curso) AS BIGINT), COUNT(DISTINCT co_curso), COUNT(*),
                   COUNT(DISTINCT (co_curso, co_municipio, tp_dimensao))
            FROM {CURSOS} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "curso",
        "SUM(qt_curso) x COUNT(DISTINCT co_curso) x COUNT(*)",
        f"{n(soma)} x {n(distintos)} x {n(linhas)}",
        f"(co_curso, co_municipio, tp_dimensao) distintos={n(pares)}; "
        f"cursos sem marcador={n(distintos - soma)}; linhas por curso contado={linhas / soma:.1f}",
    )
    nomes, rotulos = con.execute(
        f"SELECT COUNT(DISTINCT no_curso), COUNT(DISTINCT co_cine_rotulo) FROM {CURSOS} WHERE {ANO}"
    ).fetchone()
    registrar(
        "curso",
        "'curso' como nome: no_curso distintos x rotulos CINE distintos",
        f"{n(nomes)} x {n(rotulos)}",
        "no_curso nao identifica curso; rotulo CINE e classificacao do INEP",
    )

    # --- EAD
    grupos = con.execute(
        f"""SELECT tp_modalidade_ensino, tp_dimensao, COUNT(*), CAST(SUM(qt_mat) AS BIGINT),
                   CAST(SUM(qt_curso) AS BIGINT), COUNT(DISTINCT co_curso),
                   CAST(SUM(qt_ing) AS BIGINT), CAST(SUM(qt_vg_total) AS BIGINT),
                   COUNT(*) FILTER (WHERE {SETE})
            FROM {CURSOS} WHERE {ANO} GROUP BY ALL ORDER BY 1, 2"""
    ).fetchall()
    for g in grupos:
        registrar(
            "ead",
            f"{g[0]} | {g[1]}",
            f"mat={n(g[3])} SUM(qt_curso)={n(g[4])}",
            f"linhas={n(g[2])} co_curso distintos={n(g[5])} ing={n(g[6])} vagas={n(g[7])} "
            f"linhas com municipio de 7 digitos={n(g[8])}",
        )
    ead = [g for g in grupos if g[0] == "Curso a distância"]
    polo = next(g for g in grupos if g[1] == POLO)
    mat_total = sum(g[3] for g in grupos)
    registrar(
        "ead",
        "matriculas EAD: tp_modalidade_ensino = 'Curso a distância' x so a dimensao de polo",
        f"{n(sum(g[3] for g in ead))} x {n(polo[3])}",
        f"participacao no total: {sum(g[3] for g in ead) / mat_total * 100:.2f}% x "
        f"{polo[3] / mat_total * 100:.2f}% de {n(mat_total)}",
    )
    ead_distintos = con.execute(
        f"""SELECT COUNT(DISTINCT co_curso) FROM {CURSOS}
            WHERE {ANO} AND tp_modalidade_ensino = 'Curso a distância'"""
    ).fetchone()[0]
    registrar(
        "ead",
        "cursos EAD: SUM(qt_curso) na modalidade x so na dimensao de polo x co_curso distintos",
        f"{n(sum(g[4] for g in ead))} x {n(polo[4])} x {n(ead_distintos)}",
        "o marcador qt_curso da EAD esta na dimensao 'somente a nível Brasil', sem municipio",
    )
    em_duas = con.execute(
        f"""SELECT COUNT(*) FROM (SELECT co_curso FROM {CURSOS} WHERE {ANO} GROUP BY 1
                                  HAVING COUNT(DISTINCT tp_modalidade_ensino) > 1)"""
    ).fetchone()[0]
    registrar("ead", "cursos (co_curso) presentes nas duas modalidades", n(em_duas))

    # --- municipio
    r = con.execute(
        f"""WITH s AS (SELECT DISTINCT co_municipio_ies AS c FROM {IES} WHERE {ANO}),
                 o AS (SELECT co_municipio AS c,
                              bool_or(tp_dimensao = '{PRESENCIAL}') AS pres,
                              bool_or(tp_dimensao = '{POLO}') AS polo
                       FROM {CURSOS} WHERE {OFERTA} GROUP BY 1)
            SELECT (SELECT COUNT(*) FROM s), (SELECT COUNT(*) FROM o),
                   (SELECT COUNT(*) FROM o WHERE pres), (SELECT COUNT(*) FROM o WHERE polo),
                   (SELECT COUNT(*) FROM o WHERE pres AND polo),
                   (SELECT COUNT(*) FROM s JOIN o USING (c)),
                   (SELECT COUNT(*) FROM s ANTI JOIN o USING (c)),
                   (SELECT COUNT(*) FROM o ANTI JOIN s USING (c)),
                   (SELECT COUNT(*) FROM {MUN} m WHERE {REAL})"""
    ).fetchone()
    registrar(
        "municipio",
        "unidades distintas: sede de IES x local de oferta (presencial + polo)",
        f"{n(r[0])} x {n(r[1])}",
        f"oferta presencial={n(r[2])}; com polo EAD={n(r[3])}; com as duas={n(r[4])}; "
        f"sede e oferta={n(r[5])}; sede sem oferta={n(r[6])}; oferta sem sede={n(r[7])}; "
        f"unidades reais em `municipio`={n(r[8])}",
    )

    # --- gratuito
    grupos = con.execute(
        f"""SELECT in_gratuito, tp_rede, tp_categoria_administrativa, COUNT(*),
                   CAST(SUM(qt_curso) AS BIGINT), COUNT(DISTINCT co_curso), CAST(SUM(qt_mat) AS BIGINT)
            FROM {CURSOS} WHERE {ANO} GROUP BY ALL ORDER BY 1, 2, 3"""
    ).fetchall()
    for g in grupos:
        registrar(
            "gratuito",
            f"in_gratuito = {g[0]!r} | {g[1]} | {g[2]}",
            f"mat={n(g[6])}",
            f"linhas={n(g[3])} SUM(qt_curso)={n(g[4])} co_curso distintos={n(g[5])}",
        )

    def somar(i: int, gratuito: str | None, rede_alvo: str | None) -> int:
        return sum(
            g[i] for g in grupos if gratuito in (None, g[0]) and rede_alvo in (None, g[1])
        )

    for rotulo, i in (("linhas", 3), ("SUM(qt_curso)", 4), ("matriculas", 6)):
        registrar(
            "gratuito",
            f"in_gratuito = 'Sim' x tp_rede = 'Pública' — {rotulo}",
            f"{n(somar(i, 'Sim', None))} x {n(somar(i, None, 'Pública'))}",
            f"gratuito e publica={n(somar(i, 'Sim', 'Pública'))}; "
            f"gratuito e privada={n(somar(i, 'Sim', 'Privada'))}; "
            f"publica e nao gratuito={n(somar(i, 'Não', 'Pública'))}",
        )
    r = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE g = 1 AND sim), COUNT(*) FILTER (WHERE g = 1 AND NOT sim),
                   COUNT(*) FILTER (WHERE g > 1),
                   COUNT(*) FILTER (WHERE g = 1 AND sim AND publica),
                   COUNT(*) FILTER (WHERE g = 1 AND sim AND NOT publica),
                   COUNT(*) FILTER (WHERE g = 1 AND NOT sim AND publica),
                   COUNT(*) FILTER (WHERE publica)
            FROM (SELECT co_curso, COUNT(DISTINCT in_gratuito) AS g, bool_or(in_gratuito = 'Sim') AS sim,
                         bool_or(tp_rede = 'Pública') AS publica
                  FROM {CURSOS} WHERE {ANO} GROUP BY 1)"""
    ).fetchone()
    registrar(
        "gratuito",
        "por co_curso distinto: in_gratuito e constante? coincide com rede publica?",
        f"gratuitos={n(r[0])}; nao gratuitos={n(r[1])}; com os dois valores={n(r[2])}",
        f"gratuito e publica={n(r[3])}; gratuito e privada={n(r[4])}; "
        f"publica e nao gratuito={n(r[5])}; cursos de rede publica={n(r[6])}",
    )

    # --- capital
    for tabela, coluna, chave, filtro in (
        (IES, "in_capital_ies", "co_municipio_ies", ANO),
        (CURSOS, "in_capital", "co_municipio", ANO),
        (MUN, "municipio_capital", "codigo_municipio_dv", "TRUE"),
    ):
        grupos = con.execute(
            f"""SELECT "{coluna}", COUNT(*), COUNT(DISTINCT "{chave}") FROM {tabela}
                WHERE {filtro} GROUP BY 1 ORDER BY 2 DESC"""
        ).fetchall()
        registrar(
            "capital",
            f"dominio de {tabela}.{coluna}",
            f"{len(grupos)} valores",
            "; ".join(f"{v!r}: linhas={n(q)} municipios distintos={n(m)}" for v, q, m in grupos),
        )
    zero = con.execute(
        f"SELECT codigo_municipio_dv, nome_municipio FROM {MUN} WHERE municipio_capital NOT IN ('Sim', 'Não')"
    ).fetchall()
    registrar(
        "capital",
        "municipio.municipio_capital fora de 'Sim'/'Não'",
        str(len(zero)),
        "; ".join(f"{c} {nome!r}" for c, nome in zero),
    )
    r = con.execute(
        f"""WITH cap AS (SELECT codigo_municipio_dv AS c FROM {MUN} WHERE municipio_capital = 'Sim'),
                 s AS (SELECT co_municipio_ies AS c, MIN(in_capital_ies) AS lo, MAX(in_capital_ies) AS hi
                       FROM {IES} WHERE {ANO} GROUP BY 1),
                 o AS (SELECT co_municipio AS c, MIN(in_capital) AS lo, MAX(in_capital) AS hi
                       FROM {CURSOS} WHERE {ANO} AND {SETE} GROUP BY 1)
            SELECT (SELECT COUNT(*) FROM cap),
                   (SELECT COUNT(DISTINCT left(c, 2)) FROM cap),
                   (SELECT COUNT(*) FROM s WHERE lo <> hi),
                   (SELECT COUNT(*) FROM s WHERE (hi = 'Sim') <> (c IN (SELECT c FROM cap))),
                   (SELECT COUNT(*) FROM o WHERE lo <> hi),
                   (SELECT COUNT(*) FROM o WHERE (hi = 'Sim') <> (c IN (SELECT c FROM cap))),
                   (SELECT COUNT(*) FROM s WHERE hi = 'Sim'),
                   (SELECT COUNT(*) FROM o WHERE hi = 'Sim')"""
    ).fetchone()
    registrar(
        "capital",
        "as tres colunas de capital designam os mesmos municipios?",
        "SIM" if r[2] == r[3] == r[4] == r[5] == 0 else "NAO",
        f"municipio_capital = 'Sim': {r[0]} unidades em {r[1]} UFs; "
        f"sede com in_capital_ies = 'Sim': {r[6]} municipios (inconstantes={r[2]}, divergem de municipio={r[3]}); "
        f"oferta com in_capital = 'Sim': {r[7]} municipios (inconstantes={r[4]}, divergem de municipio={r[5]})",
    )
    r = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE in_capital_ies = 'Sim'),
                   (SELECT CAST(SUM(qt_mat) AS BIGINT) FROM {CURSOS} WHERE {ANO} AND in_capital = 'Sim'),
                   (SELECT CAST(SUM(qt_mat) AS BIGINT) FROM {CURSOS} WHERE {ANO} AND in_capital = 'Não'),
                   (SELECT CAST(SUM(qt_mat) AS BIGINT) FROM {CURSOS}
                    WHERE {ANO} AND in_capital NOT IN ('Sim', 'Não'))
            FROM {IES} WHERE {ANO}"""
    ).fetchone()
    registrar(
        "capital",
        "magnitude: IES com sede em capital; matriculas ofertadas em capital",
        f"IES={n(r[0])}; matriculas em capital={n(r[1])}",
        f"matriculas fora de capital={n(r[2])}; matriculas sem territorio (in_capital contaminado)={n(r[3])}",
    )


# ---------------------------------------------------------------------------- 2e. relacoes
def relacoes(con: duckdb.DuckDBPyConnection) -> None:
    # cursos -> ies (N:1). O JOIN aqui so conta linhas: nenhuma metrica de IES e somada.
    r = con.execute(
        f"""SELECT (SELECT COUNT(*) FROM {CURSOS}), (SELECT COUNT(DISTINCT co_ies) FROM {CURSOS}),
                   (SELECT COUNT(*) FROM {IES}), (SELECT COUNT(DISTINCT co_ies) FROM {IES}),
                   (SELECT COUNT(*) FROM {CURSOS} c JOIN {IES} i ON i.co_ies = c.co_ies),
                   (SELECT COUNT(*) FROM {CURSOS} c ANTI JOIN {IES} i ON i.co_ies = c.co_ies),
                   (SELECT COUNT(*) FROM {IES} i ANTI JOIN {CURSOS} c ON i.co_ies = c.co_ies),
                   (SELECT COUNT(*) FROM (SELECT co_curso FROM {CURSOS} GROUP BY 1
                                          HAVING COUNT(DISTINCT co_ies) > 1))"""
    ).fetchone()
    registrar(
        "relacao",
        "cursos -> ies | ON i.co_ies = c.co_ies (INTEGER = SMALLINT, alargamento numerico)",
        "N:1 VALIDA" if r[0] == r[4] and r[2] == r[3] and r[5] == r[6] == 0 else "FALHA",
        f"linhas de cursos antes={n(r[0])} depois={n(r[4])}; ies: linhas={n(r[2])} co_ies distintos={n(r[3])}; "
        f"co_ies distintos em cursos={n(r[1])}; linhas de cursos sem IES={n(r[5])}; IES sem curso={n(r[6])}; "
        f"co_curso com mais de um co_ies={n(r[7])}",
    )
    # cursos -> municipio
    r = con.execute(
        f"""SELECT (SELECT COUNT(*) FROM {CURSOS}), (SELECT COUNT(*) FROM {CURSOS} WHERE {SETE}),
                   (SELECT COUNT(DISTINCT co_municipio) FROM {CURSOS} WHERE {SETE}),
                   (SELECT COUNT(*) FROM {CURSOS} c JOIN {MUN} m ON m.codigo_municipio_dv = c.co_municipio
                    WHERE {SETE}),
                   (SELECT COUNT(*) FROM {CURSOS} c ANTI JOIN {MUN} m ON m.codigo_municipio_dv = c.co_municipio
                    WHERE {SETE}),
                   (SELECT COUNT(*) FROM {CURSOS} c JOIN {MUN} m ON m.codigo_municipio_dv = c.co_municipio
                    WHERE {SETE} AND NOT ({REAL})),
                   (SELECT COUNT(*) FROM {CURSOS} c JOIN {MUN} m ON m.codigo_municipio = c.co_municipio),
                   (SELECT COUNT(*) FROM {MUN}), (SELECT COUNT(DISTINCT codigo_municipio_dv) FROM {MUN})"""
    ).fetchone()
    sem = con.execute(
        f"""SELECT co_municipio, tp_dimensao, COUNT(*) FROM {CURSOS} WHERE NOT {SETE}
            GROUP BY ALL ORDER BY 3 DESC"""
    ).fetchall()
    registrar(
        "relacao",
        f"cursos -> municipio | ON m.codigo_municipio_dv = c.co_municipio WHERE {SETE}",
        "N:1 VALIDA" if r[1] == r[3] and r[4] == 0 and r[7] == r[8] else "FALHA",
        f"linhas de cursos={n(r[0])}; com 7 digitos antes={n(r[1])} depois={n(r[3])}; "
        f"municipios distintos={n(r[2])}; orfaos={n(r[4])}; linhas que caem em sentinela={n(r[5])}; "
        f"municipio: linhas={n(r[7])} codigos distintos={n(r[8])}; "
        f"JOIN pela chave de 6 digitos (codigo_municipio) devolve {n(r[6])} linhas",
    )
    registrar(
        "relacao",
        "cursos: linhas fora do padrao de 7 digitos em co_municipio",
        n(r[0] - r[1]),
        "; ".join(f"{v!r} | {d} = {n(q)}" for v, d, q in sem),
    )
    for coluna in ("co_uf", "sg_uf", "no_uf", "co_regiao", "no_regiao", "no_municipio", "in_capital"):
        q = con.execute(
            f"""SELECT COUNT(*) FILTER (WHERE NOT {SETE} AND "{coluna}" = 'Cursos a distância'),
                       COUNT(*) FILTER (WHERE {SETE} AND "{coluna}" = 'Cursos a distância')
                FROM {CURSOS}"""
        ).fetchone()
        registrar(
            "relacao",
            f"cursos.{coluna} = 'Cursos a distância' nas linhas sem municipio / nas linhas com municipio",
            f"{n(q[0])} / {n(q[1])}",
        )
    # ies -> municipio
    r = con.execute(
        f"""SELECT (SELECT COUNT(*) FROM {IES}),
                   (SELECT COUNT(*) FROM {IES} WHERE regexp_full_match(co_municipio_ies, '[0-9]{{7}}')),
                   (SELECT COUNT(DISTINCT co_municipio_ies) FROM {IES}),
                   (SELECT COUNT(*) FROM {IES} i JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies),
                   (SELECT COUNT(*) FROM {IES} i ANTI JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies),
                   (SELECT COUNT(*) FROM {IES} i JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies
                    WHERE NOT ({REAL})),
                   (SELECT COUNT(*) FROM {IES} i JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies
                    WHERE m.cd_uf <> i.co_uf_ies)"""
    ).fetchone()
    registrar(
        "relacao",
        "ies -> municipio | ON m.codigo_municipio_dv = i.co_municipio_ies",
        "N:1 VALIDA" if r[0] == r[1] == r[3] and r[4] == 0 else "FALHA",
        f"linhas de ies antes={n(r[0])} depois={n(r[3])}; com 7 digitos={n(r[1])}; "
        f"municipios de sede distintos={n(r[2])}; orfaos={n(r[4])}; em sentinela={n(r[5])}; "
        f"m.cd_uf diferente de i.co_uf_ies={n(r[6])}",
    )
    # municipio -> populacao
    r = con.execute(
        f"""SELECT (SELECT COUNT(*) FROM {MUN}), (SELECT COUNT(*) FROM {MUN} m WHERE {REAL}),
                   (SELECT COUNT(*) FROM {MUN} m WHERE NOT ({REAL})),
                   (SELECT COUNT(*) FROM {POP} WHERE ano = '2024'),
                   (SELECT COUNT(DISTINCT cod_municipio) FROM {POP} WHERE ano = '2024'),
                   (SELECT COUNT(*) FROM {MUN} m JOIN {POP} p
                      ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024' WHERE {REAL}),
                   (SELECT COUNT(*) FROM {MUN} m ANTI JOIN {POP} p
                      ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024' WHERE {REAL}),
                   (SELECT COUNT(*) FROM {POP} p ANTI JOIN (SELECT * FROM {MUN} m WHERE {REAL}) m
                      ON p.cod_municipio = m.codigo_municipio WHERE p.ano = '2024'),
                   (SELECT COUNT(*) FROM {MUN} m JOIN {POP} p
                      ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024' WHERE NOT ({REAL})),
                   (SELECT COUNT(*) FROM {MUN} m JOIN {POP} p ON p.cod_municipio = m.codigo_municipio
                    WHERE {REAL}),
                   (SELECT COUNT(*) FROM {MUN} m JOIN {POP} p
                      ON p.cod_municipio = m.codigo_municipio_dv AND p.ano = '2024'),
                   (SELECT COUNT(DISTINCT codigo_municipio) FROM {MUN} m WHERE {REAL}),
                   (SELECT COUNT(*) FROM {MUN} WHERE left(codigo_municipio_dv, 6) <> codigo_municipio),
                   (SELECT CAST(SUM(p.populacao) AS BIGINT) FROM {MUN} m JOIN {POP} p
                      ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024' WHERE {REAL})"""
    ).fetchone()
    registrar(
        "relacao",
        "municipio -> ibge_populacao_estimada | ON p.cod_municipio = m.codigo_municipio AND p.ano = '2024'"
        f" WHERE {REAL}",
        "1:1 VALIDA" if r[1] == r[5] == r[4] == r[3] and r[6] == r[7] == 0 else "FALHA",
        f"municipio: linhas={n(r[0])} reais={n(r[1])} sentinelas={n(r[2])} "
        f"codigos de 6 digitos distintos entre as reais={n(r[11])}; "
        f"populacao 2024: linhas={n(r[3])} cod_municipio distintos={n(r[4])}; "
        f"reais antes={n(r[1])} depois={n(r[5])}; reais sem populacao={n(r[6])}; "
        f"populacao 2024 sem municipio real={n(r[7])}; sentinelas que casam={n(r[8])}; "
        f"populacao somada={n(r[13])}",
    )
    registrar(
        "relacao",
        "municipio -> populacao: o que acontece sem os cuidados",
        f"sem filtro de ano: {n(r[9])} linhas (de {n(r[1])}); pela chave de 7 digitos: {n(r[10])} linhas",
        f"left(codigo_municipio_dv, 6) diferente de codigo_municipio em {n(r[12])} linhas de municipio",
    )
    dup = con.execute(
        f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE ano = '2024'), MIN(ano), MAX(ano)
            FROM (SELECT ano, cod_municipio FROM {POP} GROUP BY ALL HAVING COUNT(*) > 1)"""
    ).fetchone()
    anos = con.execute(f"SELECT ano, COUNT(*) FROM {POP} GROUP BY 1 ORDER BY 1").fetchall()
    registrar(
        "relacao",
        "ibge_populacao_estimada: pares (ano, cod_municipio) duplicados",
        f"{n(dup[0])} pares; em 2024: {n(dup[1])}",
        f"anos dos duplicados: de {dup[2]} a {dup[3]}; anos na tabela ({len(anos)}): "
        + ", ".join(a for a, _q in anos),
    )
    sent = con.execute(
        f"""SELECT COUNT(*) FILTER (WHERE right(codigo_municipio_dv, 5) = '00000'),
                   COUNT(*) FILTER (WHERE codigo_municipio_dv = '9999999'),
                   COUNT(*) FILTER (WHERE nome_municipio ILIKE 'Município Ignorado - %'),
                   (SELECT COUNT(*) FROM {IES} i JOIN {MUN} m ON m.codigo_municipio_dv = i.co_municipio_ies
                    WHERE NOT ({REAL}))
            FROM {MUN}"""
    ).fetchone()
    registrar(
        "relacao",
        f"sentinelas de municipio | NOT ({REAL})",
        f"{sent[0] + sent[1]} linhas",
        f"terminadas em 00000={sent[0]} (das quais 'Município Ignorado - UF'={sent[2]}); "
        f"9999999={sent[1]}; referenciadas pela sede de alguma IES={sent[3]}",
    )


def gravar(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def main() -> int:
    if not BANCO.is_file():
        print(f"Camada analitica ausente: {BANCO}", file=sys.stderr)
        return 1
    con = duckdb.connect(str(BANCO), read_only=True)

    tabelas = {t for (t,) in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    registrar(
        "inventario",
        "tabelas presentes no DuckDB",
        "CONFERE" if set(ESPERADO) <= tabelas else "FALTA TABELA",
        ", ".join(sorted(tabelas)),
    )
    schema = inventario(con)
    resumir_inventario(con, schema)
    tipos_e_chaves(con, schema)
    dominios(con)
    universidade(con)
    outras_ambiguidades(con)
    relacoes(con)

    gravar(SAIDA_SCHEMA, schema)
    gravar(SAIDA, resultados)
    print(f"\n{len(schema)} colunas gravadas em {SAIDA_SCHEMA.relative_to(RAIZ)}")
    print(f"{len(resultados)} testes gravados em {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
