import httpx
from urllib.parse import quote
from typing import List
from bs4 import BeautifulSoup
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class RegionsJobScraper(BaseScraper):
    source_name = "regionsjob"
    BASE_URL = "https://www.regionsjob.com"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        offres = []

        try:
            url = f"{self.BASE_URL}/emploi/{quote((query or '').replace(' ', '-'), safe='-')}.html"
            async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                soup = BeautifulSoup(resp.text, "lxml")
                for card in soup.select(".offer-item")[:20]:
                    titre_el = card.select_one("h2.offer-title a")
                    entreprise_el = card.select_one(".offer-company")
                    ville_el = card.select_one(".offer-location")
                    if titre_el:
                        offres.append(
                            OffreCreate(
                                titre=titre_el.get_text(strip=True),
                                entreprise=entreprise_el.get_text(strip=True) if entreprise_el else "Inconnu",
                                lien_source=f"{self.BASE_URL}{titre_el.get('href', '')}",
                                source=self.source_name,
                                ville=ville_el.get_text(strip=True) if ville_el else "",
                            )
                        )
        except Exception:
            pass

        return offres
