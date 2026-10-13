"""Génération d'une lettre pour une offre (appelée par la tâche Celery generate_letter)."""
from sqlalchemy import func, select
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

    # Réutilisation limitée aux lettres écrites pour CETTE offre : une lettre d'une autre offre
    # de la même entreprise (ex. offres FT anonymes « Inconnu ») ne doit jamais être envoyée.
    existante = None
    if not force_regenerate:
        existante = (
            await db.execute(
                select(Lettre)
                .where(Lettre.offre_id == offre_id)
                .order_by(Lettre.version.desc(), Lettre.id.desc())
                .limit(1)
            )
        ).scalars().first()

    if existante:
        lettre, reused = existante, True
    else:
        # Numérotation des versions par entreprise (cohérente avec les données existantes).
        version_max = (
            await db.execute(select(func.max(Lettre.version)).where(Lettre.entreprise == offre.entreprise))
        ).scalar()
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
            version=(version_max or 0) + 1,
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
