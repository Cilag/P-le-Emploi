import asyncio
from typing import List
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class LinkedInScraper(BaseScraper):
    source_name = "linkedin"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        location = ville or region or "France"
        offres = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                )
                page = await ctx.new_page()
                url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query or "")}&location={quote_plus(location)}"
                await page.goto(url, timeout=30000)
                await asyncio.sleep(3)

                cards = await page.query_selector_all(".jobs-search__results-list li")
                for card in cards[:20]:
                    try:
                        titre_el = await card.query_selector("h3.base-search-card__title")
                        entreprise_el = await card.query_selector("h4.base-search-card__subtitle")
                        ville_el = await card.query_selector(".job-search-card__location")
                        link_el = await card.query_selector("a.base-card__full-link")
                        titre = await titre_el.inner_text() if titre_el else ""
                        entreprise = await entreprise_el.inner_text() if entreprise_el else "Inconnu"
                        ville_str = await ville_el.inner_text() if ville_el else ""
                        link = await link_el.get_attribute("href") if link_el else ""

                        if titre:
                            offres.append(
                                OffreCreate(
                                    titre=titre.strip(),
                                    entreprise=entreprise.strip(),
                                    lien_source=link or "",
                                    source=self.source_name,
                                    ville=ville_str.strip(),
                                )
                            )
                    except Exception:
                        continue

                await browser.close()
        except Exception:
            pass

        return offres
