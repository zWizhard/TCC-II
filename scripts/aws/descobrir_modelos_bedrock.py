#!/usr/bin/env python3
"""Descobre, SO LENDO, os modelos e inference profiles do Bedrock acessiveis pelo perfil do TCC.

    aws sso login --profile tcc-bedrock --use-device-code      (o autor, no navegador)
    .venv/Scripts/python.exe scripts/aws/descobrir_modelos_bedrock.py [--precos]

Nao faz inferencia, nao cria nem altera recurso algum. A garantia nao e so de intencao: a sessao
boto3 recebe uma trava (`proteger`) que barra, ANTES de qualquer requisicao sair, toda operacao
fora de `OPERACOES_PERMITIDAS` — em particular todas as do `bedrock-runtime` (InvokeModel,
Converse...), que sao as cobradas.

Credenciais: as temporarias do perfil SSO, que a propria CLI guarda em ~/.aws/sso/cache. Nada e
lido do `.env` nem gravado no repositorio. A identidade (ARN, conta) so aparece no terminal; o CSV
versionado traz apenas o catalogo de modelos.

Saidas (docs/data/raw/diagnostics/):
- `<data>_bedrock_modelos.csv`: um modelo por linha — modalidades, tipos de inferencia, ciclo de
  vida, inference profiles que o servem e o estado de acesso informado pela AWS para esta conta;
- `<data>_bedrock_precos.csv` (com `--precos`): os itens da AWS Price List para o Bedrock em
  us-east-1, como vieram. O casamento preco x modelo fica para a analise: a lista nao usa o id.

O que este script NAO responde (fica para a analise, com a documentacao da AWS): suporte a saida
estruturada/uso de ferramenta por modelo e qualidade para o dominio. A permissao de invocar so se
prova invocando; isso exige autorizacao do autor (custo).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "docs" / "data" / "raw" / "diagnostics"
PERFIL = "tcc-bedrock"
REGIAO = "us-east-1"
# servico.Operacao, como o botocore nomeia o evento `before-call.<servico>.<Operacao>`.
OPERACOES_PERMITIDAS = frozenset(
    {
        "sts.GetCallerIdentity",
        "bedrock.ListFoundationModels",
        "bedrock.ListInferenceProfiles",
        "bedrock.GetFoundationModelAvailability",
        "pricing.GetProducts",
    }
)
# Candidato citado pelo orientador; entra na lista com destaque, sem ser obrigatorio.
DESTAQUES = ("llama4-scout",)
_CODIGOS_DE_SESSAO = ("SSOTokenLoadError", "UnauthorizedSSOTokenError", "TokenRetrievalError")


class OperacaoProibida(RuntimeError):
    """Uma chamada fora da allowlist de leitura foi tentada e barrada antes de sair."""


def _barrar(event_name: str, **_: Any) -> None:
    operacao = ".".join(event_name.split(".")[1:3])
    if operacao not in OPERACOES_PERMITIDAS:
        raise OperacaoProibida(f"operacao fora da allowlist de leitura: {operacao}")


def proteger(sessao: boto3.Session) -> boto3.Session:
    """Registra a trava na sessao: vale para todo cliente criado a partir dela."""
    # No no mais especifico e primeira da fila: nenhum outro handler (nem o Stubber dos testes)
    # responde antes dela.
    sessao.events.register_first("before-call.*.*", _barrar)
    return sessao


def abrir_sessao(perfil: str, regiao: str) -> boto3.Session:
    return proteger(boto3.Session(profile_name=perfil, region_name=regiao))


# --- leitura --------------------------------------------------------------------------------------


def _paginas(cliente: Any, operacao: str, chave: str, **params: Any) -> Iterator[dict[str, Any]]:
    token: str | None = None
    while True:
        resposta = getattr(cliente, operacao)(**params, **({"nextToken": token} if token else {}))
        yield from resposta.get(chave, [])
        token = resposta.get("nextToken")
        if not token:
            return


def listar_modelos(bedrock: Any) -> list[dict[str, Any]]:
    return list(bedrock.list_foundation_models().get("modelSummaries", []))


def listar_perfis(bedrock: Any) -> list[dict[str, Any]]:
    return list(
        _paginas(
            bedrock,
            "list_inference_profiles",
            "inferenceProfileSummaries",
            typeEquals="SYSTEM_DEFINED",
        )
    )


def disponibilidade(bedrock: Any, model_id: str) -> dict[str, str]:
    """Estado de acesso do modelo nesta conta, como a AWS o declara. Erro vira o codigo do erro."""
    try:
        r = bedrock.get_foundation_model_availability(modelId=model_id)
    except ClientError as exc:
        return {"erro_disponibilidade": exc.response.get("Error", {}).get("Code", "ClientError")}
    campos = (
        "agreementAvailability",
        "authorizationStatus",
        "entitlementAvailability",
        "regionAvailability",
    )
    saida: dict[str, str] = {}
    for campo in campos:
        valor = r.get(campo)
        saida[campo] = str(valor.get("status", valor)) if isinstance(valor, dict) else str(valor)
    return saida


def _base(model_id: str) -> str:
    """'meta.llama4-scout-17b-instruct-v1:0' a partir de um ARN ou id, sem prefixo de regiao."""
    return model_id.rsplit("/", 1)[-1]


def consolidar(
    modelos: list[dict[str, Any]],
    perfis: list[dict[str, Any]],
    acesso: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Uma linha por modelo, com os inference profiles que o servem e o estado de acesso."""
    perfis_do_modelo: dict[str, list[str]] = {}
    for p in perfis:
        for m in p.get("models", []):
            perfis_do_modelo.setdefault(_base(m.get("modelArn", "")), []).append(
                p["inferenceProfileId"]
            )
    linhas = []
    for m in modelos:
        mid = m["modelId"]
        tipos = list(m.get("inferenceTypesSupported", []))
        perfis_ids = sorted(set(perfis_do_modelo.get(mid, [])))
        texto = "TEXT" in m.get("inputModalities", []) and "TEXT" in m.get("outputModalities", [])
        linhas.append(
            {
                "model_id": mid,
                "provedor": m.get("providerName"),
                "nome": m.get("modelName"),
                "entrada": "|".join(m.get("inputModalities", [])),
                "saida": "|".join(m.get("outputModalities", [])),
                "tipos_de_inferencia": "|".join(tipos),
                "streaming": m.get("responseStreamingSupported"),
                "ciclo_de_vida": (m.get("modelLifecycle") or {}).get("status"),
                "inference_profiles": "|".join(perfis_ids),
                # Sob demanda direto, ou so por inference profile (caso dos modelos novos).
                "invocavel_por": (
                    "on_demand"
                    if "ON_DEMAND" in tipos
                    else "inference_profile"
                    if perfis_ids
                    else "nenhum_sem_provisionamento"
                ),
                "texto_para_texto": texto,
                "destaque": any(d in mid for d in DESTAQUES),
                **acesso.get(mid, {}),
            }
        )
    return sorted(linhas, key=lambda x: (not x["destaque"], str(x["provedor"]), x["model_id"]))


def precos(sessao: boto3.Session, regiao: str) -> list[dict[str, Any]]:
    """Itens da Price List do Bedrock na regiao, como vieram (API gratuita, so leitura)."""
    import json

    cliente = sessao.client("pricing", region_name="us-east-1")  # endpoint unico da Price List
    filtros = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": regiao}]
    linhas: list[dict[str, Any]] = []
    for codigo in ("AmazonBedrock", "AmazonBedrockFoundationModels"):
        token: str | None = None
        while True:
            params: dict[str, Any] = {"ServiceCode": codigo, "Filters": filtros, "MaxResults": 100}
            if token:
                params["NextToken"] = token
            r = cliente.get_products(**params)
            for bruto in r.get("PriceList", []):
                item = json.loads(bruto)
                attrs = item.get("product", {}).get("attributes", {})
                for termo in item.get("terms", {}).get("OnDemand", {}).values():
                    for dimensao in termo.get("priceDimensions", {}).values():
                        linhas.append(
                            {
                                "servico": codigo,
                                "modelo": attrs.get("model") or attrs.get("titanModel"),
                                "provedor": attrs.get("provider"),
                                "uso": attrs.get("usagetype"),
                                "tipo": attrs.get("inferenceType") or attrs.get("featuretype"),
                                "descricao": dimensao.get("description"),
                                "unidade": dimensao.get("unit"),
                                "usd": dimensao.get("pricePerUnit", {}).get("USD"),
                            }
                        )
            token = r.get("NextToken")
            if not token:
                break
    return linhas


# --- saida ----------------------------------------------------------------------------------------


def _gravar(caminho: Path, linhas: list[dict[str, Any]]) -> None:
    campos = list(dict.fromkeys(k for linha in linhas for k in linha))
    with caminho.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def explicar_falha(exc: Exception, perfil: str) -> str:
    """Mensagem para o autor; nunca ecoa token nem credencial."""
    nome = type(exc).__name__
    if nome in _CODIGOS_DE_SESSAO or "SSO" in nome:
        return (
            f"Sessao SSO ausente ou expirada. Rode: aws sso login --profile {perfil} "
            "--use-device-code"
        )
    if isinstance(exc, ClientError):
        codigo = exc.response.get("Error", {}).get("Code", "ClientError")
        operacao = exc.operation_name
        return (
            f"A AWS recusou {operacao}: {codigo}. Permissao do papel a confirmar com o orientador."
        )
    return f"Falha: {nome}."


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--perfil", default=PERFIL)
    p.add_argument("--regiao", default=REGIAO)
    p.add_argument("--precos", action="store_true", help="consulta tambem a AWS Price List")
    p.add_argument(
        "--sem-disponibilidade",
        action="store_true",
        help="nao consulta o estado de acesso modelo a modelo",
    )
    args = p.parse_args()
    try:
        sessao = abrir_sessao(args.perfil, args.regiao)
        quem = sessao.client("sts").get_caller_identity()
        print(f"identidade: {quem['Arn']}")  # so no terminal; nao vai para o CSV
        bedrock = sessao.client("bedrock")
        modelos = listar_modelos(bedrock)
        perfis = listar_perfis(bedrock)
        acesso = (
            {}
            if args.sem_disponibilidade
            else {m["modelId"]: disponibilidade(bedrock, m["modelId"]) for m in modelos}
        )
        linhas = consolidar(modelos, perfis, acesso)
        hoje = date.today().isoformat()
        destino = SAIDA / f"{hoje}_bedrock_modelos.csv"
        _gravar(destino, linhas)
        texto = [x for x in linhas if x["texto_para_texto"] and x["ciclo_de_vida"] == "ACTIVE"]
        print(
            f"{len(modelos)} modelos, {len(perfis)} inference profiles; "
            f"{len(texto)} ativos de texto para texto -> {destino}"
        )
        if args.precos:
            try:
                itens = precos(sessao, args.regiao)
                _gravar(SAIDA / f"{hoje}_bedrock_precos.csv", itens)
                print(f"{len(itens)} itens de preco -> {SAIDA / f'{hoje}_bedrock_precos.csv'}")
            except ClientError as exc:
                print(explicar_falha(exc, args.perfil))
        return 0
    except OperacaoProibida:
        raise  # defeito do script: nunca deve acontecer, e nao deve ser engolido
    except (BotoCoreError, ClientError) as exc:
        print(explicar_falha(exc, args.perfil))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
