import feedparser
from typing import List
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class CadrEmploiScraper(BaseScraper):
    source_name = "cadremploi"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        offres = []

        try:
            url = f"https://www.cadremploi.fr/rss/emploi/offres?q={query}&l={ville or 'France'}"
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                offres.append(
                    OffreCreate(
                        titre=entry.get("title", ""),
                        entreprise=entry.get("author", "Inconnu"),
                        description=entry.get("summary", ""),
                        lien_source=entry.get("link", ""),
                        source=self.source_name,
                        ville=ville or "",
                    )
                )
        except Exception:
            pass

        return offres
