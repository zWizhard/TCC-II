"""Validacao AST do SQL (SQLGlot, dialeto duckdb) — roda SEMPRE antes da execucao.

Defesa em profundidade: o SQL e gerado pelo backend, mas e conferido aqui como se fosse hostil.
A analise e feita sobre a ARVORE, nunca por busca de texto. A forma aceita e exatamente a que o
gerador (`sql.py`) emite: UM `SELECT ... FROM <uma tabela> [WHERE] [GROUP BY] [HAVING] [ORDER BY]
LIMIT`. Em ordem:

1. parse falho, vazio ou mais de um statement -> rejeita;
2. qualquer comentario -> rejeita (o gerador nao emite nenhum; comentario so serve para esconder);
3. nenhum no de DDL, DML ou comando em qualquer profundidade (denylist explicita);
4. raiz tem de ser SELECT; UNION e afins nao sao aceitos;
5. toda tabela e fisica e da allowlist, sem schema, catalogo nem alias; funcao de tabela
   (`read_csv`, `duckdb_tables`, `query`...) nao e tabela;
6. exatamente um SELECT e uma tabela: sem JOIN (nem produto cartesiano), sem subconsulta e sem
   CTE — o gerador nao usa nenhum deles, e cada um ja foi caminho de fuga (CTE homonima de view de
   sistema, alias que legitima coluna, produto cartesiano ate o timeout);
7. ALLOWLIST de nos: so as construcoes e funcoes que o gerador usa. O que nao esta na lista —
   `getenv`, janelas, LATERAL, OFFSET, OR, IN — cai aqui, mesmo que seja inofensivo;
8. toda coluna e uma coluna exposta da camada semantica, sem qualificador. Nome de alias so vale
   dentro do ORDER BY, e um alias nunca pode ter o nome de uma coluna fisica (senao
   `SELECT no_ies AS no_ies` legitimaria a coluna); `*` so dentro de COUNT;
9. todo parametro `$nome` tem valor vinculado;
10. LIMIT obrigatorio, inteiro e dentro do teto.

`CREATE TEMP TABLE` nao e barrado pelo motor em modo read-only (ver `api/db.py`): e barrado aqui.
"""

from collections.abc import Mapping
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from api.erros import SqlRejeitado
from api.semantica import CAMADA
from api.semantica.modelos import PAPEIS_EXPOSTOS

DIALETO = "duckdb"

# As quatro tabelas fisicas do escopo, pelo nome que a camada declara.
TABELAS_PERMITIDAS: frozenset[str] = frozenset(e.tabela for e in CAMADA.entidades)
COLUNAS_PERMITIDAS: frozenset[str] = frozenset(
    c.nome for c in CAMADA.colunas if c.papel in PAPEIS_EXPOSTOS
)


def _escopo(entidade: str | None) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """(tabelas, colunas expostas, colunas fisicas) da entidade; None = as quatro do escopo."""
    entidades = [e for e in CAMADA.entidades if entidade is None or e.id == entidade]
    if not entidades:
        raise ValueError(f"entidade desconhecida: {entidade!r}")
    ids = {e.id for e in entidades}
    fisicas = frozenset(c.nome for c in CAMADA.colunas if c.entidade in ids)
    expostas = frozenset(
        c.nome for c in CAMADA.colunas if c.entidade in ids and c.papel in PAPEIS_EXPOSTOS
    )
    return frozenset(e.tabela for e in entidades), expostas, fisicas


def _classes(*nomes: str) -> tuple[type[exp.Expression], ...]:
    """Classes do SQLGlot pelo nome. Nome que a versao instalada nao tem FALHA na importacao:

    uma denylist que encolhe em silencio numa troca de versao seria pior que nao subir.
    """
    classes = []
    for nome in nomes:
        classe = getattr(exp, nome, None)
        if not (isinstance(classe, type) and issubclass(classe, exp.Expression)):
            raise ImportError(f"sqlglot.exp.{nome} nao existe nesta versao do SQLGlot")
        classes.append(classe)
    return tuple(classes)


_PROIBIDOS = _classes(
    "Drop", "Delete", "Update", "Insert", "Alter", "AlterColumn", "TruncateTable", "Create",
    "Grant", "Revoke", "Merge", "Command", "Set", "SetItem", "Pragma", "Attach", "Detach", "Copy",
    "Use", "Execute", "Transaction", "Commit", "Rollback", "Into", "LoadData", "Export", "Install",
    "Describe", "Show", "Summarize", "Analyze", "Kill", "Lock", "Comment", "Cache", "Uncache",
    "Refresh", "Declare", "Put", "Get",
)  # fmt: skip

_FUNCOES = _classes(
    "Sum", "Count", "Coalesce", "Cast", "Nullif", "AnyValue", "RegexpFullMatch", "ArrayContains"
)
# Conectivos e operadores que o SQLGlot tambem modela como funcao.
_OPERADORES = _classes("And", "EQ", "GT", "GTE", "LT", "LTE", "Div", "Mul")
# Sem With, CTE, Subquery, Join nem TableAlias: o gerador nao os usa.
_ESTRUTURA = _classes(
    "Select", "From", "Where", "Group", "Having", "Order", "Ordered", "Limit", "Alias", "Column",
    "Identifier", "Table", "Literal", "Placeholder", "Star", "Distinct", "DataType", "IgnoreNulls",
)  # fmt: skip
_PERMITIDOS = frozenset((*_FUNCOES, *_OPERADORES, *_ESTRUTURA))


def _rejeitar(motivo: str, detalhe: str) -> SqlRejeitado:
    return SqlRejeitado(motivo, detalhe)


def validar_sql(
    sql: str,
    params: Mapping[str, Any],
    teto: int,
    entidade: str | None = None,
) -> None:
    """Levanta `SqlRejeitado` se o SQL nao for um unico SELECT dentro das allowlists.

    `entidade` restringe tabela e colunas as da entidade do plano (e o que o pipeline passa);
    sem ela valem as quatro tabelas do escopo e todas as colunas expostas.
    """
    tabelas, colunas, fisicas = _escopo(entidade)
    try:
        tokens = sqlglot.tokenize(sql, dialect=DIALETO)
        arvores = sqlglot.parse(sql, dialect=DIALETO)
    except SqlglotError as exc:
        raise _rejeitar("parse_falhou", type(exc).__name__) from exc
    if any(t.comments for t in tokens):
        raise _rejeitar("comentario", "comentários não são aceitos")
    if len(arvores) != 1 or arvores[0] is None:
        raise _rejeitar("multiplos_statements", f"{len(arvores)} statements")
    raiz = arvores[0]
    nos = list(raiz.walk())
    for no in nos:
        if isinstance(no, _PROIBIDOS):
            raise _rejeitar("comando_proibido", type(no).__name__)
    if not isinstance(raiz, exp.Select):
        raise _rejeitar("nao_e_select", type(raiz).__name__)

    tabelas_citadas = list(raiz.find_all(exp.Table))
    for tabela in tabelas_citadas:
        if not isinstance(tabela.this, exp.Identifier):
            raise _rejeitar("funcao_de_tabela", type(tabela.this).__name__)
        if tabela.catalog or tabela.db:
            raise _rejeitar("tabela_qualificada", "schema ou catálogo não são aceitos")
        if tabela.name not in tabelas:
            raise _rejeitar("tabela_fora_da_allowlist", "tabela não permitida")
    origem = raiz.args.get("from_") or raiz.args.get("from")
    if (
        len(tabelas_citadas) != 1
        or len(list(raiz.find_all(exp.Select))) != 1
        or raiz.args.get("joins")
        or not isinstance(origem, exp.From)
        or origem.this is not tabelas_citadas[0]
    ):
        raise _rejeitar(
            "construcao_nao_permitida", "exatamente um SELECT sobre uma tabela, sem JOIN nem CTE"
        )

    for no in nos:
        if isinstance(no, exp.Anonymous) or type(no) not in _PERMITIDOS:
            operador = isinstance(no, (exp.Binary, exp.Unary, exp.Predicate))
            funcao = isinstance(no, exp.Func) and not operador
            motivo = "funcao_nao_permitida" if funcao else "construcao_nao_permitida"
            raise _rejeitar(motivo, type(no).__name__)

    alias = {a.alias for a in raiz.find_all(exp.Alias)}
    if alias & fisicas:
        raise _rejeitar("coluna_nao_permitida", "alias com nome de coluna física")
    for coluna in raiz.find_all(exp.Column):
        if isinstance(coluna.this, exp.Star) or coluna.table:
            raise _rejeitar("coluna_nao_permitida", "referência de coluna não aceita")
        na_ordenacao = coluna.find_ancestor(exp.Order) is not None
        if coluna.name not in colunas and not (na_ordenacao and coluna.name in alias):
            raise _rejeitar("coluna_nao_permitida", "coluna fora da camada semântica")
    for estrela in raiz.find_all(exp.Star):
        if not isinstance(estrela.parent, exp.Count):
            raise _rejeitar("coluna_nao_permitida", "'*' só é aceito em COUNT(*)")

    for marcador in raiz.find_all(exp.Placeholder):
        if not marcador.name or marcador.name not in params:
            raise _rejeitar("parametro_sem_valor", "parâmetro sem valor vinculado")

    limite = raiz.args.get("limit")
    if not isinstance(limite, exp.Limit):
        raise _rejeitar("sem_limit", "LIMIT é obrigatório no SELECT externo")
    expressao = limite.expression
    valor: Any = None
    if isinstance(expressao, exp.Placeholder):
        valor = params.get(expressao.name)
    elif isinstance(expressao, exp.Literal) and expressao.is_int:
        valor = int(expressao.this)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= teto:
        raise _rejeitar("limit_invalido", f"LIMIT tem de ser um inteiro entre 1 e {teto}")
