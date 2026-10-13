import asyncio
import os
import sys

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
    from app.db.session import AsyncSessionLocal
    from app.services.scan import executer_passe
    from app.services.scrapers import ALL_SCRAPERS

    return run_async(executer_passe(scan_params, ALL_SCRAPERS, AsyncSessionLocal))


@app.task(name="workers.tasks.scraping.run_daily_scan", bind=True)
def run_daily_scan(self):
    from app.db.session import AsyncSessionLocal
    from app.services.scan import daily_scan_params, executer_passe
    from app.services.scrapers import ALL_SCRAPERS

    total = {"imported": 0, "duplicates": 0, "errors": []}
    for params in daily_scan_params(os.environ):
        r = run_async(executer_passe(params, ALL_SCRAPERS, AsyncSessionLocal))
        total["imported"] += r["imported"]
        total["duplicates"] += r["duplicates"]
        total["errors"] += [f"[{params['mots_cles']}] {e}" for e in r["errors"]]
    return total
