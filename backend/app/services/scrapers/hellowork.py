import asyncio
from typing import List
from playwright.async_api import async_playwright
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class HelloWorkScraper(BaseScraper):
    source_name = "hellowork"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        location = ville or region or "France"
        offres = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page = await ctx.new_page()
                url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={query}&l={location}"
                await page.goto(url, timeout=30000)
                await asyncio.sleep(2)

                cards = await page.query_selector_all("article[data-id-offre]")
                for card in cards[:20]:
                    try:
                        titre_el = await card.query_selector("h2")
                        entreprise_el = await card.query_selector("[data-cy='company-name']")
                        link_el = await card.query_selector("a")
                        titre = await titre_el.inner_text() if titre_el else ""
                        entreprise = await entreprise_el.inner_text() if entreprise_el else "Inconnu"
                        href = await link_el.get_attribute("href") if link_el else ""
                        link = f"https://www.hellowork.com{href}" if href and href.startswith("/") else href

                        if titre:
                            offres.append(
                                OffreCreate(
                                    titre=titre.strip(),
                                    entreprise=entreprise.strip(),
                                    lien_source=link or "",
                                    source=self.source_name,
                                    ville=location,
                                )
                            )
                    except Exception:
                        continue

                await browser.close()
        except Exception:
            pass

        return offres
