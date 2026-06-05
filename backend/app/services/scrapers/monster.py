import asyncio
from typing import List
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class MonsterScraper(BaseScraper):
    source_name = "monster"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        location = ville or region or "France"
        offres = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page = await ctx.new_page()
                url = f"https://www.monster.fr/emploi/recherche/?q={quote_plus(query or "")}&where={quote_plus(location)}"
                await page.goto(url, timeout=30000)
                await asyncio.sleep(2)

                cards = await page.query_selector_all("[data-testid='jobTitle']")
                for card in cards[:20]:
                    try:
                        titre = await card.inner_text()
                        parent = await card.evaluate_handle("el => el.closest('[data-jobid]')")
                        link_el = await parent.query_selector("a")
                        href = await link_el.get_attribute("href") if link_el else ""

                        if titre:
                            offres.append(
                                OffreCreate(
                                    titre=titre.strip(),
                                    entreprise="Inconnu",
                                    lien_source=href or "",
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
