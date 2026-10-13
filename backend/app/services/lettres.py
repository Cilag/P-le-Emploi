"""Génération d'une lettre pour une offre (appelée par la tâche Celery generate_letter)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidature import Candidature
from app.models.cv import CV
from app.models.lettre import Lettre
from app.models.offre import Offre
from app.services.ai.letter_generator import generate_cover_letter


async def generer_lettre_pour_offre(
    db: AsyncSession,
    offre_id: int,
    force_regenerate: bool = False,
    candidature_id: int | None = None,
    generate=generate_cover_letter,
) -> dict:
    offre = await db.get(Offre, offre_id)
    if not offre:
        return {"error": "Offre not found"}

    derniere = (
        await db.execute(
            select(Lettre)
            .where(Lettre.entreprise == offre.entreprise)
            .order_by(Lettre.version.desc())
            .limit(1)
        )
    ).scalars().first()

    if derniere and not force_regenerate:
        lettre, reused = derniere, True
    else:
        cv = (await db.execute(select(CV).where(CV.actif == True).limit(1))).scalars().first()  # noqa: E712
        contenu = generate(
            cv_text=cv.texte_extrait if cv and cv.texte_extrait else "CV non disponible.",
            offre_titre=offre.titre,
            offre_entreprise=offre.entreprise,
            offre_description=offre.description or "",
            type_contrat=offre.type_contrat,
        )
        lettre = Lettre(
            offre_id=offre_id,
            entreprise=offre.entreprise,
            contenu=contenu,
            version=(derniere.version if derniere else 0) + 1,
        )
        db.add(lettre)
        await db.flush()
        reused = False

    if candidature_id is not None:
        candidature = await db.get(Candidature, candidature_id)
        if candidature:
            candidature.lettre_id = lettre.id
    await db.commit()
    return {"lettre_id": lettre.id, "reused": reused}
