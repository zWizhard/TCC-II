#!/usr/bin/env python3
"""Baixa a malha territorial do IBGE usada pelo mapa (coropletico municipal e contorno das UFs).

    .venv/Scripts/python.exe scripts/etl/baixar_malha_ibge.py

Fonte: API de malhas do IBGE (servicodados.ibge.gov.br), versao v4, qualidade minima, GeoJSON.
O banco do IESB nao tem poligono (so latitude/longitude em `municipio`), entao a geometria e a
unica peca do projeto que vem de fora dele. Roda 1x: a malha e estatica.

Por que v4 e nao v3 (medido em 2026-10-07):
- v3 serve a malha de 2022 (5.570 feicoes) e NAO tem Boa Esperanca do Norte/MT (5101837), que
  existe em `municipio` e em `ibge_populacao_estimada` de 2024;
- v4 tem 5.571 feicoes e casa 1:1 com as 5.571 unidades de `municipio` (0 orfaos nos dois
  sentidos — ver scripts/analise/auditar_mapas.py).
A API v4 ignora o parametro `periodo` e nao declara o ano da edicao: fica registrado como
"A confirmar" no manifesto, junto do hash do arquivo, que e o que identifica a versao usada.

Os arquivos sao gravados como vieram (sem simplificar, reprojetar nem renomear propriedade):
a chave de cada feicao e `properties.codarea`, texto, 7 digitos no municipio e 2 na UF.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "data" / "reference" / "malha"
MANIFESTO = DESTINO / "MANIFEST.json"

_BASE = "https://servicodados.ibge.gov.br/api/v4/malhas/paises/BR"
_FORMATO = "formato=application/vnd.geo%2Bjson&qualidade=minima"

# arquivo -> (URL, feicoes esperadas, digitos de `codarea`)
ALVOS: dict[str, tuple[str, int, int]] = {
    "municipios.geojson": (f"{_BASE}?intrarregiao=municipio&{_FORMATO}", 5_571, 7),
    "ufs.geojson": (f"{_BASE}?intrarregiao=UF&{_FORMATO}", 27, 2),
}


def baixar(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as resposta:  # noqa: S310 — URL fixa, https
        corpo: bytes = resposta.read()
    # A API devolve gzip mesmo sem Accept-Encoding.
    return gzip.decompress(corpo) if corpo[:2] == b"\x1f\x8b" else corpo


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for nome, (url, esperadas, digitos) in ALVOS.items():
        corpo = baixar(url)
        feicoes = json.loads(corpo)["features"]
        codigos = [f["properties"]["codarea"] for f in feicoes]
        # A malha so e gravada se tiver a forma que o mapa e o JOIN pressupoem.
        problemas = []
        if len(feicoes) != esperadas:
            problemas.append(f"{len(feicoes)} feicoes, esperadas {esperadas}")
        if len(set(codigos)) != len(codigos):
            problemas.append("codarea duplicado")
        if any(not (isinstance(c, str) and c.isdigit() and len(c) == digitos) for c in codigos):
            problemas.append(f"codarea fora do formato de {digitos} digitos em texto")
        if problemas:
            print(f"{nome}: malha recusada — {'; '.join(problemas)}", file=sys.stderr)
            return 1
        (DESTINO / nome).write_bytes(corpo)
        arquivos.append(
            {
                "arquivo": nome,
                "url": url,
                "feicoes": len(feicoes),
                "bytes": len(corpo),
                "bytes_gzip": len(gzip.compress(corpo)),
                "sha256": hashlib.sha256(corpo).hexdigest(),
            }
        )
        print(f"{nome}: {len(feicoes)} feicoes, {len(corpo):,} bytes")

    MANIFESTO.write_text(
        json.dumps(
            {
                "fonte": "IBGE — API de malhas v4 (servicodados.ibge.gov.br)",
                "qualidade": "minima",
                "chave": "properties.codarea (texto; 7 digitos no municipio, 2 na UF)",
                "edicao_da_malha": "A confirmar — a API v4 nao declara o ano nem aceita 'periodo'",
                "baixado_em": datetime.now(UTC).isoformat(timespec="seconds"),
                "arquivos": arquivos,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"manifesto em {MANIFESTO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
