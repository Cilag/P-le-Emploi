"""Jooble : agrégateur d'offres, API REST (clé gratuite sur demande via jooble.org/api/about)."""
import logging
from typing import List

from app.config import settings
from app.schemas.offre import OffreCreate
from app.services.scrapers.api_commun import appel_json, date_iso, texte_brut, tronque
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://fr.jooble.org/api/{cle}"
RAYON_KM = "40"


class JoobleScraper(BaseScraper):
    source_name = "jooble"

    def __init__(self, transport=None):
        self._transport = transport

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        if not settings.jooble_api_key:
            return []
        corps = {"keywords": mots_cles or secteur, "location": ville or "", "radius": RAYON_KM, "page": "1"}
        url = API_URL.format(cle=settings.jooble_api_key)
        data = await appel_json(self.source_name, "POST", url, self._transport, json=corps)
        if data is None:
            return []
        offres = []
        for item in data.get("jobs", []):
            titre = texte_brut(item.get("title"))
            if not titre:
                continue
            offres.append(
                OffreCreate(
                    titre=titre,
                    entreprise=tronque(texte_brut(item.get("company")), 255) or "Inconnu",
                    description=texte_brut(item.get("snippet")) or None,
                    lien_source=item.get("link", ""),
                    source=self.source_name,
                    ville=tronque(texte_brut(item.get("location")), 255) or None,
                    type_contrat=tronque(texte_brut(item.get("type")), 50) or None,
                    date_publication=date_iso(item.get("updated")),
                )
            )
        logger.info("jooble : %d offres pour %r", len(offres), corps["keywords"])
        return offres
