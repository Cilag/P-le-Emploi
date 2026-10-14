"""LinkedIn : offres publiques via l'endpoint invité (sans compte, sans navigateur).

Lecture seule de pages publiques ; aucune connexion au compte LinkedIn de l'utilisateur.
"""
import logging
import re
from typing import List
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

GUEST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JOB_POSTING_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_JOB_ID_RE = re.compile(r"-(\d{6,})/?$")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def build_params(mots_cles: str, ville: str | None, remote: bool) -> dict:
    params = {
        "keywords": mots_cles,
        "location": "France" if remote else (ville or "France"),
        "f_TPR": "r86400",  # publiées dans les dernières 24 h
        "start": "0",
    }
    if remote:
        params["f_WT"] = "2"  # télétravail
    return params


def _texte(card, selector: str) -> str | None:
    el = card.select_one(selector)
    t = el.get_text(strip=True) if el else ""
    return t or None


def parse_linkedin_cards(html: str) -> list[OffreCreate]:
    offres = []
    for card in BeautifulSoup(html, "html.parser").select("li"):
        titre = _texte(card, ".base-search-card__title")
        if not titre:
            continue
        lien = card.select_one("a.base-card__full-link")
        offres.append(
            OffreCreate(
                titre=titre,
                entreprise=_texte(card, ".base-search-card__subtitle") or "Inconnu",
                lien_source=(lien.get("href") or "").split("?")[0] if lien else "",
                source=LinkedInScraper.source_name,
                ville=_texte(card, ".job-search-card__location"),
            )
        )
    return offres


class LinkedInScraper(BaseScraper):
    source_name = "linkedin"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles, remote: bool = False) -> List[OffreCreate]:
        params = build_params(mots_cles or secteur, ville, remote)
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, transport=self._transport) as client:
            resp = await client.get(GUEST_URL, params=params)
        if resp.status_code != 200:
            logger.warning("linkedin : HTTP %s pour %s — 0 offre", resp.status_code, params)
            return []
        offres = parse_linkedin_cards(resp.text)
        logger.info("linkedin : %d offres pour %s", len(offres), params)
        return offres


def job_id(lien: str) -> str | None:
    """Identifiant numérique de l'offre, en fin de chemin (…/jobs/view/<slug>-<id>), paramètres ignorés."""
    m = _JOB_ID_RE.search(urlsplit(lien or "").path)
    return m.group(1) if m else None


def parse_description(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    bloc = soup.select_one(".show-more-less-html__markup") or soup.select_one(".description__text")
    if not bloc:
        return None
    lignes = (ligne.strip() for ligne in bloc.get_text("\n").splitlines())
    texte = re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()
    return texte or None


async def fetch_description(lien: str, transport: httpx.AsyncBaseTransport | None = None) -> str | None:
    """Description complète d'une offre via la page publique ; None si indisponible (lien, 429, réseau)."""
    jid = job_id(lien)
    if not jid:
        return None
    url = JOB_POSTING_URL.format(job_id=jid)
    try:
        async with httpx.AsyncClient(timeout=30, headers=HEADERS, transport=transport) as client:
            resp = await client.get(url)
    except httpx.HTTPError as e:
        logger.warning("linkedin : description %s injoignable — %s", jid, e)
        return None
    if resp.status_code != 200:
        logger.warning("linkedin : HTTP %s pour la description %s", resp.status_code, jid)
        return None
    return parse_description(resp.text)
