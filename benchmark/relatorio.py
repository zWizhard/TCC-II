#!/usr/bin/env python3
"""Agrega as rodadas do benchmark em tabelas reaproveitaveis (CSV e Markdown).

    .venv/Scripts/python.exe -m benchmark.relatorio

Le docs/tcc/benchmark/resultados/<condicao>_<modelo>/ (pastas iniciadas por `_` sao pilotos e
ficam fora). A letra antes do primeiro `_` e a condicao do protocolo (P, N, A). Grava em
docs/tcc/benchmark/: `resumo_modelos.csv`, `por_categoria.csv`, `por_caso.csv`, `falhas.csv`,
`comparacoes_pareadas.csv`, `sistema.csv` e `TABELAS.md`.

Unidade de analise: o CASO. Um caso conta como acerto quando acerta em todas as repeticoes.
"""

import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

from benchmark.executar import SAIDA

DESTINO = SAIDA.parent
CRITERIOS = ("json_valido", "plano_valido", "plano_correto", "sql_correto", "resultado_correto")
_NOMES = {
    "json_valido": "JSON válido",
    "plano_valido": "Plano válido / SQL executável",
    "plano_correto": "Plano correto",
    "sql_correto": "SQL semanticamente correto",
    "resultado_correto": "Resultado correto (sucesso)",
}
_PAPEL = {
    "P": "produção (como o sistema está)",
    "N": "sem raciocínio (`think: false`)",
    "A": "orçamento ampliado (diagnóstico)",
}
Z95 = 1.959963984540054
PRAZO_DE_USO_S = 120.0
# Condicoes que entram na comparacao entre modelos; A e diagnostico (PROTOCOLO.md, secao 5).
COMPARAVEIS = ("P", "N")


# --- estatistica ----------------------------------------------------------------------------------


def wilson(k: int, n: int) -> tuple[float, float]:
    """Intervalo de confianca de 95% de Wilson para a proporcao k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centro = p + Z95**2 / (2 * n)
    margem = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n**2))
    denominador = 1 + Z95**2 / n
    return (max(0.0, (centro - margem) / denominador), min(1.0, (centro + margem) / denominador))


def mcnemar_exato(b: int, c: int) -> float:
    """p bilateral do teste exato de McNemar; b e c sao os casos discordantes."""
    n = b + c
    if n == 0:
        return 1.0
    cauda = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * cauda)


def holm(ps: list[float]) -> list[float]:
    """p ajustados de Holm, na ordem de entrada."""
    m = len(ps)
    ajustados = [0.0] * m
    anterior = 0.0
    for posto, i in enumerate(sorted(range(m), key=lambda i: ps[i])):
        anterior = max(anterior, min(1.0, (m - posto) * ps[i]))
        ajustados[i] = anterior
    return ajustados


def qui2_cauda(x: float, gl: int) -> float:
    """P(X >= x) para uma qui-quadrado com `gl` graus de liberdade (gl inteiro >= 1)."""
    if x <= 0:
        return 1.0
    meio = x / 2
    # Q(a, x) pela recorrencia Q(a+1) = Q(a) + x^a e^-x / Gamma(a+1), de a = 1/2 ou a = 1.
    if gl % 2:
        a, q = 0.5, math.erfc(math.sqrt(meio))
    else:
        a, q = 1.0, math.exp(-meio)
    while a < gl / 2:
        q += math.exp(a * math.log(meio) - meio - math.lgamma(a + 1))
        a += 1
    return min(1.0, q)


def cochran_q(matriz: list[list[bool]]) -> tuple[float, int, float] | None:
    """(Q, gl, p) para linhas = casos e colunas = modelos. None se nao ha variacao."""
    k = len(matriz[0])
    colunas = [sum(linha[j] for linha in matriz) for j in range(k)]
    linhas = [sum(linha) for linha in matriz]
    total = sum(linhas)
    denominador = k * total - sum(r * r for r in linhas)
    if k < 2 or denominador == 0:
        return None
    q = (k - 1) * (k * sum(c * c for c in colunas) - total * total) / denominador
    return q, k - 1, qui2_cauda(q, k - 1)


def percentil(valores: list[float], q: float) -> float:
    """Percentil pelo posto mais proximo (sem interpolar: n pequeno)."""
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(q * len(ordenados)) - 1)]


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _taxa(k: int, n: int) -> str:
    baixo, alto = wilson(k, n)
    return f"{k}/{n} ({_pct(k / n)}%; {_pct(baixo)}–{_pct(alto)})"


# --- leitura --------------------------------------------------------------------------------------


def carregar() -> dict[str, dict[str, dict[str, Any]]]:
    """condicao -> modelo -> {manifesto, info, execucoes}."""
    dados: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for pasta in sorted(SAIDA.iterdir()):
        if not pasta.is_dir() or pasta.name.startswith("_") or "_" not in pasta.name:
            continue
        if not (pasta / "execucoes.jsonl").exists():  # rodada so do bloco de sistema
            continue
        condicao = pasta.name.split("_", 1)[0]
        manifesto = json.loads((pasta / "manifesto.json").read_text("utf-8"))
        with (pasta / "execucoes.jsonl").open(encoding="utf-8") as f:
            execucoes = [json.loads(linha) for linha in f if linha.strip()]
        for info in manifesto["modelos"]:
            modelo = info["modelo"]
            if modelo in dados[condicao]:
                raise SystemExit(f"modelo {modelo} aparece em duas rodadas da condicao {condicao}")
            dados[condicao][modelo] = {
                "pasta": pasta.name,
                "manifesto": manifesto,
                "info": info,
                "execucoes": [e for e in execucoes if e["modelo"] == modelo],
            }
    return dados


def _por_caso(execucoes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    casos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in sorted(execucoes, key=lambda x: x["repeticao"]):
        casos[e["caso"]].append(e)
    return casos


def acertos(execucoes: list[dict[str, Any]], criterio: str) -> dict[str, bool]:
    """caso -> acertou o criterio em TODAS as repeticoes."""
    return {c: all(e[criterio] for e in es) for c, es in _por_caso(execucoes).items()}


# --- resumo por modelo ----------------------------------------------------------------------------


def resumo(condicao: str, modelo: str, r: dict[str, Any]) -> dict[str, Any]:
    execucoes, info = r["execucoes"], r["info"]
    memoria = info.get("memoria") or {}
    linha: dict[str, Any] = {
        "condicao": condicao,
        "modelo": modelo,
        "situacao": info.get("situacao"),
        "parametros": (info.get("instalado") or {}).get("parameter_size"),
        "quantizacao": (info.get("instalado") or {}).get("quantization_level"),
        "digest": ((info.get("instalado") or {}).get("digest") or "")[:12],
        "fracao_na_gpu": memoria.get("fracao_na_gpu"),
        "memoria_gb": round(memoria["bytes_em_memoria"] / 1e9, 1) if memoria else None,
        "janela_de_contexto": memoria.get("janela_de_contexto"),
        "carga_s": info.get("carga_s"),
        "casos": 0,
        "execucoes": len(execucoes),
    }
    if not execucoes:
        return linha
    casos = _por_caso(execucoes)
    n = len(casos)
    linha["casos"] = n
    linha["repeticoes"] = max(e["repeticao"] for e in execucoes)
    for criterio in CRITERIOS:
        k = sum(acertos(execucoes, criterio).values())
        baixo, alto = wilson(k, n)
        linha[f"{criterio}_casos"] = k
        linha[f"{criterio}_pct"] = _pct(k / n)
        linha[f"{criterio}_ic95"] = f"{_pct(baixo)}–{_pct(alto)}"
        linha[f"{criterio}_pct_execucoes"] = _pct(
            sum(e[criterio] for e in execucoes) / len(execucoes)
        )
    sucesso = acertos(execucoes, "resultado_correto")
    explicitos = [c for c, es in casos.items() if not es[0].get("convencao_implicita")]
    linha["sucesso_sem_convencao_casos"] = sum(sucesso[c] for c in explicitos)
    linha["casos_sem_convencao"] = len(explicitos)
    # Estabilidade: mesma saida bruta e mesmo desfecho em todas as repeticoes do caso.
    linha["casos_com_saida_identica"] = sum(
        len({(e["desfecho"], e["resultado_correto"], e["resposta_bruta"]) for e in es}) == 1
        for es in casos.values()
    )
    linha["casos_com_desfecho_estavel"] = sum(
        len({(e["desfecho"], e["resultado_correto"]) for e in es}) == 1 for es in casos.values()
    )
    tempos = [e["tempo_ms"] / 1000 for e in execucoes]
    certos = [e["tempo_ms"] / 1000 for e in execucoes if e["resultado_correto"]]
    linha["latencia_mediana_s"] = round(statistics.median(tempos), 1)
    linha["latencia_p90_s"] = round(percentil(tempos, 0.9), 1)
    linha["latencia_max_s"] = round(max(tempos), 1)
    linha["latencia_mediana_dos_acertos_s"] = (
        round(statistics.median(certos), 1) if certos else None
    )
    linha["execucoes_acima_de_120_s"] = sum(t > PRAZO_DE_USO_S for t in tempos)
    llm = [e["llm"] for e in execucoes if e["llm"]]
    gerados = [x["tokens_gerados"] for x in llm if x["tokens_gerados"]]
    velocidade = [x["tokens_por_segundo"] for x in llm if x["tokens_por_segundo"]]
    entrada = [x["tokens_de_entrada"] for x in llm if x["tokens_de_entrada"]]
    linha["tokens_gerados_mediana"] = round(statistics.median(gerados)) if gerados else None
    linha["tokens_por_segundo_mediana"] = (
        round(statistics.median(velocidade), 1) if velocidade else None
    )
    linha["tokens_de_entrada_max"] = max(entrada) if entrada else None
    teto = r["manifesto"]["configuracao"]["max_tokens"]
    janela = linha["janela_de_contexto"]
    linha["entrada_mais_teto_cabe_na_janela"] = (
        None if not entrada or not janela else max(entrada) + teto <= janela
    )
    linha["execucoes_com_raciocinio"] = sum(x["raciocinio_chars"] > 0 for x in llm)
    linha["paradas_por_length"] = sum(x["motivo_de_parada"] == "length" for x in llm)
    desfechos = Counter(e["desfecho"] for e in execucoes)
    for d in ("respondida", "plano_invalido", "resposta_do_modelo_invalida", "modelo_indisponivel"):
        linha[f"n_{d}"] = desfechos.pop(d, 0)
    linha["n_outros_desfechos"] = sum(desfechos.values())
    return linha


# --- saida ----------------------------------------------------------------------------------------


def _gravar(nome: str, linhas: list[dict[str, Any]]) -> None:
    if not linhas:
        return
    campos = list(dict.fromkeys(k for linha in linhas for k in linha))
    with (DESTINO / nome).open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def _tabela(cabecalho: list[str], linhas: list[list[Any]]) -> str:
    def texto(v: Any) -> str:
        return "—" if v is None else str(v)

    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(texto(v) for v in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def _secao_da_condicao(
    condicao: str,
    modelos: dict[str, dict[str, Any]],
    saidas: dict[str, list[dict[str, Any]]],
) -> list[str]:
    linhas = [resumo(condicao, m, r) for m, r in modelos.items()]
    saidas["resumos"] += linhas
    medidos = [x for x in linhas if x["casos"]]
    um = next(iter(modelos.values()))["manifesto"]["configuracao"]
    md = [
        "",
        f"## Condição {condicao} — {_PAPEL.get(condicao, '')}",
        "",
        f"`num_predict` = {um['max_tokens']}; opções = `{um['opcoes_do_protocolo']}`; campos = "
        f"`{um.get('campos_do_protocolo') or {}}`; prazo = {um['timeout_s']:g} s; temperatura 0; "
        f"{um['repeticoes']} repetição(ões).",
        "",
        "### Funil de correção — casos corretos em todas as repetições (%; IC 95%)",
        "",
        _tabela(
            ["Modelo", *(_NOMES[c] for c in CRITERIOS)],
            [
                [x["modelo"], *(_taxa(x[f"{c}_casos"], x["casos"]) for c in CRITERIOS)]
                for x in medidos
            ],
        ),
        "",
        "### Sucesso: todos os casos, sem os 4 de convenção implícita, e por execução",
        "",
        _tabela(
            ["Modelo", "28 casos", "24 casos (sem F4, G4, M1, M2)", "Por execução (%)"],
            [
                [
                    x["modelo"],
                    _taxa(x["resultado_correto_casos"], x["casos"]),
                    _taxa(x["sucesso_sem_convencao_casos"], x["casos_sem_convencao"]),
                    x["resultado_correto_pct_execucoes"],
                ]
                for x in medidos
            ],
        ),
        "",
        "### Desfechos (execuções) e estabilidade (casos)",
        "",
        _tabela(
            [
                "Modelo",
                "Execuções",
                "Respondida",
                "Plano inválido",
                "Não é um plano",
                "Sem resposta no prazo",
                "Paradas por `length`",
                "Com raciocínio",
                "Desfecho estável",
                "Saída idêntica",
            ],
            [
                [
                    x["modelo"],
                    x["execucoes"],
                    x["n_respondida"],
                    x["n_plano_invalido"],
                    x["n_resposta_do_modelo_invalida"],
                    x["n_modelo_indisponivel"],
                    x["paradas_por_length"],
                    x["execucoes_com_raciocinio"],
                    f"{x['casos_com_desfecho_estavel']}/{x['casos']}",
                    f"{x['casos_com_saida_identica']}/{x['casos']}",
                ]
                for x in medidos
            ],
        ),
        "",
        "### Latência e uso do hardware",
        "",
        _tabela(
            [
                "Modelo",
                "Parâmetros",
                "Quant.",
                "Memória (GB)",
                "Fração na GPU",
                "Carga (s)",
                "Mediana (s)",
                "P90 (s)",
                "Máx. (s)",
                "Mediana dos acertos (s)",
                "Tokens gerados (med.)",
                "Tokens/s (med.)",
            ],
            [
                [
                    x["modelo"],
                    x["parametros"],
                    x["quantizacao"],
                    x["memoria_gb"],
                    x["fracao_na_gpu"],
                    x["carga_s"],
                    x["latencia_mediana_s"],
                    x["latencia_p90_s"],
                    x["latencia_max_s"],
                    x["latencia_mediana_dos_acertos_s"],
                    x["tokens_gerados_mediana"],
                    x["tokens_por_segundo_mediana"],
                ]
                for x in medidos
            ],
        ),
    ]
    estouro = [x["modelo"] for x in medidos if x["entrada_mais_teto_cabe_na_janela"] is False]
    if estouro:
        md += [
            "",
            "Atenção: maior entrada + teto de geração passa da janela de contexto em "
            + ", ".join(estouro)
            + ".",
        ]
    nao_medidos = [x for x in linhas if not x["casos"]]
    if nao_medidos:
        md += [
            "",
            "Não medidos: "
            + "; ".join(f"{x['modelo']} ({x['situacao']})" for x in nao_medidos)
            + ".",
        ]

    sucesso = {
        m: acertos(r["execucoes"], "resultado_correto")
        for m, r in modelos.items()
        if r["execucoes"]
    }
    categoria_de = {e["caso"]: e["categoria"] for r in modelos.values() for e in r["execucoes"]}
    implicito = {
        e["caso"] for r in modelos.values() for e in r["execucoes"] if e.get("convencao_implicita")
    }
    linhas_cat = []
    for cat in sorted(set(categoria_de.values())):
        ids = sorted(c for c, k in categoria_de.items() if k == cat)
        linha_md: list[Any] = [cat, len(ids)]
        for m, s in sucesso.items():
            k = sum(s.get(c, False) for c in ids)
            linha_md.append(f"{k}/{len(ids)}")
            saidas["por_categoria"].append(
                {
                    "condicao": condicao,
                    "categoria": cat,
                    "modelo": m,
                    "casos": len(ids),
                    "acertos": k,
                }
            )
        linhas_cat.append(linha_md)
    md += [
        "",
        "### Sucesso por categoria (casos corretos / casos)",
        "",
        _tabela(["Categoria", "n", *sucesso], linhas_cat),
        "",
        "### Sucesso por caso (* = convenção implícita)",
        "",
        _tabela(
            ["Caso", "Categoria", *sucesso],
            [
                [
                    c + ("*" if c in implicito else ""),
                    categoria_de[c],
                    *("✓" if s.get(c) else "✗" for s in sucesso.values()),
                ]
                for c in sorted(categoria_de)
            ],
        ),
    ]
    for m, r in modelos.items():
        motivos: Counter[str] = Counter()
        campos: Counter[str] = Counter()
        for c, es in _por_caso(r["execucoes"]).items():
            saidas["por_caso"].append(
                {
                    "condicao": condicao,
                    "modelo": m,
                    "caso": c,
                    "categoria": es[0]["categoria"],
                    "convencao_implicita": bool(es[0].get("convencao_implicita")),
                    "sucesso": all(e["resultado_correto"] for e in es),
                    "desfechos": " ".join(e["desfecho"] for e in es),
                    "campos_divergentes": " ".join(
                        sorted({x for e in es for x in e["campos_divergentes"]})
                    ),
                    "latencia_mediana_s": round(
                        statistics.median(e["tempo_ms"] for e in es) / 1000, 1
                    ),
                }
            )
        for e in r["execucoes"]:
            if e["desfecho"] == "plano_invalido":
                motivos.update(e["motivos"])
            if e["json_valido"] and not e["plano_correto"]:
                campos.update(e["campos_divergentes"])
        saidas["falhas"] += [
            {"condicao": condicao, "modelo": m, "tipo": tipo, "item": k, "execucoes": v}
            for tipo, contagem in (
                ("motivo_de_rejeicao", motivos),
                ("campo_divergente_do_plano", campos),
            )
            for k, v in contagem.most_common()
        ]
        if motivos or campos:
            md += [
                "",
                f"**{m}** — motivos de rejeição do plano (execuções): "
                + (", ".join(f"`{k}` {v}" for k, v in motivos.most_common(6)) or "nenhum")
                + ". Campos divergentes da referência: "
                + (", ".join(f"`{k}` {v}" for k, v in campos.most_common(6)) or "nenhum")
                + ".",
            ]

    if condicao in COMPARAVEIS and len(sucesso) > 1:
        comuns = sorted(set.intersection(*(set(s) for s in sucesso.values())))
        q = cochran_q([[s[c] for s in sucesso.values()] for c in comuns])
        pares = []
        for a, b in combinations(sucesso, 2):
            so_a = sum(sucesso[a][c] and not sucesso[b][c] for c in comuns)
            so_b = sum(sucesso[b][c] and not sucesso[a][c] for c in comuns)
            pares.append((a, b, so_a, so_b, mcnemar_exato(so_a, so_b)))
        ajustados = holm([p[4] for p in pares])
        for (a, b, so_a, so_b, p), p_holm in zip(pares, ajustados, strict=True):
            saidas["pareadas"].append(
                {
                    "comparacao": "entre_modelos",
                    "condicao": condicao,
                    "a": a,
                    "b": b,
                    "casos": len(comuns),
                    "so_a_acerta": so_a,
                    "so_b_acerta": so_b,
                    "p_mcnemar_exato": round(p, 4),
                    "p_holm": round(p_holm, 4),
                }
            )
        md += [
            "",
            "### Comparação entre modelos",
            "",
            "Q de Cochran (global): "
            + (
                "sem variação entre modelos."
                if q is None
                else f"Q = {q[0]:.2f}, gl = {q[1]}, p = {q[2]:.4f}."
            ),
            "",
            _tabela(
                ["Modelo A", "Modelo B", "Só A acerta", "Só B acerta", "p (McNemar)", "p (Holm)"],
                [
                    [a, b, so_a, so_b, f"{p:.4f}", f"{h:.4f}"]
                    for (a, b, so_a, so_b, p), h in zip(pares, ajustados, strict=True)
                ],
            ),
        ]
    return md


def _secao_entre_condicoes(
    dados: dict[str, dict[str, dict[str, Any]]], saidas: dict[str, list[dict[str, Any]]]
) -> list[str]:
    md: list[str] = []
    if "P" in dados and "N" in dados:
        linhas = []
        for m in dados["P"]:
            if (
                m not in dados["N"]
                or not dados["P"][m]["execucoes"]
                or not dados["N"][m]["execucoes"]
            ):
                continue
            p, n = (acertos(dados[c][m]["execucoes"], "resultado_correto") for c in ("P", "N"))
            comuns = sorted(set(p) & set(n))
            so_p = sum(p[c] and not n[c] for c in comuns)
            so_n = sum(n[c] and not p[c] for c in comuns)
            valor = mcnemar_exato(so_p, so_n)
            mediana = {
                c: statistics.median(e["tempo_ms"] for e in dados[c][m]["execucoes"]) / 1000
                for c in ("P", "N")
            }
            saidas["pareadas"].append(
                {
                    "comparacao": "P_x_N",
                    "condicao": "P x N",
                    "a": f"{m} (P)",
                    "b": f"{m} (N)",
                    "casos": len(comuns),
                    "so_a_acerta": so_p,
                    "so_b_acerta": so_n,
                    "p_mcnemar_exato": round(valor, 4),
                }
            )
            linhas.append(
                [
                    m,
                    f"{sum(p.values())}/{len(p)}",
                    f"{sum(n.values())}/{len(n)}",
                    so_p,
                    so_n,
                    f"{valor:.4f}",
                    f"{mediana['P']:.1f}",
                    f"{mediana['N']:.1f}",
                ]
            )
        md += [
            "",
            "## P × N: efeito de desligar o raciocínio, por modelo",
            "",
            _tabela(
                [
                    "Modelo",
                    "Sucesso em P",
                    "Sucesso em N",
                    "Só P acerta",
                    "Só N acerta",
                    "p (McNemar)",
                    "Mediana P (s)",
                    "Mediana N (s)",
                ],
                linhas,
            ),
        ]
    if "P" in dados and "A" in dados:
        linhas = []
        for m, r in dados["A"].items():
            if m not in dados["P"] or not r["execucoes"]:
                continue
            p1 = {e["caso"]: e for e in dados["P"][m]["execucoes"] if e["repeticao"] == 1}
            a1 = {e["caso"]: e for e in r["execucoes"] if e["repeticao"] == 1}
            comuns = sorted(set(p1) & set(a1))
            no_prazo = [c for c in comuns if a1[c]["tempo_ms"] / 1000 <= PRAZO_DE_USO_S]
            linhas.append(
                [
                    m,
                    f"{sum(p1[c]['resultado_correto'] for c in comuns)}/{len(comuns)}",
                    f"{sum(a1[c]['resultado_correto'] for c in comuns)}/{len(comuns)}",
                    f"{sum(a1[c]['resultado_correto'] for c in no_prazo)}/{len(comuns)}",
                    len(comuns) - len(no_prazo),
                    f"{statistics.median(p1[c]['tempo_ms'] for c in comuns) / 1000:.1f}",
                    f"{statistics.median(a1[c]['tempo_ms'] for c in comuns) / 1000:.1f}",
                ]
            )
        md += [
            "",
            "## A × P (repetição 1): efeito de ampliar tokens, janela e prazo",
            "",
            "Diagnóstico: três parâmetros mudam juntos; não entra na comparação entre modelos.",
            "",
            _tabela(
                [
                    "Modelo",
                    "Sucesso em P (rep. 1)",
                    "Sucesso em A",
                    "Sucesso em A em até 120 s",
                    "Execuções de A acima de 120 s",
                    "Mediana P (s)",
                    "Mediana A (s)",
                ],
                linhas,
            ),
        ]
    return md


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    dados = carregar()
    if not dados:
        print(f"nenhuma rodada em {SAIDA}")
        return 1
    saidas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    md: list[str] = [
        "# Tabelas do benchmark (geradas por `benchmark/relatorio.py`)",
        "",
        "Não editar à mão. Unidade de análise: o caso (acerto = correto em todas as repetições). "
        "IC 95% de Wilson. Protocolo em [`PROTOCOLO.md`](PROTOCOLO.md); leitura e limitações em "
        "[`RESULTADOS.md`](RESULTADOS.md).",
    ]
    for condicao in sorted(dados, key=lambda c: "PNA".find(c)):
        md += _secao_da_condicao(condicao, dados[condicao], saidas)
    md += _secao_entre_condicoes(dados, saidas)

    # Bloco de sistema: nao depende de modelo; confere-se que e igual em todas as rodadas.
    pastas = [p for p in sorted(SAIDA.iterdir()) if p.is_dir() and not p.name.startswith("_")]
    sistemas = [json.loads((p / "sistema.json").read_text("utf-8")) for p in pastas]
    sistema = sistemas[0]
    md += [
        "",
        "## Bloco de sistema (sem LLM)",
        "",
        f"Idêntico nas {len(sistemas)} rodadas: "
        f"{'sim' if all(s == sistema for s in sistemas) else 'NÃO'}. "
        f"Situação exata: {sum(s['situacao_exata'] for s in sistema)}/{len(sistema)}. "
        "(A abstenção é condição de entrada no bloco, não resultado.)",
        "",
        _tabela(
            ["Caso", "Categoria", "Pergunta", "Situação ideal", "Situação obtida", "Exata"],
            [
                [
                    s["caso"],
                    s["categoria"],
                    s["pergunta"],
                    s["situacao_ideal"],
                    s["situacao"],
                    "✓" if s["situacao_exata"] else "✗",
                ]
                for s in sistema
            ],
        ),
        "",
    ]
    _gravar("resumo_modelos.csv", saidas["resumos"])
    _gravar("por_categoria.csv", saidas["por_categoria"])
    _gravar("por_caso.csv", saidas["por_caso"])
    _gravar("falhas.csv", saidas["falhas"])
    _gravar("comparacoes_pareadas.csv", saidas["pareadas"])
    _gravar("sistema.csv", sistema)
    (DESTINO / "TABELAS.md").write_text("\n".join(md), "utf-8")
    print(f"{len(saidas['resumos'])} linhas de resumo; tabelas em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
