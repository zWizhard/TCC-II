"""Normalizacao de texto da camada semantica.

Deterministica e sem modelo: minusculas, sem acento, sem pontuacao, plural simples. O lexico e a
pergunta passam pela MESMA funcao (`chave`), de modo que a regra de plural nao precisa ser
linguisticamente perfeita — so consistente dos dois lados.

A barra '/' e preservada como token proprio: 'concluintes/ingressantes' e uma razao, e a
recuperacao precisa ve-la.
"""

import re
import unicodedata
from dataclasses import dataclass

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9/]+")
# Numero no formato brasileiro e UM token: milhar com ponto ('100.000') e decimal com virgula
# ('1,5', '1.234,5'). Sem isto, '100.000' viraria os numeros 100 e 0.
_NUMERO_BR = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\d.,]*\d)|\d+,\d+(?![\d.,]*\d)"
_PALAVRA = re.compile(_NUMERO_BR + r"|[^\W_]+|/")
_SO_NUMERO_BR = re.compile(_NUMERO_BR)
NUMERO = re.compile(r"\d+(?:\.\d+)?")  # forma canonica: so digitos, ponto como decimal


def e_numero(norma: str) -> bool:
    """O token (ja normalizado) e um numero, inteiro ou decimal."""
    return NUMERO.fullmatch(norma) is not None


# (sufixo plural, substituto), testados nesta ordem antes do corte do 's' final.
_PLURAIS: tuple[tuple[str, str], ...] = (
    ("oes", "ao"),
    ("aes", "ao"),
    ("ais", "al"),
    ("eis", "el"),
    ("ois", "ol"),
    ("ores", "or"),
    ("ares", "ar"),
    ("eres", "er"),
    ("zes", "z"),
    ("ns", "m"),
)


def normalizar(texto: str) -> str:
    """Minusculas, sem acento, pontuacao reduzida a espaco; a barra vira palavra isolada."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if not unicodedata.combining(c)
    )
    return " ".join(_NAO_ALFANUMERICO.sub(" ", sem_acento).replace("/", " / ").split())


def singular(token: str) -> str:
    """Plural simples do portugues; tokens de ate 2 letras e sem 's' final ficam como estao."""
    if len(token) <= 2 or not token.endswith("s"):
        return token
    for sufixo, substituto in _PLURAIS:
        if token.endswith(sufixo) and len(token) > len(sufixo) + 1:
            return token[: -len(sufixo)] + substituto
    return token[:-1]


def palavras(texto: str) -> list[str]:
    """Lista de palavras de um texto separado por espacos (para declarar listas longas)."""
    return texto.split()


def chave(termo: str) -> str:
    """Forma canonica de um termo: e a chave do lexico e a forma em que a pergunta e casada."""
    return " ".join(singular(t) for t in normalizar(termo).split())


@dataclass(frozen=True)
class Token:
    original: str  # como o usuario escreveu (caixa e acento decidem sigla de UF e nome proprio)
    norma: str  # normalizado, ainda no plural: e o que se compara com as stopwords
    chave: str  # normalizado e no singular: e o que se compara com o lexico


def tokenizar(texto: str) -> list[Token]:
    """Tokens da pergunta, na ordem; o hifen separa ('centro-oeste') e a barra e token."""
    tokens: list[Token] = []
    for m in _PALAVRA.finditer(texto):
        if _SO_NUMERO_BR.fullmatch(m.group()):
            canonico = m.group().replace(".", "").replace(",", ".")
            tokens.append(Token(m.group(), canonico, canonico))
            continue
        for parte in normalizar(m.group()).split():
            tokens.append(Token(m.group(), parte, singular(parte)))
    return tokens


# Lista pequena de proposito: palavra de conteudo fora do lexico TEM de aparecer como nao
# reconhecida. Negacoes ('sem', 'nao', 'exceto'...) NAO sao stopwords: ver NEGACOES.
STOPWORDS: frozenset[str] = frozenset(
    palavras(
        """
    a o as os um uma uns umas de do da dos das em no na nos nas por para pra com sob sobre
    entre e ou que se como qual quais quanto quanta quantos quantas quando ha tem tinha existe
    existem possui possuem sao foi esta estao ser estar ter me mostre mostrar liste listar diga
    informe exiba quero saber gostaria ver cada todo toda todos todas ao aos pelo pela pelos pelas
    seu sua seus suas esse essa esses essas este estes isso aquele aquela la ja apenas somente so
    """
    )
)

# Negacao e exclusao. A camada ainda nao tem filtro negativo: uma destas palavras, solta na
# pergunta, leva a esclarecimento — descarta-la inverteria o filtro em silencio. N-gramas do
# lexico que as contem ('sem fins lucrativos', 'nao aplicavel') sao casados antes e nao contam.
NEGACOES: frozenset[str] = frozenset(
    palavras("sem exceto fora menos nao nem excluindo excluido exclusive tirando")
)

# Palavras de operacao (limiar, ordem, forma da resposta). Nao sao conteudo da base: saem no
# contexto em `operadores`, para o QueryPlan da proxima fase, e nunca viram mapeamento.
OPERADORES: frozenset[str] = frozenset(
    palavras(
        """
    mais maior maiores menor menores numero numeros quantidade quantidades total totais
    acima abaixo ranking top comparar compare comparacao distribuicao proporcao percentual
    participacao razao taxa relacao indice quociente
    """
    )
)

# Operadores de limiar: um numero logo depois deles e quantidade, nao ano ('mais de 2000').
LIMIARES: frozenset[str] = frozenset(
    palavras("mais menos acima abaixo maior menor superior inferior top minimo maximo")
)

# Palavras que pedem uma razao entre duas medidas.
PALAVRAS_DE_RAZAO: frozenset[str] = frozenset(
    palavras("proporcao percentual razao taxa relacao indice quociente")
)
# Destas, as que nao fazem sentido com uma medida so ('taxa de matriculas').
RAZAO_EXIGE_DOIS: frozenset[str] = frozenset(palavras("razao taxa relacao indice quociente"))

# Conectores que, ENTRE duas medidas, formam uma razao ('X por Y', 'X sobre Y', 'X/Y',
# 'X para cada Y', 'X em relacao a Y', 'X versus Y').
CONECTORES_DE_RAZAO: frozenset[str] = frozenset(
    palavras("por sobre / dividido dividida divididos divididas cada relacao versus vs")
)
# Palavras que podem acompanhar o conector sem mudar o sentido.
ENCHIMENTO_DE_RAZAO: frozenset[str] = frozenset(
    palavras("o a os as de do da dos das um uma para em ao aos pelo pela no na numero total")
)

# Conectores aceitos dentro de um nome proprio de lugar ('Sao Jose dos Campos').
CONECTORES_DE_NOME: frozenset[str] = frozenset({"de", "do", "da", "dos", "das", "e"})

# Preposicoes depois das quais um 'para'/'se' e, provavelmente, a UF escrita sem acento ou caixa.
PREPOSICOES_DE_LUGAR: frozenset[str] = frozenset({"em", "no", "na", "do", "de", "pelo"})

# Expressoes que so repetem o escopo da base (toda ela e educacao superior, Censo 2024). Casadas
# como n-grama e descartadas: sem isto, 'educacao superior' casaria a area CINE 'Educacao'.
# 'graduacao' NAO esta aqui: so e ignorada em 'curso(s) de graduacao' (ver recuperacao.py);
# junto de docente ou titulacao e o valor da titulacao.
FRASES_IGNORADAS: frozenset[str] = frozenset(
    chave(f)
    for f in (
        "educação superior",
        "ensino superior",
        "nível superior",
        "censo da educação superior",
        "censo",
        "ano",
        "ano de 2024",
        "em 2024",
        "2024",
    )
)
# (substantivo, resto ignorado): o substantivo e casado normalmente, o resto e descartado.
ESCOPO_DEPOIS_DE: tuple[tuple[str, tuple[str, ...]], ...] = (("curso", ("de", "graduacao")),)

ANO_DA_BASE = "2024"
ANO_MINIMO, ANO_MAXIMO = 1990, 2100
