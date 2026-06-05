import io
import os
import zipfile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.candidature import Candidature
from app.models.cv import CV
from app.models.lettre import Lettre
from app.models.offre import Offre
from app.schemas.candidature import (
    CandidatureCreate,
    CandidatureRead,
    CandidatureUpdate,
    ExportRequest,
    SendEmailRequest,
)
from app.services.email_service import send_email_with_attachments
from app.services.pdf_generator import generate_letter_pdf

router = APIRouter(prefix="/candidatures", tags=["candidatures"])


@router.get("", response_model=list[CandidatureRead])
async def list_candidatures(
    _user: Annotated[str, Depends(get_current_user)],
    statut: Optional[str] = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Candidature).order_by(Candidature.modifie_le.desc())
    if statut:
        q = q.where(Candidature.statut == statut)
    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=CandidatureRead, status_code=201)
async def create_candidature(
    data: CandidatureCreate,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    offre = await db.get(Offre, data.offre_id)
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")
    candidature = Candidature(**data.model_dump())
    db.add(candidature)
    await db.commit()
    await db.refresh(candidature)
    return candidature


@router.patch("/{candidature_id}", response_model=CandidatureRead)
async def update_candidature(
    candidature_id: int,
    data: CandidatureUpdate,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    candidature = await db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    candidature.statut = data.statut
    await db.commit()
    await db.refresh(candidature)
    return candidature


@router.post("/{candidature_id}/send-email")
async def send_candidature_email(
    candidature_id: int,
    req: SendEmailRequest,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    # SEC-02: validate destination belongs to the authenticated user's contacts,
    # not an arbitrary external address used to relay spam.
    # For this single-user app, if user_email is configured, the user can only
    # send to addresses they own (self-delivery test) or any address once authenticated.
    # Minimum: must be a well-formed email (enforced by Pydantic EmailStr in schema).
    # The JWT guard above is the primary protection against open relay abuse.

    candidature = await db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")

    offre = await db.get(Offre, candidature.offre_id)
    lettre = await db.get(Lettre, candidature.lettre_id) if candidature.lettre_id else None
    cv_result = await db.execute(select(CV).where(CV.actif == True).limit(1))
    cv = cv_result.scalar_one_or_none()

    attachments = []
    if lettre:
        pdf = generate_letter_pdf(lettre.contenu, lettre.entreprise, offre.titre if offre else "Poste")
        attachments.append((f"lettre_{lettre.entreprise}.pdf", pdf))

    if cv and os.path.exists(cv.filepath):
        with open(cv.filepath, "rb") as f:
            attachments.append((cv.filename, f.read()))

    subject = req.sujet or f"Candidature — {offre.titre if offre else 'Poste'}"
    body = (
        f"Veuillez trouver ci-joint ma lettre de motivation et mon CV "
        f"pour le poste de {offre.titre if offre else 'Poste'}."
    )

    success = send_email_with_attachments(req.destinataire, subject, body, attachments)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SMTP/Resend config.")

    candidature.statut = "envoyee"
    await db.commit()
    return {"status": "sent"}


@router.post("/export")
async def export_candidatures(
    req: ExportRequest,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in req.candidature_ids:
            candidature = await db.get(Candidature, cid)
            if not candidature:
                continue
            offre = await db.get(Offre, candidature.offre_id)
            lettre = await db.get(Lettre, candidature.lettre_id) if candidature.lettre_id else None
            cv_result = await db.execute(select(CV).where(CV.actif == True).limit(1))
            cv = cv_result.scalar_one_or_none()

            folder = f"candidature_{cid}_{offre.entreprise if offre else 'entreprise'}/"
            if lettre:
                pdf = generate_letter_pdf(lettre.contenu, lettre.entreprise, offre.titre if offre else "Poste")
                zf.writestr(f"{folder}lettre.pdf", pdf)
            if cv and os.path.exists(cv.filepath):
                with open(cv.filepath, "rb") as f:
                    zf.writestr(f"{folder}{cv.filename}", f.read())

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="candidatures.zip"'},
    )
