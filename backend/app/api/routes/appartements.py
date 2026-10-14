import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.appartement import AlerteEmail, Annonce, DossierLocataire
from app.schemas.appartement import AnnonceRead, AnnonceUpdate, DossierRead, DossierUpdate
from app.services.appartements.etat import lire_etat

router = APIRouter(prefix="/appartements", tags=["appartements"])
_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


@router.get("", response_model=list[AnnonceRead])
async def lister(
    _user: Annotated[str, Depends(get_current_user)],
    statut: Optional[str] = Query(None, max_length=20),
    ville: Optional[str] = Query(None, max_length=100),
    note_min: Optional[int] = Query(None, ge=0, le=10),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Annonce).order_by(
        Annonce.vue.asc(), Annonce.note.desc().nulls_last(), Annonce.recue_le.desc(), Annonce.id.desc()
    )
    if statut:
        q = q.where(Annonce.statut == statut)
    if ville:
        q = q.where(Annonce.ville.ilike(f"%{ville}%"))
    if note_min is not None:
        q = q.where(Annonce.note >= note_min)
    q = q.offset((page - 1) * per_page).limit(per_page)
    return (await db.execute(q)).scalars().all()


@router.get("/dossier", response_model=DossierRead)
async def lire_dossier(_user: Annotated[str, Depends(get_current_user)], db: AsyncSession = Depends(get_db)):
    d = (await db.execute(select(DossierLocataire).limit(1))).scalars().first()
    return DossierRead(texte=d.texte if d else "", modifie_le=d.modifie_le if d else None)


@router.put("/dossier", response_model=DossierRead)
async def ecrire_dossier(
    data: DossierUpdate,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    d = (await db.execute(select(DossierLocataire).limit(1))).scalars().first()
    if not d:
        d = DossierLocataire(texte=data.texte)
        db.add(d)
    else:
        d.texte = data.texte
    await db.commit()
    await db.refresh(d)
    return DossierRead(texte=d.texte, modifie_le=d.modifie_le)


@router.get("/etat")
async def etat_lecture(_user: Annotated[str, Depends(get_current_user)], db: AsyncSession = Depends(get_db)):
    depuis = datetime.now(timezone.utc) - timedelta(hours=24)
    nb_alertes = (await db.execute(
        select(func.count()).select_from(AlerteEmail).where(AlerteEmail.traite_le >= depuis)
    )).scalar()
    nb_annonces = (await db.execute(
        select(func.count()).select_from(Annonce).where(Annonce.recue_le >= depuis)
    )).scalar()
    e = lire_etat(_redis)
    return {
        "derniere_lecture": e.get("derniere_lecture"),
        "dernier_statut": e.get("statut"),
        "derniere_erreur": e.get("erreur"),
        "nb_alertes_24h": nb_alertes,
        "nb_annonces_24h": nb_annonces,
    }


@router.post("/lire-maintenant", status_code=202)
async def lire_maintenant(_user: Annotated[str, Depends(get_current_user)]):
    from app.workers_client import lire_alertes_task
    task = lire_alertes_task.apply_async(kwargs={}, queue="default")
    return {"task_id": task.id, "status": "queued"}


@router.get("/{annonce_id}", response_model=AnnonceRead)
async def detail(annonce_id: int, _user: Annotated[str, Depends(get_current_user)], db: AsyncSession = Depends(get_db)):
    a = await db.get(Annonce, annonce_id)
    if not a:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    a.vue = True
    await db.commit()
    await db.refresh(a)
    return a


@router.patch("/{annonce_id}", response_model=AnnonceRead)
async def modifier(
    annonce_id: int,
    data: AnnonceUpdate,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    a = await db.get(Annonce, annonce_id)
    if not a:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    a.statut = data.statut
    await db.commit()
    await db.refresh(a)
    return a


@router.post("/{annonce_id}/analyser", status_code=202)
async def relancer_analyse(
    annonce_id: int,
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Annonce, annonce_id):
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    from app.workers_client import analyser_annonce_task
    task = analyser_annonce_task.apply_async(kwargs={"annonce_id": annonce_id}, queue="default")
    return {"task_id": task.id, "status": "queued"}
