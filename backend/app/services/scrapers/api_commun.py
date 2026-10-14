"""Outils partagés par les sources interrogées via une API JSON (Adzuna, Jooble, Remotive)."""
import html
import logging
import re
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

_BLOC = re.compile(r"</?(?:p|br|div|li|ul|ol|h[1-6]|tr|td|section)[^>]*>", re.I)
_BALISE = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")


def texte_brut(fragment: str | None) -> str:
    """Retire balises HTML et entités (&amp;, &nbsp;…) et normalise les espaces (texte sur une ligne)."""
    if not fragment:
        return ""
    # Balises de bloc → espace ; balises en ligne (<b>, <strong>…) retirées sans espace.
    texte = _BALISE.sub("", _BLOC.sub(" ", html.unescape(fragment)))
    return _ESPACES.sub(" ", texte).strip()


def date_iso(valeur: str | None) -> datetime | None:
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        return None


def tronque(valeur: str | None, longueur: int) -> str | None:
    return valeur[:longueur] if valeur else valeur


async def appel_json(source: str, methode: str, url: str, transport=None, **kwargs) -> dict | None:
    """Requête HTTP renvoyant le JSON, ou None (journalisé) en cas d'erreur réseau ou de statut ≠ 200."""
    try:
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.request(methode, url, **kwargs)
    except httpx.HTTPError as e:
        logger.warning("%s : injoignable — %s", source, e)
        return None
    if resp.status_code != 200:
        logger.warning("%s : HTTP %s — %s", source, resp.status_code, resp.text[:200])
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("%s : réponse non JSON", source)
        return None
