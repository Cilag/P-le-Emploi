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
def generate_letter(self, offre_id: int, force_regenerate: bool = False):
    from app.db.session import AsyncSessionLocal
    from app.models.offre import Offre
    from app.models.lettre import Lettre
    from app.models.cv import CV
    from app.services.ai.letter_generator import generate_cover_letter
    from sqlalchemy import select

    async def _run():
        async with AsyncSessionLocal() as db:
            offre = await db.get(Offre, offre_id)
            if not offre:
                return {"error": "Offre not found"}

            cv_result = await db.execute(select(CV).where(CV.actif == True).limit(1))
            cv = cv_result.scalar_one_or_none()
            cv_text = cv.texte_extrait if cv else "CV non disponible."

            if not force_regenerate:
                existing = await db.execute(
                    select(Lettre)
                    .where(Lettre.entreprise == offre.entreprise)
                    .order_by(Lettre.version.desc())
                )
                existing_lettre = existing.scalar_one_or_none()
                if existing_lettre:
                    return {"lettre_id": existing_lettre.id, "reused": True}

            contenu = generate_cover_letter(
                cv_text=cv_text,
                offre_titre=offre.titre,
                offre_entreprise=offre.entreprise,
                offre_description=offre.description or "",
                type_contrat=offre.type_contrat,
            )

            latest = await db.execute(
                select(Lettre.version)
                .where(Lettre.entreprise == offre.entreprise)
                .order_by(Lettre.version.desc())
            )
            last_version = latest.scalar() or 0

            lettre = Lettre(
                offre_id=offre_id,
                entreprise=offre.entreprise,
                contenu=contenu,
                version=last_version + 1,
            )
            db.add(lettre)
            await db.commit()
            await db.refresh(lettre)
            return {"lettre_id": lettre.id, "reused": False}

    return run_async(_run())
