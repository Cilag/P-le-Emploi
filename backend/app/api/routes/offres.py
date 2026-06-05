from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.db.session import get_db
from app.models.offre import Offre
from app.schemas.offre import OffreRead, OffreScanParams
from workers_client import run_scan_task

router = APIRouter(prefix="/offres", tags=["offres"])


@router.get("", response_model=list[OffreRead])
async def list_offres(
    source: Optional[str] = None,
    type_contrat: Optional[str] = None,
    ville: Optional[str] = None,
    statut: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Offre).order_by(Offre.date_import.desc())
    if source:
        q = q.where(Offre.source == source)
    if type_contrat:
        q = q.where(Offre.type_contrat == type_contrat)
    if ville:
        q = q.where(Offre.ville.ilike(f"%{ville}%"))
    if statut:
        q = q.where(Offre.statut == statut)
    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{offre_id}", response_model=OffreRead)
async def get_offre(offre_id: int, db: AsyncSession = Depends(get_db)):
    offre = await db.get(Offre, offre_id)
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")
    return offre


@router.post("/scan")
async def launch_scan(params: OffreScanParams):
    task = run_scan_task.apply_async(kwargs={"scan_params": params.model_dump()}, queue="scraping")
    return {"task_id": task.id, "status": "queued"}


@router.get("/scan/{task_id}")
async def get_scan_status(task_id: str):
    from app.workers_client import get_celery_app
    result = get_celery_app().AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@router.get("/sources/list")
async def list_sources():
    from app.services.scrapers import ALL_SCRAPERS
    return {"sources": list(ALL_SCRAPERS.keys())}
