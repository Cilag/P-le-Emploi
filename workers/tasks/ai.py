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


@app.task(name="workers.tasks.ai.generate_letter", bind=True)
def generate_letter(self, offre_id: int, force_regenerate: bool = False, candidature_id: int | None = None):
    from app.db.session import AsyncSessionLocal
    from app.services.lettres import generer_lettre_pour_offre

    async def _run():
        async with AsyncSessionLocal() as db:
            return await generer_lettre_pour_offre(db, offre_id, force_regenerate, candidature_id)

    return run_async(_run())
