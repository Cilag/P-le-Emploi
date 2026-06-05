import asyncio
from typing import List
from playwright.async_api import async_playwright
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper


class LEtudiantScraper(BaseScraper):
    source_name = "letudiant"

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        query = mots_cles or secteur
        offres = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page = await ctx.new_page()
                url = f"https://jobs.letudiant.fr/alternances.html?q={query}"
                if ville:
                    url += f"&location={ville}"
                await page.goto(url, timeout=30000)
                await asyncio.sleep(2)

                cards = await page.query_selector_all(".offer-card")
                for card in cards[:20]:
                    try:
                        titre_el = await card.query_selector("h2.offer-title")
                        entreprise_el = await card.query_selector(".offer-company")
                        ville_el = await card.query_selector(".offer-location")
                        link_el = await card.query_selector("a")
                        titre = await titre_el.inner_text() if titre_el else ""
                        entreprise = await entreprise_el.inner_text() if entreprise_el else "Inconnu"
                        ville_str = await ville_el.inner_text() if ville_el else ""
                        href = await link_el.get_attribute("href") if link_el else ""
                        link = f"https://jobs.letudiant.fr{href}" if href and href.startswith("/") else href

                        if titre:
                            offres.append(
                                OffreCreate(
                                    titre=titre.strip(),
                                    entreprise=entreprise.strip(),
                                    lien_source=link or "",
                                    source=self.source_name,
                                    ville=ville_str.strip(),
                                    type_contrat="alternance",
                                )
                            )
                    except Exception:
                        continue

                await browser.close()
        except Exception:
            pass

        return offres
