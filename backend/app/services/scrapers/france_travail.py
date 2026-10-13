import logging
import re

import httpx
from typing import List
from datetime import datetime
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper
from app.config import settings

logger = logging.getLogger(__name__)

COMMUNES_INSEE = {"bordeaux": "33063"}
DISTANCE_KM = 30
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def lieu_params(ville: str | None) -> dict:
    """L'API attend un code INSEE dans `commune`, pas un nom de ville."""
    if not ville:
        return {}
    code = COMMUNES_INSEE.get(ville.strip().lower())
    if code:
        return {"commune": code, "distance": DISTANCE_KM}
    logger.warning("france_travail : ville %r sans code INSEE connu, recherche sans filtre de lieu", ville)
    return {}


def email_contact(item: dict) -> str | None:
    courriel = ((item.get("contact") or {}).get("courriel") or "").strip()
    return courriel if _EMAIL_RE.match(courriel) else None


def to_offre(item: dict) -> OffreCreate:
    return OffreCreate(
        titre=item.get("intitule", ""),
        entreprise=(item.get("entreprise") or {}).get("nom", "Inconnu"),
        description=item.get("description", ""),
        lien_source=(item.get("origineOffre") or {}).get("urlOrigine", ""),
        source=FranceTravailScraper.source_name,
        ville=(item.get("lieuTravail") or {}).get("libelle", ""),
        type_contrat=item.get("typeContrat", ""),
        date_publication=datetime.fromisoformat(item["dateCreation"].replace("Z", "+00:00"))
        if item.get("dateCreation") else None,
        email_contact=email_contact(item),
    )


class FranceTravailScraper(BaseScraper):
    source_name = "france_travail"
    TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            self.TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.francetravail_client_id,
                "client_secret": settings.francetravail_client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        if not settings.francetravail_client_id:
            return []

        offres = []
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_token(client)
            params: dict = {"motsCles": mots_cles or secteur, "range": "0-49"}
            params.update(lieu_params(ville))
            if type_contrat:
                contract_map = {"CDI": "CDI", "CDD": "CDD", "alternance": "CFA"}
                params["typeContrat"] = contract_map.get(type_contrat, type_contrat)

            resp = await client.get(
                self.SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            # L'API France Travail répond 206 Partial Content sur les résultats paginés (cas normal).
            if resp.status_code not in (200, 206):
                logger.warning("france_travail : HTTP %s — %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            offres = [to_offre(item) for item in data.get("resultats", [])]
        return offres
