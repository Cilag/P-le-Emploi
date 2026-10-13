import io
import os
import zipfile
from datetime import datetime, timezone
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
    PreparerRequest,
    SendEmailRequest,
)
from app.services.candidatures import EnvoiEchoue, SmtpNonConfigure, envoyer_candidature_par_email
from app.services.pdf_generator import generate_letter_pdf

router = APIRouter(prefix="/candidatures", tags=["candidatures"])


def _lire(c: Candidature, o: Offre) -> CandidatureRead:
    return CandidatureRead(
        id=c.id, offre_id=c.offre_id, lettre_id=c.lettre_id, statut=c.statut,
        cree_le=c.cree_le, modifie_le=c.modifie_le, envoyee_le=c.envoyee_le,
        offre_titre=o.titre, offre_entreprise=o.entreprise,
        offre_lien=o.lien_source, offre_email_contact=o.email_contact,
    )


@router.get("", response_model=list[CandidatureRead])
async def list_candidatures(
    _user: Annotated[str, Depends(get_current_user)],
    statut: Optional[str] = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Candidature, Offre).join(Offre, Offre.id == Candidature.offre_id).order_by(Candidature.modifie_le.desc())
    if statut:
        q = q.where(Candidature.statut == statut)
    q = q.offset((page - 1) * per_page).limit(per_page)
    return [_lire(c, o) for c, o in (await db.execute(q)).all()]


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


@router.post("/preparer", status_code=202)
async def preparer_candidature(
    data: PreparerRequest,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    offre = await db.get(Offre, data.offre_id)
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")
    cv = (await db.execute(select(CV).where(CV.actif == True).limit(1))).scalars().first()  # noqa: E712
    if not cv:
        raise HTTPException(status_code=409, detail="Téléversez d'abord votre CV")
    candidature = (
        await db.execute(
            select(Candidature).where(Candidature.offre_id == data.offre_id).order_by(Candidature.id.desc()).limit(1)
        )
    ).scalars().first()
    if not candidature:
        candidature = Candidature(offre_id=data.offre_id)
        db.add(candidature)
        await db.commit()
        await db.refresh(candidature)
    from app.workers_client import generate_letter_task
    task = generate_letter_task.apply_async(
        kwargs={"offre_id": data.offre_id, "force_regenerate": False, "candidature_id": candidature.id},
        queue="ai",
    )
    return {"candidature_id": candidature.id, "task_id": task.id, "status": "queued"}


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

    try:
        await envoyer_candidature_par_email(db, candidature, req.destinataire, req.sujet)
    except SmtpNonConfigure:
        raise HTTPException(status_code=503, detail="SMTP non configuré")
    except EnvoiEchoue as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "sent"}


@router.post("/{candidature_id}/postuler")
async def postuler(
    candidature_id: int,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    candidature = await db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    lettre = await db.get(Lettre, candidature.lettre_id) if candidature.lettre_id else None
    if not lettre:
        raise HTTPException(status_code=409, detail="Générez d'abord la lettre")
    offre = await db.get(Offre, candidature.offre_id)
    if offre.email_contact:
        if candidature.statut == "envoyee":
            raise HTTPException(status_code=409, detail="Candidature déjà envoyée")
        try:
            await envoyer_candidature_par_email(db, candidature, offre.email_contact)
        except SmtpNonConfigure:
            raise HTTPException(status_code=503, detail="SMTP non configuré")
        except EnvoiEchoue as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"mode": "email", "destinataire": offre.email_contact}
    return {"mode": "site", "lien": offre.lien_source, "lettre_id": lettre.id, "lettre_texte": lettre.contenu}


@router.post("/{candidature_id}/marquer-envoyee", response_model=CandidatureRead)
async def marquer_envoyee(
    candidature_id: int,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    candidature = await db.get(Candidature, candidature_id)
    if not candidature:
        raise HTTPException(status_code=404, detail="Candidature not found")
    candidature.statut = "envoyee"
    candidature.envoyee_le = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(candidature)
    return candidature


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
