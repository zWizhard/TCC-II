#!/usr/bin/env python3
"""Executor do benchmark: valida o conjunto de teste e mede o bloco de sistema (sem LLM).

    .venv/Scripts/python.exe -m benchmark.executar --validar-conjunto
    .venv/Scripts/python.exe -m benchmark.executar --rotulo <nome>

Ordem de uma execucao:
1. valida o conjunto de teste (o plano de referencia de cada caso tem de reproduzir o SQL de
   referencia; se nao reproduzir, nada e medido);
2. roda o bloco de sistema (sem LLM), uma vez, e grava `sistema.json` e `manifesto.json` em
   docs/tcc/benchmark/resultados/<rotulo>/.

A medicao de modelos (bloco de modelo) depende de um provedor de LLM implementado. O provedor de
producao e a AWS Bedrock (ADR-0021), ainda sem fabrica: quando ela existir, a medicao volta a
usar `medir_caso` com esse provedor, sem mudar casos, criterios nem relatorio.
"""

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import sqlglot

from api.analista.llm import PROMPT_DE_SISTEMA
from api.analista.pipeline import RespostaAnalista, responder
from api.analista.plano import QueryPlan
from api.config import RAIZ, Settings
from api.db import BaseAnalitica
from api.erros import ErroApi
from api.semantica import recuperar_contexto
from benchmark.avaliacao import (
    diferencas_de_plano,
    ha_empate_na_ordem,
    mesmo_resultado,
    plano_canonico,
)
from benchmark.casos import CASOS, PERGUNTA_DE_AQUECIMENTO, Caso, casos
from benchmark.provedor import ProvedorProibido, ProvedorRoteirizado

SAIDA = RAIZ / "docs" / "tcc" / "benchmark" / "resultados"
SEMENTE_PADRAO = 20241007
REPETICOES_PADRAO = 3
_LIMITE_FINAL = re.compile(r"LIMIT (\d+)$")
_SITUACOES_SEM_RESPOSTA = frozenset(
    {"requer_esclarecimento", "recusada", "nao_mapeada", "nao_suportada", "pergunta_invalida"}
)

Referencia = tuple[list[str], list[tuple[Any, ...]]]


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _json(dados: Any) -> str:
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, default=str)


# --- referencia -----------------------------------------------------------------------------------


def _colunas(sql: str) -> list[str]:
    """Nomes das colunas de saida de um SELECT, lidos da arvore (a base so devolve as linhas)."""
    arvore = sqlglot.parse_one(sql, dialect="duckdb")
    assert isinstance(arvore, sqlglot.exp.Select)
    return list(arvore.named_selects)


def referencia(caso: Caso, base: BaseAnalitica) -> Referencia:
    """Colunas e linhas do SQL de referencia do caso, executado agora na base local."""
    assert caso.sql_referencia is not None
    return _colunas(caso.sql_referencia), base.consultar(caso.sql_referencia, {})


def _empate_no_corte(caso: Caso, base: BaseAnalitica, ref: Referencia) -> bool:
    """Em 'os N maiores', o N-esimo empata com o seguinte? Entao a resposta nao seria unica."""
    assert caso.sql_referencia is not None
    corte = _LIMITE_FINAL.search(caso.sql_referencia)
    if corte is None:
        return False
    n = int(corte.group(1))
    alem = base.consultar(_LIMITE_FINAL.sub(f"LIMIT {n + 1}", caso.sql_referencia), {})
    i = ref[0].index(caso.metricas[0])
    return len(alem) > n and alem[n][i] == alem[n - 1][i]


def validar_conjunto(base: BaseAnalitica) -> list[str]:
    """Problemas do conjunto de teste. Lista vazia = pode medir.

    Cada caso do bloco de modelo: a pergunta chega ao LLM; o plano de referencia passa na
    validacao; o SQL gerado a partir dele devolve o mesmo resultado do SQL de referencia; e, nos
    rankings, nao ha empate que torne a ordem ou o corte arbitrarios. Cada caso do bloco de
    sistema: a pergunta e resolvida sem LLM.
    """
    problemas: list[str] = []
    ids = [c.id for c in CASOS]
    if len(set(ids)) != len(ids) or len({c.pergunta for c in CASOS}) != len(CASOS):
        problemas.append("ha id ou pergunta repetidos no conjunto")
    for caso in casos("modelo"):
        assert caso.plano is not None
        ref = referencia(caso, base)
        if not ref[1]:
            problemas.append(f"{caso.id}: o SQL de referencia nao devolve linhas")
        registro = medir_caso(caso, base, ProvedorRoteirizado(caso.plano), ref)
        for criterio in ("plano_correto", "sql_correto", "resultado_correto"):
            if not registro[criterio]:
                problemas.append(
                    f"{caso.id}: o plano de referencia falha em '{criterio}' "
                    f"(desfecho {registro['desfecho']}; {registro['motivos']})"
                )
        if caso.ordenado and (
            ha_empate_na_ordem(ref[0], ref[1], caso.metricas[0])
            or _empate_no_corte(caso, base, ref)
        ):
            problemas.append(f"{caso.id}: ranking com empate; a ordem esperada nao e unica")
    for caso in casos("sistema"):
        if medir_caso_de_sistema(caso, base)["llm_chamado"]:
            problemas.append(
                f"{caso.id}: a pergunta chega ao LLM; nao pertence ao bloco de sistema"
            )
    return problemas


# --- medicao --------------------------------------------------------------------------------------


def medir_caso(
    caso: Caso,
    base: BaseAnalitica,
    provedor: Any,
    ref: Referencia,
) -> dict[str, Any]:
    """Uma pergunta pelo pipeline de producao, avaliada contra a referencia do caso."""
    assert caso.plano is not None
    resposta: RespostaAnalista | None = None
    erro: ErroApi | None = None
    inicio = time.perf_counter()
    try:
        resposta = responder(caso.pergunta, base, provedor)
    except ErroApi as exc:
        erro = exc
    tempo_ms = round((time.perf_counter() - inicio) * 1000, 1)
    plano = resposta.plano if resposta is not None else None
    esperado = plano_canonico(caso.plano)
    diferencas = diferencas_de_plano(plano_canonico(plano), esperado) if plano else list(esperado)

    respondida = resposta is not None and resposta.situacao == "respondida"
    sql_correto = resultado_correto = False
    if respondida:
        assert resposta is not None and resposta.consulta is not None
        gerado = resposta.consulta
        colunas_sql = _colunas(gerado.sql)
        linhas_sql = base.consultar(gerado.sql, dict(gerado.parametros))[: resposta.plano.limit]  # type: ignore[union-attr]
        sql_correto = mesmo_resultado(
            ref[0], ref[1], colunas_sql, linhas_sql, caso.metricas, caso.ordenado
        )
        resultado_correto = (
            mesmo_resultado(
                ref[0],
                ref[1],
                [c.id for c in resposta.colunas],
                resposta.linhas,
                caso.metricas,
                caso.ordenado,
            )
            # Nenhuma metrica a mais, nenhuma a menos.
            and {c.id for c in resposta.colunas if c.papel == "metrica"} == set(caso.metricas)
            # 'Os N maiores' sai marcado como truncado por definicao; fora disso, truncar e erro.
            and (not resposta.truncado or "limit" in caso.plano)
            and str(resposta.recorte) == caso.plano["dimensions"]["recorte"]
        )
    if erro is not None:
        desfecho = erro.codigo
        motivos = [erro.mensagem]
    else:
        assert resposta is not None
        desfecho = resposta.situacao
        motivos = [m.codigo for m in resposta.motivos]
    return {
        "caso": caso.id,
        "categoria": caso.categoria,
        "convencao_implicita": caso.convencao_implicita,
        "prompt_sha256": _sha256(recuperar_contexto(caso.pergunta).para_prompt()),
        "desfecho": desfecho,
        "motivos": motivos,
        "json_valido": plano is not None,
        "plano_valido": respondida,
        "plano_correto": not diferencas,
        "campos_divergentes": diferencas,
        "sql_executavel": respondida,
        "sql_correto": sql_correto,
        "resultado_correto": resultado_correto,
        "tempo_ms": tempo_ms,
        "sql": resposta.consulta.sql if respondida and resposta and resposta.consulta else None,
    }


def medir_caso_de_sistema(caso: Caso, base: BaseAnalitica) -> dict[str, Any]:
    provedor = ProvedorProibido()
    situacao = "erro"
    try:
        situacao = responder(caso.pergunta, base, provedor).situacao
    except (ErroApi, AssertionError) as exc:
        situacao = f"erro:{type(exc).__name__}"
    return {
        "caso": caso.id,
        "categoria": caso.categoria,
        "pergunta": caso.pergunta,
        "situacao_ideal": caso.situacao_ideal,
        "situacao": situacao,
        "llm_chamado": provedor.chamado,
        # Seguranca: nenhum numero foi devolvido para uma pergunta que nao pode ser respondida.
        "abstencao_correta": not provedor.chamado and situacao in _SITUACOES_SEM_RESPOSTA,
        "situacao_exata": situacao == caso.situacao_ideal,
    }


# --- ambiente e modelo ----------------------------------------------------------------------------


def _comando(*args: str) -> str | None:
    try:
        saida = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() or None


def _sha256_de_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        while bloco := f.read(1 << 20):
            h.update(bloco)
    return h.hexdigest()


def _hash_do_codigo() -> dict[str, str]:
    """Um hash por pacote que influi no resultado: o conteudo de todos os seus .py, em ordem."""
    saida: dict[str, str] = {}
    for pacote in ("api/analista", "api/semantica", "benchmark"):
        h = hashlib.sha256()
        for arquivo in sorted((RAIZ / pacote).glob("*.py")):
            if arquivo.name == "relatorio.py":  # agrega depois; nao participa da medicao
                continue
            h.update(arquivo.name.encode())
            h.update(arquivo.read_bytes().replace(b"\r\n", b"\n"))
        saida[pacote] = h.hexdigest()
    saida["api/indicadores.py"] = _sha256_de_arquivo(RAIZ / "api" / "indicadores.py")
    return saida


def ambiente() -> dict[str, Any]:
    gpu = _comando(
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"
    )
    cpu = _comando(
        "powershell",
        "-NoProfile",
        "-Command",
        "(Get-CimInstance Win32_Processor).Name; "
        "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)",
    )
    return {
        "sistema": platform.platform(),
        "python": platform.python_version(),
        "cpu_e_ram_gb": cpu.splitlines() if cpu else None,
        "gpu": gpu,
        "vram_em_uso_antes_mib": _comando(
            "nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"
        ),
        "bibliotecas": {p: version(p) for p in ("duckdb", "sqlglot", "pydantic", "httpx")},
        # O repositorio tem alteracoes nao commitadas: o codigo medido e identificado por hash.
        "codigo_sha256": _hash_do_codigo(),
        "base_duckdb_sha256": _sha256_de_arquivo(Settings().analytics_duckdb_path),
        "git_commit": _comando("git", "-C", str(RAIZ), "rev-parse", "HEAD"),
        "git_alteracoes_nao_commitadas": bool(
            _comando("git", "-C", str(RAIZ), "status", "--porcelain")
        ),
    }


# --- execucao -------------------------------------------------------------------------------------


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--validar-conjunto", action="store_true", help="so valida o conjunto e sai")
    p.add_argument("--rotulo", help="nome da pasta de resultados do bloco de sistema")
    return p.parse_args()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    args = _argumentos()
    settings = Settings()
    base = BaseAnalitica(settings.analytics_duckdb_path, settings.api_query_timeout_seconds)
    try:
        problemas = validar_conjunto(base)
        for problema in problemas:
            print("CONJUNTO INVALIDO:", problema)
        if problemas:
            return 1
        n_m, n_s = len(casos("modelo")), len(casos("sistema"))
        print(f"conjunto valido: {n_m} casos de modelo, {n_s} de sistema")
        if args.validar_conjunto:
            return 0
        if not args.rotulo:
            print("informe --rotulo (ou --validar-conjunto)")
            return 2
        pasta = SAIDA / args.rotulo
        pasta.mkdir(parents=True, exist_ok=False)  # nunca sobrescreve uma rodada
        refs = {c.id: referencia(c, base) for c in casos("modelo")}
        sistema = [medir_caso_de_sistema(c, base) for c in casos("sistema")]
        (pasta / "sistema.json").write_text(
            json.dumps(sistema, ensure_ascii=False, indent=1), "utf-8"
        )
        contexto = recuperar_contexto(PERGUNTA_DE_AQUECIMENTO)
        manifesto: dict[str, Any] = {
            "rotulo": args.rotulo,
            "inicio": datetime.now(UTC).isoformat(timespec="seconds"),
            "ambiente": ambiente(),
            "configuracao": {"provedor": settings.llm_provider},
            "prompt_de_sistema_sha256": _sha256(PROMPT_DE_SISTEMA),
            "schema_do_plano_sha256": _sha256(_json(QueryPlan.model_json_schema())),
            "conjunto_sha256": _sha256(_json([vars(c) for c in CASOS])),
            "referencias_sha256": _sha256(_json(refs)),
            "prompt_de_exemplo_chars": len(contexto.para_prompt()),
            "casos": {"modelo": n_m, "sistema": n_s},
            "fim": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        (pasta / "manifesto.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=1), "utf-8"
        )
        print(f"gravado em {pasta}")
        return 0
    finally:
        base.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
