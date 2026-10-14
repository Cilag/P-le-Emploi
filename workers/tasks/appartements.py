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


def _redis():
    import redis

    return redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


@app.task(name="workers.tasks.appartements.lire_alertes", bind=True)
def lire_alertes(self):
    from app.db.session import AsyncSessionLocal
    from app.services.appartements import etat
    from app.services.appartements.imap import ImapError
    from app.services.appartements.imap import lire_alertes as lire
    from app.services.appartements.pipeline import traiter_alertes

    r = _redis()
    if not etat.prendre_verrou(r):
        return {"ignore": "lecture déjà en cours"}
    try:
        try:
            emails = lire()
        except ImapError as e:
            etat.ecrire_etat(r, "erreur", str(e))
            return {"erreur": str(e)}
        res = run_async(traiter_alertes(AsyncSessionLocal, emails))
        etat.ecrire_etat(r, "partiel" if res["erreurs"] else "ok", "; ".join(res["erreurs"])[:500] or None)
        return res
    finally:
        etat.liberer_verrou(r)


@app.task(name="workers.tasks.appartements.analyser_annonce")
def analyser_annonce(annonce_id: int):
    from app.db.session import AsyncSessionLocal
    from app.services.appartements.pipeline import analyser_annonce as analyser

    return run_async(analyser(AsyncSessionLocal, annonce_id))
