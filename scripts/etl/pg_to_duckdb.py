#!/usr/bin/env python3
"""Copia FIEL das tabelas do escopo do PostgreSQL do IESB para um DuckDB local (ADR-0003).

Por que existe: `inep_educacao_superior_cursos` tem 609 MB e nenhum indice, e a conta do
projeto nao pode criar um. Cada agregacao vira seq scan no banco institucional. A camada
analitica local resolve isso, e o SQL gerado pelo LLM nunca mais toca a fonte oficial.

Principio inegociavel: a copia e integral e literal. Todas as colunas, todas as linhas,
tipos vindos da ORIGEM. Nenhuma agregacao, filtro, renomeacao, dedup ou "limpeza" acontece
aqui — inclusive as duplicatas conhecidas de `ibge_populacao_estimada` sao copiadas como
estao. Corrigir grain e trabalho da consulta; um ETL que "arruma" o dado destroi a
possibilidade de auditar a copia contra a origem.

COMO a copia e feita, e por que (medido em 2026-09-19 nesta maquina):

    motor do DuckDB, CREATE TABLE AS de 5M linhas ......... 0,16 s
    executemany, carga real de ies (2.561 x 82 col) ....... 869 celulas/s
    executemany, carga real de populacao (144.678 x 6) .... 677 celulas/s

Linha/s nao serve de comparacao aqui: o custo do executemany acompanha o numero de VALORES
vinculados, nao de linhas — as mesmas medicoes dao 10,6 e 112,9 linhas/s. Em celulas/s, a
faixa medida projetava de 65,9 h a 51,3 h para os 160.637.827 valores de cursos
(720.349 x 223), que por isso nunca chegou a ser carregado assim. A transferencia e
delegada a extensao `postgres` do DuckDB: ela le o PostgreSQL em C++ e materializa a tabela
sem que nenhum valor passe pelo interpretador. O Python aqui cuida so de metadados,
contagem e conferencia.

Duas conexoes, de proposito:
  - psycopg, com as travas de sessao da ADR-0002 (scripts/db/conexao.py): le schema,
    contagens e versao. E o caminho ja auditado.
  - DuckDB via extensao postgres: transporta o dado. A trava somente-leitura e imposta
    por PGOPTIONS (`default_transaction_read_only=on`) mais READ_ONLY no ATTACH, e e
    CONFERIDA no servidor antes de qualquer copia — nao se confia na configuracao, mede-se.

Credenciais vem do .env na raiz, sao passadas ao DuckDB apenas por variavel de ambiente do
libpq (NUNCA dentro de uma string SQL) e NUNCA sao impressas.

Uso:
    .venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py
    .venv/Scripts/python.exe scripts/etl/pg_to_duckdb.py --tabelas municipio,inep_educacao_superior_ies
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import catalogo
import duckdb
from catalogo import Tabela

RAIZ = Path(__file__).resolve().parents[2]

# Nao ha pacote instalavel no repositorio: rodando de scripts/etl, o sys.path nao inclui
# scripts/db. Sem isto, as travas da ADR-0002 teriam de ser reescritas aqui — exatamente a
# duplicacao que conexao.py existe para evitar.
sys.path.insert(0, str(RAIZ / "scripts" / "db"))

from conexao import carregar_env, conectar  # noqa: E402

# Travas que o backend recebe na conexao ABERTA PELO DUCKDB. A extensao nao executa os
# nossos SET, entao a trava viaja como opcao de inicializacao do libpq. O statement_timeout
# e generoso porque cursos sao 609 MB de seq scan; a trava read-only nao e negociavel.
PG_OPTIONS_ETL = "-c default_transaction_read_only=on -c statement_timeout=1800s"

# Timeout da conexao psycopg (metadados e COUNT(*)): COUNT(*) em cursos e seq scan de 609 MB.
ETL_STATEMENT_TIMEOUT = "30min"

ALIAS_ORIGEM = "pg_origem"

# Traducao pg -> duckdb ESPERADA. Desde que a extensao passou a criar as tabelas, este mapa
# deixou de gerar DDL e virou CONFERENCIA: dizemos que tipo a coluna deveria ter na copia e
# comparamos com o que ela tem. E uma checagem mais forte do que gerar o DDL nos mesmos,
# porque agora ha duas opinioes independentes sobre cada coluna.
MAPA_TIPOS: dict[str, str] = {
    "character": "VARCHAR",
    "character varying": "VARCHAR",
    "text": "VARCHAR",
    "smallint": "SMALLINT",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "real": "FLOAT",
    "double precision": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMP WITH TIME ZONE",
}

# DuckDB nao vai alem de DECIMAL(38, s).
PRECISAO_MAXIMA_DECIMAL = 38

# O que de fato quebra o projeto e a coluna mudar de CLASSE — `nu_ano_censo` virando inteiro
# faz todo filtro por '2024' devolver zero linha, em silencio. Largura diferente dentro da
# mesma classe (VARCHAR vs VARCHAR(4)) nao muda resultado de consulta e vira registro, nao
# parada. Classe diferente aborta.
CLASSES: dict[str, str] = {
    "VARCHAR": "texto",
    "TINYINT": "inteiro",
    "SMALLINT": "inteiro",
    "INTEGER": "inteiro",
    "BIGINT": "inteiro",
    "HUGEINT": "inteiro",
    "UTINYINT": "inteiro",
    "USMALLINT": "inteiro",
    "UINTEGER": "inteiro",
    "UBIGINT": "inteiro",
    "DECIMAL": "decimal",
    "FLOAT": "flutuante",
    "DOUBLE": "flutuante",
    "BOOLEAN": "booleano",
    "DATE": "data",
    "TIMESTAMP": "tempo",
    "TIMESTAMP WITH TIME ZONE": "tempo",
    "TIME": "tempo",
    "BLOB": "binario",
    "UUID": "texto",
}


@dataclass(frozen=True)
class Coluna:
    """Uma coluna como o information_schema da ORIGEM a descreve."""

    nome: str
    tipo_pg: str
    nulavel: bool
    precisao: int | None
    escala: int | None


def formatar(n: int) -> str:
    """Separador de milhar em pt-BR, so para o progresso no terminal ficar legivel."""
    return f"{n:,}".replace(",", ".")


def tipo_duckdb(tabela: str, coluna: Coluna) -> str:
    """Tipo que a coluna DEVERIA ter na copia, ou aborta se o tipo da origem for desconhecido."""
    if coluna.tipo_pg == "numeric":
        if coluna.precisao is None:
            return "DOUBLE"
        if coluna.precisao > PRECISAO_MAXIMA_DECIMAL:
            sys.exit(
                f"ERRO: {tabela}.{coluna.nome} e numeric({coluna.precisao},{coluna.escala or 0}) "
                f"e excede o DECIMAL maximo do DuckDB ({PRECISAO_MAXIMA_DECIMAL}). "
                "Converter para DOUBLE perderia digitos em silencio. Abortado."
            )
        return f"DECIMAL({coluna.precisao}, {coluna.escala or 0})"
    tipo = MAPA_TIPOS.get(coluna.tipo_pg)
    if tipo is None:
        sys.exit(
            f"ERRO: tipo sem traducao definida em {tabela}.{coluna.nome}: '{coluna.tipo_pg}'.\n"
            "Acrescente a regra em MAPA_TIPOS depois de conferir o tipo no banco. "
            "O ETL nao adivinha tipo."
        )
    return tipo


def classe(tipo: str) -> str:
    """Classe do tipo, ignorando largura e precisao. Tipo fora do mapa vira 'desconhecido'."""
    base = tipo.split("(")[0].strip().upper()
    return CLASSES.get(base, "desconhecido")


def ler_colunas(conn: Any, tabela: str) -> list[Coluna]:
    """Le o schema real da tabela na origem, na ordem de ordinal_position.

    A expectativa de tipo nasce daqui, e nao de uma lista escrita a mao, porque lista a mao
    envelhece: se a origem ganhar ou perder coluna, a conferencia acompanha.
    """
    sql = """
        SELECT column_name, data_type, is_nullable, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(sql, (catalogo.SCHEMA_ORIGEM, tabela))
        linhas = cur.fetchall()
    if not linhas:
        sys.exit(
            f"ERRO: tabela {catalogo.SCHEMA_ORIGEM}.{tabela} nao encontrada na origem "
            "(ou sem permissao de leitura). Abortado."
        )
    return [
        Coluna(nome=n, tipo_pg=t, nulavel=(nul == "YES"), precisao=p, escala=e)
        for n, t, nul, p, e in linhas
    ]


def contar_origem(conn: Any, tabela: str) -> int:
    """COUNT(*) na origem. Em cursos e um seq scan de 609 MB — e o preco de saber se a copia veio inteira."""
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{catalogo.SCHEMA_ORIGEM}"."{tabela}"')
        linha = cur.fetchone()
    return int(linha[0]) if linha else 0


def versao_postgres(conn: Any) -> str:
    """SHOW server_version, e nao version(): a segunda carrega dados do servidor que nao precisam ir para o manifesto."""
    with conn.cursor() as cur:
        cur.execute("SHOW server_version")
        linha = cur.fetchone()
    return f"PostgreSQL {linha[0]}" if linha else "A confirmar"


def anexar_origem(duck: duckdb.DuckDBPyConnection, env: dict[str, str]) -> None:
    """Anexa o PostgreSQL ao DuckDB em modo somente-leitura e CONFERE a trava no servidor.

    As credenciais viajam por variavel de ambiente do libpq, nunca dentro do SQL do ATTACH:
    string de conexao em SQL apareceria em mensagem de erro, em plano de consulta e no
    historico do DuckDB. Com PG* no ambiente do processo, o ATTACH recebe a string vazia.
    """
    os.environ["PGHOST"] = env["PGHOST"]
    os.environ["PGPORT"] = env.get("PGPORT", "5432")
    os.environ["PGDATABASE"] = env["PGDATABASE"]
    os.environ["PGUSER"] = env["PGUSER"]
    os.environ["PGPASSWORD"] = env["PGPASSWORD"]
    os.environ["PGSSLMODE"] = env.get("PGSSLMODE", "prefer")
    os.environ["PGOPTIONS"] = PG_OPTIONS_ETL

    duck.execute("INSTALL postgres")
    duck.execute("LOAD postgres")
    duck.execute(f"ATTACH '' AS {ALIAS_ORIGEM} (TYPE POSTGRES, READ_ONLY)")

    # Confere no SERVIDOR que a sessao aberta pela extensao esta somente-leitura. Sem esta
    # medicao, PGOPTIONS seria uma suposicao: basta o libpq ignorar a variavel para o ETL
    # passar a rodar numa sessao gravavel sem ninguem perceber.
    linha = duck.execute(
        f"SELECT * FROM postgres_query('{ALIAS_ORIGEM}', "
        "'SELECT current_setting(''transaction_read_only'')')"
    ).fetchone()
    obtido = str(linha[0]) if linha else "?"
    if obtido != "on":
        sys.exit(
            "ERRO: a sessao que o DuckDB abriu no PostgreSQL NAO ficou somente-leitura "
            f"(transaction_read_only = '{obtido}'). Abortado antes de qualquer copia."
        )
    print("   sessao da extensao conferida no servidor: transaction_read_only = on")


def conferir_tipos(
    duck: duckdb.DuckDBPyConnection, tabela: str, colunas: list[Coluna]
) -> list[dict[str, str]]:
    """Compara o tipo de cada coluna da copia com o tipo esperado a partir da origem.

    Divergencia de CLASSE aborta: texto que virou numero derruba zero a esquerda e faz todo
    filtro por '2024' devolver vazio. Divergencia so de largura fica registrada.
    """
    obtidos = {
        str(n): str(t)
        for n, t in duck.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
            [tabela],
        ).fetchall()
    }
    divergencias: list[dict[str, str]] = []
    erros: list[str] = []
    for c in colunas:
        esperado = tipo_duckdb(tabela, c)
        obtido = obtidos.get(c.nome)
        if obtido is None:
            erros.append(f"{c.nome}: ausente na copia")
            continue
        # Sem espaco: DuckDB imprime DECIMAL(15,7) e o mapa monta DECIMAL(15, 7). Tratar
        # isso como divergencia encheria o manifesto de achado que nao existe.
        if obtido.upper().replace(" ", "") == esperado.upper().replace(" ", ""):
            continue
        if classe(obtido) != classe(esperado):
            erros.append(
                f"{c.nome}: origem {c.tipo_pg} (classe {classe(esperado)}) virou "
                f"{obtido} (classe {classe(obtido)})"
            )
            continue
        divergencias.append(
            {"coluna": c.nome, "origem": c.tipo_pg, "esperado": esperado, "obtido": obtido}
        )
    if erros:
        sys.exit(
            f"ERRO: a copia de {tabela} mudou a classe de {len(erros)} coluna(s):\n  "
            + "\n  ".join(erros)
            + "\nA copia nao e fiel. Abortado."
        )
    return divergencias


def conferir_nao_nulos(duck: duckdb.DuckDBPyConnection, tabela: str, colunas: list[Coluna]) -> int:
    """Conta linhas com NULL em coluna que a ORIGEM declara NOT NULL.

    CREATE TABLE AS nao carrega constraint, entao a nulidade declarada na origem deixa de
    ser imposta na copia. Em vez de recriar a constraint, mede-se o dado: constraint garante
    o futuro, a medicao prova o presente — e e o presente que vai virar numero do TCC.
    """
    obrigatorias = [c.nome for c in colunas if not c.nulavel]
    if not obrigatorias:
        return 0
    condicao = " OR ".join(f'"{n}" IS NULL' for n in obrigatorias)
    linha = duck.execute(f'SELECT COUNT(*) FROM "{tabela}" WHERE {condicao}').fetchone()
    return int(linha[0]) if linha else 0


def copiar(
    conn: Any,
    duck: duckdb.DuckDBPyConnection,
    tabela: Tabela,
) -> dict[str, Any]:
    """Copia uma tabela inteira da origem para o DuckDB e devolve as evidencias da carga.

    A transferencia e um CREATE TABLE AS sobre a tabela anexada: o dado vai do PostgreSQL
    ao arquivo local dentro do DuckDB, em C++. CREATE OR REPLACE torna a carga idempotente
    — rodar de novo nao acumula linha nem exige apagar o arquivo na mao.
    """
    colunas = ler_colunas(conn, tabela.nome)
    print(f"\n== {tabela.nome} ({len(colunas)} colunas)")

    linhas_origem = contar_origem(conn, tabela.nome)
    print(f"   origem: {formatar(linhas_origem)} linhas")
    if linhas_origem != tabela.linhas_esperadas:
        # Nao aborta: a origem pode ter sido atualizada. Mas fica registrado no manifesto,
        # porque as somas de controle do TCC foram medidas com a contagem antiga.
        print(
            f"   ATENCAO: catalogo esperava {formatar(tabela.linhas_esperadas)} linhas. "
            "A divergencia vai para o manifesto."
        )

    inicio = datetime.now()
    duck.execute(
        f'CREATE OR REPLACE TABLE "{tabela.nome}" AS '
        f'SELECT * FROM {ALIAS_ORIGEM}."{catalogo.SCHEMA_ORIGEM}"."{tabela.nome}"'
    )
    segundos = (datetime.now() - inicio).total_seconds()

    linha = duck.execute(f'SELECT COUNT(*) FROM "{tabela.nome}"').fetchone()
    linhas_copia = int(linha[0]) if linha else 0
    taxa = linhas_copia / segundos if segundos > 0 else 0
    print(f"   copiadas {formatar(linhas_copia)} linhas em {segundos:.1f}s ({taxa:,.0f} linhas/s)")
    if linhas_copia != linhas_origem:
        sys.exit(
            f"ERRO: {tabela.nome} tem {formatar(linhas_copia)} linhas na copia e "
            f"{formatar(linhas_origem)} na origem. A copia esta incompleta. Abortado."
        )

    divergencias = conferir_tipos(duck, tabela.nome, colunas)
    if divergencias:
        print(f"   tipos: {len(divergencias)} coluna(s) com largura diferente, mesma classe")
    else:
        print("   tipos: todas as colunas com o tipo esperado a partir da origem")

    nulos = conferir_nao_nulos(duck, tabela.nome, colunas)
    obrigatorias = sum(1 for c in colunas if not c.nulavel)
    if nulos:
        sys.exit(
            f"ERRO: {formatar(nulos)} linha(s) de {tabela.nome} tem NULL em coluna que a "
            "origem declara NOT NULL. A copia nao e fiel. Abortado."
        )
    print(f"   nulidade: 0 NULL nas {obrigatorias} colunas NOT NULL da origem")

    return {
        "situacao": "ok",
        "extraido_em": inicio.isoformat(timespec="seconds"),
        "segundos": round(segundos, 1),
        "linhas_origem": linhas_origem,
        "linhas_copia": linhas_copia,
        "colunas": len(colunas),
        "colunas_not_null_na_origem": obrigatorias,
        "linhas_com_null_indevido": nulos,
        "linhas_esperadas_catalogo": tabela.linhas_esperadas,
        "confere_com_catalogo": linhas_origem == tabela.linhas_esperadas,
        "tipos_divergentes_mesma_classe": divergencias,
    }


def tabelas_no_destino(duck: duckdb.DuckDBPyConnection) -> set[str]:
    """Tabelas que realmente existem no arquivo DuckDB, para o manifesto nao falar de fantasma."""
    linhas = duck.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    return {str(linha[0]) for linha in linhas}


def carregar_manifesto(caminho: Path, destino: Path) -> dict[str, Any]:
    """Le o manifesto anterior, se ele ainda descrever ESTE arquivo DuckDB.

    Manifesto de outro destino (ou de um arquivo que foi apagado) descreve uma copia que
    nao existe mais: reaproveita-lo faria uma carga parcial parecer completa.
    """
    vazio: dict[str, Any] = {"tabelas": {}}
    if not caminho.exists() or not destino.exists():
        return vazio
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return vazio
    if not isinstance(dados, dict) or dados.get("arquivo_destino") != _rotulo(destino):
        return vazio
    if not isinstance(dados.get("tabelas"), dict):
        dados["tabelas"] = {}
    return dados


def _rotulo(caminho: Path) -> str:
    """Caminho relativo a raiz do repositorio, com barra normal, para o manifesto nao carregar caminho de maquina."""
    alvo = caminho.resolve()
    rel = alvo.relative_to(RAIZ) if alvo.is_relative_to(RAIZ) else alvo
    return str(rel).replace("\\", "/")


def gravar_manifesto(
    caminho: Path,
    destino: Path,
    tabelas: dict[str, Any],
    versao_pg: str,
) -> None:
    """Grava o manifesto marcando explicitamente se a copia esta incompleta.

    E escrito a cada tabela concluida, e nao so no fim: se o ETL morrer no meio de cursos,
    o manifesto tem de mostrar 'em_carga' em vez de manter o registro da carga anterior,
    que descreveria uma copia que ja nao existe.
    """
    completas = [n for n, d in tabelas.items() if d.get("situacao") == "ok"]
    ausentes = [t.nome for t in catalogo.TABELAS if t.nome not in completas]
    conteudo = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "arquivo_destino": _rotulo(destino),
        "origem": {
            "sgbd": versao_pg,
            "schema": catalogo.SCHEMA_ORIGEM,
        },
        "duckdb_versao": duckdb.__version__,
        "transporte": "extensao postgres do DuckDB (ATTACH READ_ONLY + CREATE TABLE AS)",
        "copia_completa": not ausentes,
        "tabelas_ausentes_ou_incompletas": ausentes,
        "tabelas": tabelas,
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Copia integral das tabelas do Censo do PostgreSQL do IESB para o DuckDB local."
    )
    p.add_argument(
        "--tabelas",
        help="lista separada por virgula; sem isto, copia o escopo inteiro do catalogo",
    )
    p.add_argument("--saida", default=catalogo.DESTINO_PADRAO, help="arquivo .duckdb de destino")
    p.add_argument(
        "--recriar",
        action="store_true",
        help="apaga o arquivo de destino antes de carregar o escopo inteiro",
    )
    args = p.parse_args()

    nomes: list[str] | None = None
    if args.tabelas:
        nomes = [n.strip() for n in args.tabelas.split(",") if n.strip()]
        desconhecidas = [n for n in nomes if n not in catalogo.POR_NOME]
        if desconhecidas:
            sys.exit(
                f"ERRO: fora do catalogo: {', '.join(desconhecidas)}.\n"
                f"Tabelas do escopo: {', '.join(catalogo.ORDEM_DE_CARGA)}"
            )
    alvos = catalogo.tabelas_em_ordem(nomes)

    destino = Path(args.saida)
    if not destino.is_absolute():
        destino = RAIZ / destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    manifesto = RAIZ / catalogo.MANIFESTO

    # CREATE OR REPLACE nao devolve ao arquivo o espaco das tabelas substituidas: recarregar
    # o escopo por cima quase dobrou o arquivo (75,5 -> 144,3 MB em 2026-09-19). Recriar
    # devolve uma copia compacta. Exige o escopo inteiro: apagar o arquivo carregando so uma
    # tabela jogaria fora as outras tres, que so voltam com uma nova ida ao banco.
    if args.recriar:
        if nomes is not None:
            sys.exit("ERRO: --recriar apaga o arquivo inteiro e nao aceita --tabelas.")
        for arquivo in (destino, destino.with_suffix(destino.suffix + ".wal")):
            if arquivo.exists():
                arquivo.unlink()
                print(f"removido: {_rotulo(arquivo)}")

    env = carregar_env(RAIZ / ".env")
    # Lido ANTES de abrir o DuckDB: duckdb.connect cria o arquivo, e depois disso o teste
    # "o destino existe?" deixaria de distinguir uma copia anterior de um arquivo recem-nascido.
    anterior = carregar_manifesto(manifesto, destino)
    conn = conectar(env, statement_timeout=ETL_STATEMENT_TIMEOUT)
    duck = duckdb.connect(str(destino))
    try:
        versao_pg = versao_postgres(conn)
        # Sem host nem usuario no stdout: ambos ficam so no .env (docs/ENVIRONMENT.md).
        print(f"conectado (sessao somente-leitura) · origem {versao_pg}")
        print(f"destino {_rotulo(destino)} · DuckDB {duckdb.__version__}")
        anexar_origem(duck, env)
        print(f"tabelas: {', '.join(t.nome for t in alvos)}")

        # O manifesto so herda o que ESTA no arquivo: registro de carga anterior cuja tabela
        # sumiu do DuckDB descreveria uma copia que nao existe, e e assim que uma carga
        # parcial passa por completa.
        presentes = tabelas_no_destino(duck)
        registro: dict[str, Any] = {
            n: d for n, d in anterior.get("tabelas", {}).items() if n in presentes
        }
        # A tabela e marcada como em_carga ANTES de comecar: uma queda no meio deixa o
        # rastro no manifesto, em vez de manter o registro ok da carga anterior.
        for t in alvos:
            registro[t.nome] = {
                "situacao": "em_carga",
                "iniciado_em": datetime.now().isoformat(timespec="seconds"),
            }
        gravar_manifesto(manifesto, destino, registro, versao_pg)

        for t in alvos:
            registro[t.nome] = copiar(conn, duck, t)
            gravar_manifesto(manifesto, destino, registro, versao_pg)
    finally:
        duck.close()
        conn.close()

    faltando = [
        t.nome for t in catalogo.TABELAS if registro.get(t.nome, {}).get("situacao") != "ok"
    ]
    print(f"\nmanifesto: {_rotulo(manifesto)}")
    if faltando:
        print(f"COPIA INCOMPLETA — ainda sem carga: {', '.join(faltando)}")
    else:
        print("copia completa: as 4 tabelas do catalogo estao no arquivo.")
    print("Proximo passo: scripts/etl/validar_duckdb.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
