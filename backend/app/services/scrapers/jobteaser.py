import httpx
from typing import List
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class JobTeaserScraper(BaseScraper):
    source_name = "jobteaser"
    SEARCH_URL = "https://www.jobteaser.com/en/job-offers"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        offres = []

        try:
            params = {"q": query, "location": ville or "France", "contract": type_contrat or ""}
            async with httpx.AsyncClient(timeout=20, headers={"Accept": "application/json"}) as client:
                resp = await client.get(f"{self.SEARCH_URL}.json", params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                for item in data.get("job_offers", [])[:20]:
                    offres.append(
                        OffreCreate(
                            titre=item.get("title", ""),
                            entreprise=item.get("company", {}).get("name", "Inconnu"),
                            description=item.get("description", ""),
                            lien_source=f"https://www.jobteaser.com{item.get('url', '')}",
                            source=self.source_name,
                            ville=item.get("location", {}).get("city", ""),
                            type_contrat=item.get("contract_type", ""),
                        )
                    )
        except Exception:
            pass

        return offres
