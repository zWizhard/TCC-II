"""Provedor de LLM: fabrica, configuracao e independencia de modelo. Nenhum teste abre rede."""

from pathlib import Path

import pytest

import api
import api.analista
from api.analista.llm import criar_provedor
from api.config import Settings
from api.erros import ModeloIndisponivel


def test_configuracao_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in ("LLM_PROVIDER", "LLM_TIMEOUT_SECONDS", "ANALISTA_MAX_LINHAS"):
        monkeypatch.delenv(nome, raising=False)
    padrao = Settings()
    assert (padrao.llm_provider, padrao.analista_max_linhas) == ("bedrock", 1000)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("ANALISTA_MAX_LINHAS", "50")
    s = Settings()
    assert (s.llm_timeout_seconds, s.analista_max_linhas) == (30, 50)
    with pytest.raises(ValueError):
        Settings(analista_max_linhas=1001)  # nenhuma configuracao passa do teto rigido


@pytest.mark.parametrize("nome", ["bedrok", "ollama", "api-paga", ""])
def test_provedor_desconhecido_e_recusado_na_configuracao(
    nome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erro de digitacao no provedor falha na partida, nao vira 503 silencioso."""
    monkeypatch.setenv("LLM_PROVIDER", nome)
    with pytest.raises(ValueError):
        Settings()


def test_provedor_nao_implementado_e_503_explicado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Bedrock ainda nao tem fabrica: 503 com mensagem curta, sem tentar a rede."""
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    provedor = criar_provedor(Settings())  # criar nao falha: so a chamada ao modelo
    with pytest.raises(ModeloIndisponivel) as exc:
        provedor.gerar_json("sistema", "{}", {})
    assert (exc.value.status, exc.value.codigo) == (503, "modelo_indisponivel")
    assert "ainda não está disponível" in exc.value.mensagem


def test_codigo_do_analista_nao_depende_do_nome_de_modelo() -> None:
    """Nenhum modulo do pacote cita um modelo concreto nem ramifica pelo nome dele."""
    pasta = Path(api.analista.__file__).parent
    fontes = "\n".join(p.read_text(encoding="utf-8") for p in pasta.glob("*.py")).lower()
    for nome in ("llama", "qwen", "mistral", "gemma", "phi3", "deepseek", "gpt-"):
        assert nome not in fontes, nome


def test_api_nao_tem_resquicio_de_ollama() -> None:
    """O Ollama foi removido do projeto (decisao do autor, 2026-11-06): nem codigo, nem config."""
    pasta = Path(api.__file__).parent
    for arquivo in pasta.rglob("*.py"):
        assert "ollama" not in arquivo.read_text(encoding="utf-8").lower(), arquivo
    assert not [c for c in Settings.model_fields if "ollama" in c]
