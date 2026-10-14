"""Adzuna : agrégateur d'offres, API officielle (clé gratuite sur developer.adzuna.com)."""
import logging
from typing import List

from app.config import settings
from app.schemas.offre import OffreCreate
from app.services.scrapers.api_commun import appel_json, date_iso, texte_brut
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
DISTANCE_KM = 30
CONTRATS = {"permanent": "CDI", "contract": "CDD"}


class AdzunaScraper(BaseScraper):
    source_name = "adzuna"

    def __init__(self, transport=None):
        self._transport = transport

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            return []
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": mots_cles or secteur,
            "results_per_page": "50",
            "max_days_old": "2",
            "content-type": "application/json",
        }
        if ville:
            params.update({"where": ville, "distance": str(DISTANCE_KM)})
        data = await appel_json(self.source_name, "GET", SEARCH_URL, self._transport, params=params)
        if data is None:
            return []
        offres = []
        for item in data.get("results", []):
            titre = texte_brut(item.get("title"))
            if not titre:
                continue
            offres.append(
                OffreCreate(
                    titre=titre,
                    entreprise=(item.get("company") or {}).get("display_name") or "Inconnu",
                    description=texte_brut(item.get("description")) or None,
                    lien_source=item.get("redirect_url", ""),
                    source=self.source_name,
                    ville=(item.get("location") or {}).get("display_name") or None,
                    type_contrat=CONTRATS.get(item.get("contract_type") or ""),
                    date_publication=date_iso(item.get("created")),
                )
            )
        logger.info("adzuna : %d offres pour %r", len(offres), params["what"])
        return offres
