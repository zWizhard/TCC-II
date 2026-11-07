"""Analise e explicacao DETERMINISTICAS do resultado. O LLM nao e calculadora.

Todo numero daqui sai das linhas devolvidas pelo banco, por aritmetica em Python: soma, maximo,
minimo, media e participacao percentual. A explicacao e um texto montado pelo backend a partir
do plano validado e da camada semantica — nomes canonicos das metricas ("matrículas", nunca
"alunos"), recorte e dimensao de oferta sempre declarados, base de um unico ano.

Nao ha explicacao gerada por LLM nesta versao. `verificar_texto` e a trava que qualquer texto
livre tem de passar (e que o texto do backend passa, em teste): nenhum numero ausente do
resultado, nenhum termo temporal (a base so tem 2024) e nenhum termo que a terminologia veda.
"""

import re
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from api.analista.plano import Direcao
from api.analista.sql import ColunaSaida
from api.analista.validacao import PlanoValidado, aditiva
from api.consultas import ANO_CENSO
from api.indicadores import Nivel, Recorte
from api.semantica import CAMADA, CamadaSemantica
from api.semantica.texto import chave

_ROTULO_RECORTE: dict[Recorte, str] = {
    Recorte.SEDE: "sede da IES (município de sede da instituição)",
    Recorte.OFERTA: "local de oferta do curso (inclui polos EAD)",
}
_ROTULO_NIVEL: dict[Nivel, str] = {
    Nivel.BRASIL: "Brasil",
    Nivel.REGIAO: "região",
    Nivel.UF: "UF",
    Nivel.MUNICIPIO: "município",
}
_TERMOS_TEMPORAIS = frozenset(
    chave(t)
    for t in (
        *(s.termo for s in CAMADA.termo_vedado("variacao_temporal").termos),
        *("evolução", "tendência", "crescimento", "queda", "aumento", "redução", "variação"),
    )
)
_NUMERO = re.compile(r"\d[\d.]*(?:,\d+)?")
_PALAVRA = re.compile(r"[^\W\d_]+")


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Extremo(_Modelo):
    rotulo: str
    valor: int | float


class AnaliseMetrica(_Modelo):
    metrica: str
    nome: str
    unidade: str
    linhas_com_valor: int
    # Consulta sem agrupamento: o valor unico devolvido pelo banco (nulo = nao se aplica).
    valor: int | float | None = None
    # Soma das linhas devolvidas; nula para razao e contagem distinta (nao se somam) e quando o
    # resultado foi truncado (seria um total parcial).
    soma: int | None = None
    media: float | None = None
    maximo: Extremo | None = None
    minimo: Extremo | None = None
    # Participacao de cada linha na soma, em %, na ordem das linhas; so quando `soma` existe e
    # nao ha limiar (com limiar, a soma nao e o total do recorte).
    participacao_pct: tuple[float | None, ...] | None = None


class Analise(_Modelo):
    metricas: tuple[AnaliseMetrica, ...]
    observacoes: tuple[str, ...] = ()


def formatar(valor: Any) -> str:
    """Numero no padrao brasileiro (1.234.567 e 12,34); nulo = 'não se aplica'."""
    if valor is None:
        return "não se aplica"
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return str(valor)
    texto = f"{valor:,}" if isinstance(valor, int) else f"{valor:,.2f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _rotulo(linha: list[Any], indices: list[int]) -> str:
    return " / ".join(str(linha[i]) for i in indices) or "Brasil"


def analisar(
    validado: PlanoValidado,
    colunas: tuple[ColunaSaida, ...],
    linhas: list[list[Any]],
    truncado: bool,
) -> Analise:
    dims = [i for i, c in enumerate(colunas) if c.papel == "dimensao"]
    agrupado = bool(validado.agrupamentos)
    com_limiar = bool(validado.plano.having)
    metricas: list[AnaliseMetrica] = []
    observacoes: list[str] = []
    for m in validado.metricas:
        i = next(k for k, c in enumerate(colunas) if c.papel == "metrica" and c.referencia == m.id)
        pares = [(linha[i], _rotulo(linha, dims)) for linha in linhas if linha[i] is not None]
        soma: int | None = None
        media: float | None = None
        participacao: tuple[float | None, ...] | None = None
        if agrupado and aditiva(m) and not truncado:
            soma = sum(int(v) for v, _ in pares)
            media = round(soma / len(pares), 2) if pares else None
            if soma > 0 and not com_limiar:
                participacao = tuple(
                    None if linha[i] is None else round(linha[i] / soma * 100, 2)
                    for linha in linhas
                )
        maior = max(pares, key=lambda p: p[0], default=None) if agrupado else None
        menor = min(pares, key=lambda p: p[0], default=None) if agrupado else None
        metricas.append(
            AnaliseMetrica(
                metrica=m.id,
                nome=m.nome,
                unidade=m.unidade,
                linhas_com_valor=len(pares),
                valor=linhas[0][i] if linhas and not agrupado else None,
                soma=soma,
                media=media,
                maximo=None if maior is None else Extremo(rotulo=maior[1], valor=maior[0]),
                minimo=None if menor is None else Extremo(rotulo=menor[1], valor=menor[0]),
                participacao_pct=participacao,
            )
        )
        if agrupado and not aditiva(m):
            observacoes.append(
                f"'{m.nome}' não é somável entre os grupos: não há total nem participação."
            )
    if truncado:
        observacoes.append(
            "Resultado truncado pelo limite de linhas: soma, média e participação não são "
            "calculadas, e máximo e mínimo valem só para as linhas exibidas."
        )
    if com_limiar and agrupado:
        observacoes.append(
            "Há limiar sobre a métrica: a soma cobre só os grupos que passaram por ele."
        )
    return Analise(metricas=tuple(metricas), observacoes=tuple(observacoes))


def interpretar(validado: PlanoValidado, camada: CamadaSemantica | None = None) -> str:
    """Como a pergunta foi lida, com os nomes canonicos da camada (nunca os do usuario)."""
    camada = camada or CAMADA
    plano = validado.plano
    texto = " e ".join(m.nome for m in validado.metricas)
    if validado.agrupamentos:
        texto += " por " + ", ".join(camada.dimensao(a).nome for a in validado.agrupamentos)
    else:
        texto += f" no nível {_ROTULO_NIVEL[plano.dimensions.nivel_territorial]}"
    for f in plano.filters:
        d = camada.dimensao(f.dimensao)
        rotulos = {str(v.id): v.rotulo for v in d.valores}
        texto += f"; {d.nome} = {', '.join(rotulos.get(v, v) for v in f.valores)}"
    for h in plano.having:
        texto += f"; {camada.metrica(h.metrica).nome} {h.operador} {formatar(h.valor)}"
    if validado.agrupamentos:
        # Ordem e limite fazem parte da leitura: sao declarados, nunca implicitos.
        por_id = {m.id: m.nome for m in validado.metricas}
        ordem = [
            f"{por_id.get(o.por) or camada.dimensao(o.por).nome} "
            f"({'decrescente' if o.direcao == Direcao.DESC else 'crescente'})"
            for o in plano.order_by
        ] or [f"{validado.metricas[0].nome} (decrescente, ordem padrão)"]
        texto += f"; ordenado por {', '.join(ordem)}; até {formatar(plano.limit)} linhas"
    return texto + "."


def declarar_oferta(validado: PlanoValidado, camada: CamadaSemantica | None = None) -> list[str]:
    camada = camada or CAMADA
    rotulos = {str(v.id): v.rotulo for v in camada.dimensao("dimensao").valores}
    return [rotulos[str(d)] for d in validado.plano.dimensions.dimensao_de_oferta]


def resumir(validado: PlanoValidado, analise: Analise, n_linhas: int, truncado: bool) -> str:
    """Frase com os numeros do resultado — todos ja calculados em `analisar` ou vindos do banco."""
    if n_linhas == 0:
        return "Resultado: nenhuma linha atende à consulta."
    partes: list[str] = []
    if not validado.agrupamentos:
        return (
            "Resultado: "
            + "; ".join(
                f"{a.nome} = {formatar(a.valor)}" + ("" if a.valor is None else f" {a.unidade}")
                for a in analise.metricas
            )
            + "."
        )
    contagem = "1 linha" if n_linhas == 1 else f"{formatar(n_linhas)} linhas"
    partes.append(contagem + (" (truncado pelo limite)" if truncado else ""))
    for a in analise.metricas:
        if a.soma is not None:
            partes.append(f"soma de {a.nome} nas linhas = {formatar(a.soma)} {a.unidade}")
        if a.maximo is not None and a.minimo is not None:
            partes.append(
                f"maior {a.nome}: {a.maximo.rotulo} ({formatar(a.maximo.valor)}); "
                f"menor: {a.minimo.rotulo} ({formatar(a.minimo.valor)})"
            )
    return "Resultado: " + "; ".join(partes) + "."


def explicar(
    validado: PlanoValidado,
    resumo: str,
    camada: CamadaSemantica | None = None,
) -> str:
    """Texto final: interpretacao, recorte e dimensao declarados, base e resultado."""
    plano = validado.plano
    partes = [
        f"Interpretação: {interpretar(validado, camada)}",
        f"Recorte territorial: {_ROTULO_RECORTE[plano.dimensions.recorte]}.",
    ]
    oferta = declarar_oferta(validado, camada)
    if oferta:
        partes.append(f"Dimensão de oferta: {'; '.join(oferta)}.")
    partes.append(
        f"Base: Censo da Educação Superior {ANO_CENSO}, retrato de um único ano "
        "(sem comparação entre anos)."
    )
    partes.append(resumo)
    return " ".join(partes)


def numeros_do_resultado(linhas: Iterable[list[Any]], analise: Analise) -> set[float]:
    """Todo numero que um texto sobre o resultado pode citar."""
    permitidos: set[float] = {float(ANO_CENSO)}
    n = 0
    for linha in linhas:
        n += 1
        for celula in linha:
            if isinstance(celula, (int, float)) and not isinstance(celula, bool):
                permitidos.add(float(celula))
            elif isinstance(celula, str):
                permitidos.update(float(x) for x in re.findall(r"\d+", celula))
    permitidos.add(float(n))
    for a in analise.metricas:
        extremos = [e.valor for e in (a.maximo, a.minimo) if e is not None]
        for v in (a.valor, a.soma, a.media, *extremos):
            if v is not None:
                permitidos.add(float(v))
        permitidos.update(float(p) for p in a.participacao_pct or () if p is not None)
    return permitidos


def verificar_texto(
    texto: str, numeros_permitidos: Iterable[float], termos_proibidos: Iterable[str] = ()
) -> list[str]:
    """Problemas de um texto livre sobre o resultado (lista vazia = aprovado).

    Numero: aceito se for igual a um permitido, com tolerancia de arredondamento a 2 casas.
    """
    problemas: list[str] = []
    permitidos = list(numeros_permitidos)
    for bruto in _NUMERO.findall(texto):
        valor = float(bruto.rstrip(".").replace(".", "").replace(",", "."))
        if not any(abs(valor - p) <= 0.005 + 1e-9 for p in permitidos):
            problemas.append(f"número ausente do resultado: {bruto}")
    palavras = {chave(p) for p in _PALAVRA.findall(texto)}
    normalizado = " ".join(chave(p) for p in _PALAVRA.findall(texto))
    for termo in sorted(_TERMOS_TEMPORAIS):
        if (termo in palavras) if " " not in termo else (termo in normalizado):
            problemas.append(f"termo temporal vedado (a base só tem {ANO_CENSO}): {termo}")
    for termo in termos_proibidos:
        k = chave(termo)
        if k and (k in palavras or k + "s" in palavras):
            problemas.append(f"termo vedado pela terminologia: {termo}")
    return problemas
