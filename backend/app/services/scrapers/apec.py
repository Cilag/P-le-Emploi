import httpx
from typing import List
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class ApecScraper(BaseScraper):
    source_name = "apec"
    SEARCH_URL = "https://api.apec.fr/offres/v1/recherche"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        offres = []
        query = mots_cles or secteur
        params = {
            "motsCles": query,
            "nbResultatsParPage": 30,
            "numeroPage": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(self.SEARCH_URL, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                for item in data.get("resultats", []):
                    offres.append(
                        OffreCreate(
                            titre=item.get("intitule", ""),
                            entreprise=item.get("nomEntreprise", "Inconnu"),
                            description=item.get("texteHtml", ""),
                            lien_source=f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{item.get('numOffre', '')}",
                            source=self.source_name,
                            ville=item.get("lieuDeTravail", ""),
                            type_contrat=item.get("typeContrat", ""),
                        )
                    )
        except Exception:
            pass

        return offres
