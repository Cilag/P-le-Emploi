"""Scan des sources d'offres et import dédoublonné (appelé par les tâches Celery)."""
import logging
from collections.abc import Mapping

from sqlalchemy import select

from app.models.offre import Offre
from app.schemas.offre import OffreCreate

logger = logging.getLogger(__name__)

DEFAULT_MOTS_CLES = "DevOps;administrateur système;SRE;ingénieur cloud"
DEFAULT_VILLE = "Bordeaux"
DEFAULT_SOURCES = "france_travail,linkedin,adzuna,jooble,welcome_to_the_jungle,apec"
# Remotive n'est pas inclus : son API ne renvoie que ses 15 dernières offres, sans filtre (2026-10).
SOURCES_TELETRAVAIL = ["linkedin"]


async def import_offres(db, offres: list[OffreCreate]) -> tuple[int, int]:
    """Ajoute les offres absentes (en base comme dans le lot). Renvoie (importées, doublons)."""
    vus: set[str] = set()
    importees = doublons = 0
    for o in offres:
        h = Offre.compute_hash(o.titre, o.entreprise, o.ville or "")
        if h in vus or (await db.execute(select(Offre.id).where(Offre.dedup_hash == h))).first():
            doublons += 1
            continue
        vus.add(h)
        db.add(Offre(**o.model_dump(), dedup_hash=h))
        importees += 1
    await db.commit()
    return importees, doublons


def _liste(valeur: str, sep: str) -> list[str]:
    return [v.strip() for v in valeur.split(sep) if v.strip()]


def daily_scan_params(env: Mapping[str, str]) -> list[dict]:
    """Passes du scan quotidien : une par mot-clé sur la ville, puis une par mot-clé en télétravail (LinkedIn)."""
    mots = _liste(env.get("SCAN_MOTS_CLES", DEFAULT_MOTS_CLES), ";")
    sources = _liste(env.get("SCAN_SOURCES", DEFAULT_SOURCES), ",")
    ville = env.get("SCAN_VILLE", DEFAULT_VILLE).strip()
    passes = [{"secteur": "informatique", "mots_cles": m, "ville": ville, "sources": sources} for m in mots]
    passes += [
        {"secteur": "informatique", "mots_cles": m, "ville": None, "sources": list(SOURCES_TELETRAVAIL), "remote": True}
        for m in mots
    ]
    return passes


async def executer_passe(scan_params: dict, scrapers: Mapping, session_factory) -> dict:
    """Interroge chaque source ; l'échec d'une source n'arrête pas les autres."""
    res = {"imported": 0, "duplicates": 0, "errors": [], "par_source": {}}
    for name in scan_params.get("sources") or list(scrapers.keys()):
        kwargs = {
            "secteur": scan_params.get("secteur", "informatique"),
            "region": scan_params.get("region"),
            "ville": scan_params.get("ville"),
            "type_contrat": scan_params.get("type_contrat"),
            "mots_cles": scan_params.get("mots_cles"),
        }
        if scan_params.get("remote"):
            kwargs["remote"] = True
        try:
            cls = scrapers.get(name)
            if cls is None:
                res["errors"].append(f"{name}: source inconnue")
                continue
            offres = await cls().scrape(**kwargs)
            async with session_factory() as db:
                importees, doublons = await import_offres(db, offres)
        except Exception as e:
            logger.warning("scan %s : %s", name, e, exc_info=True)
            res["errors"].append(f"{name}: {e}")
            continue
        res["imported"] += importees
        res["duplicates"] += doublons
        res["par_source"][name] = importees
    return res
