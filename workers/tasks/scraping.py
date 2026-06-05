import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from celery_app import app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="workers.tasks.scraping.run_scan", bind=True, max_retries=3)
def run_scan(self, scan_params: dict):
    from app.services.scrapers import ALL_SCRAPERS
    from app.db.session import AsyncSessionLocal
    from app.models.offre import Offre
    from sqlalchemy import select

    sources = scan_params.get("sources") or list(ALL_SCRAPERS.keys())
    results = {"imported": 0, "duplicates": 0, "errors": []}

    async def _run():
        for source_name in sources:
            scraper_cls = ALL_SCRAPERS.get(source_name)
            if not scraper_cls:
                continue
            try:
                scraper = scraper_cls()
                offres = await scraper.scrape(
                    secteur=scan_params.get("secteur", "informatique"),
                    region=scan_params.get("region"),
                    ville=scan_params.get("ville"),
                    type_contrat=scan_params.get("type_contrat"),
                    mots_cles=scan_params.get("mots_cles"),
                )
                async with AsyncSessionLocal() as db:
                    for offre_data in offres:
                        dedup_hash = Offre.compute_hash(
                            offre_data.titre, offre_data.entreprise, offre_data.ville or ""
                        )
                        existing = await db.execute(
                            select(Offre).where(Offre.dedup_hash == dedup_hash)
                        )
                        if existing.scalar_one_or_none():
                            results["duplicates"] += 1
                            continue
                        offre = Offre(**offre_data.model_dump(), dedup_hash=dedup_hash)
                        db.add(offre)
                    await db.commit()
                    results["imported"] += len(offres)
            except Exception as e:
                results["errors"].append(f"{source_name}: {str(e)}")

    run_async(_run())
    return results
