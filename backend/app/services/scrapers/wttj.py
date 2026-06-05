import httpx
from typing import List
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class WTTJScraper(BaseScraper):
    source_name = "welcome_to_the_jungle"
    API_URL = "https://api.welcometothejungle.com/api/v1/jobs"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        offres = []
        query = mots_cles or secteur
        params = {"query": query, "page": 1, "per_page": 30, "country_code": "FR"}
        if ville:
            params["city"] = ville

        try:
            async with httpx.AsyncClient(timeout=20, headers={"Accept": "application/json"}) as client:
                resp = await client.get(self.API_URL, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                for item in data.get("jobs", []):
                    org = item.get("organization", {})
                    offres.append(
                        OffreCreate(
                            titre=item.get("name", ""),
                            entreprise=org.get("name", "Inconnu"),
                            description=item.get("description", ""),
                            lien_source=f"https://www.welcometothejungle.com{item.get('uri', '')}",
                            source=self.source_name,
                            ville=(item.get("office", {}) or {}).get("city", ""),
                            type_contrat=item.get("contract_type", {}).get("name", ""),
                        )
                    )
        except Exception:
            pass

        return offres
