"""Appel au modèle de langage : Hermes (via hermes-ha-proxy sur le LAN) ou Gemini.

Le proxy d'Hermes n'accepte que les rôles user/assistant et tronque chaque message à
8000 caractères : les consignes « système » partent donc dans un premier message user.
"""
import httpx

from app.config import settings

HERMES_TIMEOUT = 300
MAX_MESSAGE = 8000
_GEMINI_MODEL = "gemini-1.5-flash"


class LLMError(RuntimeError):
    """Le modèle n'a pas pu produire de réponse (configuration, réseau, erreur distante)."""


def chat(system_prompt: str, user_prompt: str) -> str:
    provider = settings.llm_provider.strip().lower()
    if provider == "hermes":
        return _hermes_chat(system_prompt, user_prompt)
    if provider == "gemini":
        return _gemini_chat(system_prompt, user_prompt)
    raise LLMError(f"LLM_PROVIDER inconnu : {settings.llm_provider!r} (attendu : hermes ou gemini)")


def _hermes_chat(system_prompt: str, user_prompt: str, client: httpx.Client | None = None) -> str:
    if not settings.hermes_url or not settings.hermes_token:
        raise LLMError("HERMES_URL ou HERMES_TOKEN absent : configurez l'accès à Hermes.")
    payload = {
        "messages": [
            {"role": "user", "content": system_prompt[:MAX_MESSAGE]},
            {"role": "assistant", "content": "Compris."},
            {"role": "user", "content": user_prompt[:MAX_MESSAGE]},
        ]
    }
    own_client = client is None
    client = client or httpx.Client(timeout=HERMES_TIMEOUT)
    try:
        resp = client.post(
            settings.hermes_url.rstrip("/") + "/chat",
            json=payload,
            headers={"Authorization": f"Bearer {settings.hermes_token}"},
        )
    except httpx.HTTPError as e:
        raise LLMError(f"Hermes injoignable : {e}") from e
    finally:
        if own_client:
            client.close()
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if resp.status_code != 200 or data.get("error"):
        detail = data.get("error") or resp.text[:200]
        raise LLMError(f"Hermes a répondu {resp.status_code} : {detail}")
    reply = (data.get("reply") or "").strip()
    if not reply:
        raise LLMError("Hermes a renvoyé une réponse vide.")
    return reply


def _gemini_chat(system_prompt: str, user_prompt: str) -> str:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY est absent ou vide.")
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(_GEMINI_MODEL, system_instruction=system_prompt)
    return model.generate_content(user_prompt).text
