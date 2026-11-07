"""Descoberta de modelos do Bedrock: so leitura, sem rede e sem credencial real.

Os clientes usam credenciais falsas e o `Stubber` do botocore: nenhuma requisicao sai da maquina.
"""

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

_CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "aws" / "descobrir_modelos_bedrock.py"


def _modulo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("descobrir_modelos_bedrock", _CAMINHO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


D = _modulo()


@pytest.fixture
def sessao(monkeypatch: pytest.MonkeyPatch) -> Iterator[boto3.Session]:
    # Nada do ambiente real (perfil, cache SSO, variaveis) entra no teste.
    for var in (
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_CONFIG_FILE",
        "AWS_SHARED_CREDENTIALS_FILE",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(Path(__file__).parent / "inexistente.cfg"))
    yield D.proteger(
        boto3.Session(
            aws_access_key_id="falso",
            aws_secret_access_key="falso",
            aws_session_token="falso",
            region_name="us-east-1",
        )
    )


# --- trava de somente leitura ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("servico", "operacao", "params"),
    [
        ("bedrock-runtime", "invoke_model", {"modelId": "x", "body": b"{}"}),
        ("bedrock-runtime", "converse", {"modelId": "x", "messages": []}),
        (
            "bedrock",
            "create_inference_profile",
            {"inferenceProfileName": "x", "modelSource": {"copyFrom": "arn:aws:bedrock:::x"}},
        ),
        ("bedrock", "put_use_case_for_model_access", {"formData": b"{}"}),
        ("ec2", "start_instances", {"InstanceIds": ["i-0"]}),
    ],
)
def test_trava_barra_inferencia_e_escrita_antes_de_sair(
    sessao: boto3.Session, servico: str, operacao: str, params: dict[str, object]
) -> None:
    cliente = sessao.client(servico)

    def nunca_enviar(**_: object) -> None:
        raise AssertionError("a requisicao chegou a ser montada para envio")

    # Se a trava falhasse, a requisicao seria barrada aqui, ainda dentro do processo.
    cliente.meta.events.register("before-send", nunca_enviar)
    with pytest.raises(D.OperacaoProibida):
        getattr(cliente, operacao)(**params)


def test_controle_sem_trava_a_requisicao_seria_montada() -> None:
    # Prova que o teste acima nao passa por acaso: sem `proteger`, a chamada chega ao envio.
    s = boto3.Session(aws_access_key_id="f", aws_secret_access_key="f", region_name="us-east-1")
    cliente = s.client("bedrock-runtime")

    def nunca_enviar(**_: object) -> None:
        raise AssertionError("montada para envio")

    cliente.meta.events.register("before-send", nunca_enviar)
    with pytest.raises(AssertionError, match="montada para envio"):
        cliente.invoke_model(modelId="x", body=b"{}")


def test_operacoes_permitidas_sao_so_leitura() -> None:
    for op in D.OPERACOES_PERMITIDAS:
        assert op.split(".")[1].startswith(("List", "Get")), op
    assert not any(op.startswith("bedrock-runtime.") for op in D.OPERACOES_PERMITIDAS)


def test_leitura_permitida_passa_pela_trava(sessao: boto3.Session) -> None:
    bedrock = sessao.client("bedrock")
    with Stubber(bedrock) as stub:
        stub.add_response("list_foundation_models", {"modelSummaries": []})
        assert D.listar_modelos(bedrock) == []


# --- leitura ---------------------------------------------------------------------------------------


def _perfil(pid: str, *arns: str) -> dict[str, object]:
    return {
        "inferenceProfileName": pid,
        "inferenceProfileArn": f"arn:aws:bedrock:us-east-1::inference-profile/{pid}",
        "inferenceProfileId": pid,
        "status": "ACTIVE",
        "type": "SYSTEM_DEFINED",
        "models": [{"modelArn": a} for a in arns],
    }


def test_inference_profiles_paginados(sessao: boto3.Session) -> None:
    bedrock = sessao.client("bedrock")
    with Stubber(bedrock) as stub:
        stub.add_response(
            "list_inference_profiles",
            {
                "inferenceProfileSummaries": [
                    _perfil("us.a", "arn:aws:bedrock:us-east-1::foundation-model/a")
                ],
                "nextToken": "t",
            },
            {"typeEquals": "SYSTEM_DEFINED"},
        )
        stub.add_response(
            "list_inference_profiles",
            {
                "inferenceProfileSummaries": [
                    _perfil("us.b", "arn:aws:bedrock:us-east-1::foundation-model/b")
                ]
            },
            {"typeEquals": "SYSTEM_DEFINED", "nextToken": "t"},
        )
        assert [p["inferenceProfileId"] for p in D.listar_perfis(bedrock)] == ["us.a", "us.b"]


def test_disponibilidade_registra_o_codigo_do_erro(sessao: boto3.Session) -> None:
    bedrock = sessao.client("bedrock")
    with Stubber(bedrock) as stub:
        stub.add_client_error("get_foundation_model_availability", "AccessDeniedException")
        assert D.disponibilidade(bedrock, "m") == {"erro_disponibilidade": "AccessDeniedException"}


def test_consolidar_casa_modelo_e_perfil_e_destaca_o_llama4_scout() -> None:
    scout = "meta.llama4-scout-17b-instruct-v1:0"
    modelos = [
        {
            "modelId": "amazon.nova-micro-v1:0",
            "providerName": "Amazon",
            "inputModalities": ["TEXT"],
            "outputModalities": ["TEXT"],
            "inferenceTypesSupported": ["ON_DEMAND"],
            "modelLifecycle": {"status": "ACTIVE"},
        },
        {
            "modelId": scout,
            "providerName": "Meta",
            "inputModalities": ["TEXT", "IMAGE"],
            "outputModalities": ["TEXT"],
            "inferenceTypesSupported": ["INFERENCE_PROFILE"],
            "modelLifecycle": {"status": "ACTIVE"},
        },
        {
            "modelId": "stability.sd3",
            "providerName": "Stability AI",
            "inputModalities": ["TEXT"],
            "outputModalities": ["IMAGE"],
            "inferenceTypesSupported": ["PROVISIONED"],
            "modelLifecycle": {"status": "LEGACY"},
        },
    ]
    perfis = [
        _perfil(
            "us.meta.llama4-scout-17b-instruct-v1:0",
            f"arn:aws:bedrock:us-east-1::foundation-model/{scout}",
            f"arn:aws:bedrock:us-west-2::foundation-model/{scout}",
        )
    ]
    acesso = {scout: {"authorizationStatus": "AUTHORIZED"}}
    linhas = D.consolidar(modelos, perfis, acesso)
    assert linhas[0]["model_id"] == scout and linhas[0]["destaque"]
    assert linhas[0]["invocavel_por"] == "inference_profile"
    assert linhas[0]["inference_profiles"] == "us.meta.llama4-scout-17b-instruct-v1:0"
    assert linhas[0]["authorizationStatus"] == "AUTHORIZED"
    por_id = {x["model_id"]: x for x in linhas}
    assert por_id["amazon.nova-micro-v1:0"]["invocavel_por"] == "on_demand"
    assert por_id["stability.sd3"]["invocavel_por"] == "nenhum_sem_provisionamento"
    assert not por_id["stability.sd3"]["texto_para_texto"]


def test_precos_le_a_price_list_sem_interpretar(sessao: boto3.Session) -> None:
    pricing = sessao.client("pricing", region_name="us-east-1")
    item = {
        "product": {
            "attributes": {
                "model": "Llama 4 Scout",
                "provider": "Meta",
                "usagetype": "USE1-x-input-tokens",
            }
        },
        "terms": {
            "OnDemand": {
                "t": {
                    "priceDimensions": {
                        "d": {
                            "description": "por 1K tokens de entrada",
                            "unit": "1K tokens",
                            "pricePerUnit": {"USD": "0.0001700000"},
                        }
                    }
                }
            }
        },
    }
    filtros = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}]
    with Stubber(pricing) as stub:
        stub.add_response(
            "get_products",
            {"PriceList": [json.dumps(item)]},
            {"ServiceCode": "AmazonBedrock", "Filters": filtros, "MaxResults": 100},
        )
        stub.add_response(
            "get_products",
            {"PriceList": []},
            {"ServiceCode": "AmazonBedrockFoundationModels", "Filters": filtros, "MaxResults": 100},
        )
        sessao_falsa = type("S", (), {"client": lambda self, *a, **k: pricing})()
        linhas = D.precos(sessao_falsa, "us-east-1")
    assert linhas == [
        {
            "servico": "AmazonBedrock",
            "modelo": "Llama 4 Scout",
            "provedor": "Meta",
            "uso": "USE1-x-input-tokens",
            "tipo": None,
            "descricao": "por 1K tokens de entrada",
            "unidade": "1K tokens",
            "usd": "0.0001700000",
        }
    ]


def test_mensagens_de_falha_nao_ecoam_segredo() -> None:
    erro = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "token=SEGREDO"}},
        "ListFoundationModels",
    )
    msg = D.explicar_falha(erro, "tcc-bedrock")
    assert "AccessDeniedException" in msg and "SEGREDO" not in msg

    class SSOTokenLoadError(Exception):
        pass

    assert "aws sso login --profile tcc-bedrock" in D.explicar_falha(
        SSOTokenLoadError(), "tcc-bedrock"
    )
