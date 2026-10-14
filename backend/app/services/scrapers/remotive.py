"""Remotive : offres tech 100 % télétravail, API publique sans clé (remotive.com/api/remote-jobs).

Utilisée seulement pendant la passe « télétravail » du scan ; Remotive demande de ne pas
l'interroger à haute fréquence (le scan quotidien fait une requête par mot-clé).
"""
import logging
from typing import List

from app.schemas.offre import OffreCreate
from app.services.scrapers.api_commun import appel_json, date_iso, texte_brut, tronque
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
# Offres ouvertes à un candidat basé en France
ZONES_OK = ("worldwide", "anywhere", "europe", "emea", "france")
CONTRATS = {"full_time": "CDI", "contract": "Freelance", "part_time": "Temps partiel", "internship": "Stage"}


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def __init__(self, transport=None):
        self._transport = transport

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles, remote: bool = False) -> List[OffreCreate]:
        if not remote:
            return []
        recherche = mots_cles or secteur
        data = await appel_json(self.source_name, "GET", API_URL, self._transport,
                                params={"search": recherche, "limit": "50"})
        if data is None:
            return []
        offres = []
        for item in data.get("jobs", []):
            zone = item.get("candidate_required_location") or ""
            titre = texte_brut(item.get("title"))
            if not titre or not any(z in zone.lower() for z in ZONES_OK):
                continue
            offres.append(
                OffreCreate(
                    titre=titre,
                    entreprise=tronque(item.get("company_name"), 255) or "Inconnu",
                    description=texte_brut(item.get("description")) or None,
                    lien_source=item.get("url", ""),
                    source=self.source_name,
                    ville=tronque(f"Télétravail ({zone})", 255),
                    type_contrat=CONTRATS.get(item.get("job_type") or ""),
                    date_publication=date_iso(item.get("publication_date")),
                )
            )
        logger.info("remotive : %d offres pour %r", len(offres), recherche)
        return offres
