"""LinkedIn : offres publiques via l'endpoint invité (sans compte, sans navigateur).

Lecture seule de pages publiques ; aucune connexion au compte LinkedIn de l'utilisateur.
"""
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

GUEST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
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
