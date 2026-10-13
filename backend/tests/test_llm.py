import json

import httpx
import pytest

from app.config import settings
from app.services.ai import llm


@pytest.fixture
def hermes(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "hermes")
    monkeypatch.setattr(settings, "hermes_url", "http://hermes.test:8643/")
    monkeypatch.setattr(settings, "hermes_token", "t" * 40)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_hermes_requete_exacte(hermes):
    vu = {}

    def handler(request):
        vu["url"] = str(request.url)
        vu["auth"] = request.headers["authorization"]
        vu["body"] = json.loads(request.content)
        return httpx.Response(200, json={"reply": "  Madame, Monsieur  "})

    out = llm._hermes_chat("S" * 9000, "U" * 9000, client=_client(handler))

    assert out == "Madame, Monsieur"
    assert vu["url"] == "http://hermes.test:8643/chat"
    assert vu["auth"] == "Bearer " + "t" * 40
    msgs = vu["body"]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "S" * 8000
    assert msgs[1]["content"] == "Compris."
    assert msgs[2]["content"] == "U" * 8000


def test_hermes_champ_error_leve_llmerror(hermes):
    c = _client(lambda r: httpx.Response(200, json={"error": "quota"}))
    with pytest.raises(llm.LLMError, match="quota"):
        llm._hermes_chat("s", "u", client=c)


def test_hermes_http_500_leve_llmerror(hermes):
    c = _client(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(llm.LLMError, match="500"):
        llm._hermes_chat("s", "u", client=c)


def test_hermes_injoignable_leve_llmerror(hermes):
    def handler(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(llm.LLMError, match="injoignable"):
        llm._hermes_chat("s", "u", client=_client(handler))


def test_hermes_reponse_vide_leve_llmerror(hermes):
    c = _client(lambda r: httpx.Response(200, json={"reply": "   "}))
    with pytest.raises(llm.LLMError, match="vide"):
        llm._hermes_chat("s", "u", client=c)


def test_hermes_non_configure_leve_llmerror(monkeypatch):
    monkeypatch.setattr(settings, "hermes_url", "")
    monkeypatch.setattr(settings, "hermes_token", "")
    with pytest.raises(llm.LLMError, match="HERMES_URL"):
        llm._hermes_chat("s", "u")


def test_chat_choisit_le_fournisseur(monkeypatch):
    monkeypatch.setattr(llm, "_hermes_chat", lambda s, u: "hermes")
    monkeypatch.setattr(llm, "_gemini_chat", lambda s, u: "gemini")
    monkeypatch.setattr(settings, "llm_provider", "Hermes")
    assert llm.chat("s", "u") == "hermes"
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    assert llm.chat("s", "u") == "gemini"
    monkeypatch.setattr(settings, "llm_provider", "openai")
    with pytest.raises(llm.LLMError, match="LLM_PROVIDER"):
        llm.chat("s", "u")


def test_lettre_tronque_cv_et_description(monkeypatch):
    from app.services.ai import letter_generator

    vu = {}

    def fake_chat(system_prompt, user_prompt):
        vu["system"], vu["user"] = system_prompt, user_prompt
        return "```\nBonjour\n```"

    monkeypatch.setattr(letter_generator, "chat", fake_chat)
    out = letter_generator.generate_cover_letter("C" * 7000, "SRE", "Acme", "D" * 6000, "CDI")
    assert out == "Bonjour"
    assert "C" * 6000 in vu["system"] and "C" * 6001 not in vu["system"]
    assert "D" * 5000 in vu["user"] and "D" * 5001 not in vu["user"]
    assert "sans préambule" in vu["user"]


def test_nettoyer_reponse():
    from app.services.ai.letter_generator import nettoyer_reponse

    assert nettoyer_reponse("```text\nLettre\n```") == "Lettre"
    assert nettoyer_reponse("  Lettre  ") == "Lettre"
