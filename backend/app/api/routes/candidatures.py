import io
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db.session import get_db
from app.models.candidature import Candidature
from app.models.offre import Offre
from app.models.lettre import Lettre
from app.models.cv import CV
from app.schemas.candidature import CandidatureCreate, CandidatureRead, CandidatureUpdate, SendEmailRequest, ExportRequest
from app.services.pdf_generator import generate_letter_pdf
from app.services.email_service import send_email_with_attachments
import os

router = APIRouter(prefix="/candidatures", tags=["candidatures"])

VALID_STATUTS = {"en_attente", "envoyee", "refusee", "entretien", "acceptee"}


@router.get("", response_model=list[CandidatureRead])
async def list_candidatures(
    statut: Optional[str] = None,
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
async def create_candidature(data: CandidatureCreate, db: AsyncSession = Depends(get_db)):
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
    db: AsyncSession = Depends(get_db),
):
    if data.statut not in VALID_STATUTS:
        raise HTTPException(status_code=422, detail=f"Invalid statut. Must be one of: {VALID_STATUTS}")
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
    db: AsyncSession = Depends(get_db),
):
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
    body = f"Veuillez trouver ci-joint ma lettre de motivation et mon CV pour le poste de {offre.titre if offre else 'Poste'}."

    success = send_email_with_attachments(req.destinataire, subject, body, attachments)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SMTP/Resend config.")

    candidature.statut = "envoyee"
    await db.commit()
    return {"status": "sent"}


@router.post("/export")
async def export_candidatures(req: ExportRequest, db: AsyncSession = Depends(get_db)):
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
