"""Envoi d'une candidature par e-mail (lettre PDF + CV en pièces jointes)."""
import os
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models.candidature import Candidature
from app.models.cv import CV
from app.models.lettre import Lettre
from app.models.offre import Offre
from app.services.email_service import send_email_with_attachments
from app.services.pdf_generator import generate_letter_pdf


class SmtpNonConfigure(Exception):
    pass


class EnvoiEchoue(Exception):
    pass


class DejaEnvoyee(Exception):
    pass


class CvIntrouvable(Exception):
    pass


async def envoyer_candidature_par_email(
    db: AsyncSession, candidature: Candidature, destinataire: str, sujet: str | None = None
) -> None:
    if not (settings.resend_api_key or settings.smtp_host):
        raise SmtpNonConfigure()
    offre = await db.get(Offre, candidature.offre_id)
    lettre = await db.get(Lettre, candidature.lettre_id) if candidature.lettre_id else None
    cv = (await db.execute(select(CV).where(CV.actif == True).limit(1))).scalars().first()  # noqa: E712
    titre = offre.titre if offre else "Poste"

    if not cv or not os.path.exists(cv.filepath):
        raise CvIntrouvable()

    attachments = []
    if lettre:
        attachments.append((f"lettre_{lettre.entreprise}.pdf", generate_letter_pdf(lettre.contenu, lettre.entreprise, titre)))
    with open(cv.filepath, "rb") as f:
        attachments.append((cv.filename, f.read()))

    body = f"Veuillez trouver ci-joint ma lettre de motivation et mon CV pour le poste de {titre}."

    # Réservation atomique : un seul appelant concurrent peut passer à "envoyee".
    precedent = candidature.statut
    res = await db.execute(
        update(Candidature)
        .where(Candidature.id == candidature.id, Candidature.statut != "envoyee")
        .values(statut="envoyee", envoyee_le=datetime.now(timezone.utc))
    )
    await db.commit()
    if res.rowcount == 0:
        raise DejaEnvoyee()
    await db.refresh(candidature)

    # Envoi bloquant (smtplib) hors de la boucle d'événements.
    if not await run_in_threadpool(
        send_email_with_attachments, destinataire, sujet or f"Candidature — {titre}", body, attachments
    ):
        await db.execute(
            update(Candidature).where(Candidature.id == candidature.id).values(statut=precedent, envoyee_le=None)
        )
        await db.commit()
        await db.refresh(candidature)
        raise EnvoiEchoue("Échec de l'envoi. Vérifiez la configuration SMTP/Resend.")
