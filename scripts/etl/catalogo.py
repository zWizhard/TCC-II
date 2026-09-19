#!/usr/bin/env python3
"""Catalogo das tabelas copiadas do PostgreSQL do IESB para o DuckDB local (ADR-0003).

Escopo declarado como DADO, e nao espalhado em if/else pelos scripts, porque tres coisas
diferentes precisam concordar sobre ele: o ETL (o que copiar e em que ordem), o validador
(o que conferir) e o manifesto (o que faltou copiar). Uma lista so evita que a copia fique
parcial sem ninguem perceber.

Todos os numeros abaixo foram MEDIDOS no banco em 2026-09-05 e estao em docs/data/.
Nada aqui e estimativa: tabela sem medicao registra None, nunca um palpite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_ORIGEM = "public"

# Relativo a raiz do repositorio. O arquivo e regeravel e fica fora do git (.gitignore).
DESTINO_PADRAO = "data/analytics/censo_2024.duckdb"

MANIFESTO = "docs/data/ETL_MANIFEST.json"


@dataclass(frozen=True)
class Tabela:
    """Uma tabela do escopo, com o que se sabe dela na ORIGEM.

    `linhas_esperadas` e `somas_controle` sao a testemunha independente da copia: se o
    DuckDB divergir deles, a copia esta errada mesmo que o ETL tenha terminado sem excecao.
    """

    nome: str
    descricao: str
    # Chave natural verificada na origem — usada so para TESTAR unicidade na copia.
    # O ETL nao cria PK nem indice: constraint que a origem nao tem quebraria a fidelidade.
    chave_natural: tuple[str, ...]
    linhas_esperadas: int
    colunas_esperadas: int | None = None
    # expressao SQL -> valor esperado. Vale tanto no PostgreSQL quanto no DuckDB.
    somas_controle: dict[str, int] = field(default_factory=dict)
    # Quantas linhas a mais que a chave natural distinta a ORIGEM tem. > 0 significa
    # duplicata legitima da fonte, que a copia fiel deve reproduzir — nao e defeito da copia.
    duplicatas_conhecidas: int = 0
    observacao: str = ""


TABELAS: tuple[Tabela, ...] = (
    Tabela(
        nome="inep_educacao_superior_ies",
        descricao="Censo da Educacao Superior 2024 — cadastro das IES",
        chave_natural=("nu_ano_censo", "co_ies"),
        linhas_esperadas=2_561,
        colunas_esperadas=82,
        observacao="Unica coluna que admite NULL e qt_tec_total, e nela ha 0 nulos.",
    ),
    Tabela(
        nome="municipio",
        descricao="Municipios brasileiros com coordenadas — tabela-ponte territorial",
        chave_natural=("codigo_municipio_dv",),
        linhas_esperadas=5_599,
        observacao=(
            "5.571 municipios + 28 sentinelas (26 'Municipio Ignorado - <UF>', 9900000 e "
            "9999999). As sentinelas sao copiadas: filtrar e trabalho da consulta, nao do ETL."
        ),
    ),
    Tabela(
        nome="ibge_populacao_estimada",
        descricao="Populacao estimada do IBGE por municipio e ano (serie 2000+)",
        chave_natural=("ano", "cod_municipio"),
        linhas_esperadas=144_678,
        duplicatas_conhecidas=50,
        observacao=(
            "50 pares (ano, municipio) duplicados com valores divergentes em 2000-2020; "
            "2024 esta limpo. cod_municipio tem 6 digitos: exige municipio como ponte."
        ),
    ),
    Tabela(
        nome="inep_educacao_superior_cursos",
        descricao="Censo da Educacao Superior 2024 — cursos por municipio e dimensao",
        chave_natural=("nu_ano_censo", "co_curso", "co_municipio", "tp_dimensao"),
        linhas_esperadas=720_349,
        colunas_esperadas=223,
        # Medidas nacionais de 2024 (unico ano existente na tabela). Sao as somas de
        # controle da copia: batem no DuckDB ou a copia nao pode ser usada.
        somas_controle={
            "SUM(qt_curso)": 45_776,
            "SUM(qt_mat)": 10_227_266,
            "SUM(qt_ing)": 5_010_613,
            "SUM(qt_conc)": 1_333_988,
            "COUNT(DISTINCT co_curso)": 46_150,
        },
        observacao=(
            "Grain = curso x municipio x tp_dimensao, NAO um curso por linha. 609 MB, "
            "sem indice: todo filtro na origem e seq scan."
        ),
    ),
)

# Menores primeiro e cursos por ultimo: uma falha de ambiente (credencial, tipo fora do
# mapa, disco) aparece em segundos nas tabelas pequenas, antes de gastar a extracao das
# 720 mil linhas de cursos.
ORDEM_DE_CARGA: tuple[str, ...] = (
    "inep_educacao_superior_ies",
    "municipio",
    "ibge_populacao_estimada",
    "inep_educacao_superior_cursos",
)

POR_NOME: dict[str, Tabela] = {t.nome: t for t in TABELAS}

assert set(POR_NOME) == set(ORDEM_DE_CARGA), "ORDEM_DE_CARGA e TABELAS divergem"


def tabelas_em_ordem(nomes: list[str] | None = None) -> list[Tabela]:
    """Devolve as tabelas pedidas na ordem de carga; sem argumento, o escopo inteiro."""
    if nomes is None:
        return [POR_NOME[n] for n in ORDEM_DE_CARGA]
    escolhidas = set(nomes)
    return [POR_NOME[n] for n in ORDEM_DE_CARGA if n in escolhidas]
