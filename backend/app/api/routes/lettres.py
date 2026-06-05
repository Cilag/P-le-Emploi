from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.lettre import Lettre
from app.models.offre import Offre
from app.schemas.lettre import LettreRead, LettreUpdate, LettreGenerateRequest
from workers_client import generate_letter_task

router = APIRouter(prefix="/lettres", tags=["lettres"])


@router.get("", response_model=list[LettreRead])
async def list_lettres(
    entreprise: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Lettre).order_by(Lettre.modifie_le.desc())
    if entreprise:
        q = q.where(Lettre.entreprise.ilike(f"%{entreprise}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{lettre_id}", response_model=LettreRead)
async def get_lettre(lettre_id: int, db: AsyncSession = Depends(get_db)):
    lettre = await db.get(Lettre, lettre_id)
    if not lettre:
        raise HTTPException(status_code=404, detail="Lettre not found")
    return lettre


@router.post("/generate")
async def generate_lettre(req: LettreGenerateRequest, db: AsyncSession = Depends(get_db)):
    offre = await db.get(Offre, req.offre_id)
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")
    task = generate_letter_task.apply_async(
        kwargs={"offre_id": req.offre_id, "force_regenerate": req.force_regenerate},
        queue="ai",
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/generate/{task_id}")
async def get_generation_status(task_id: str):
    from app.workers_client import get_celery_app
    result = get_celery_app().AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@router.put("/{lettre_id}", response_model=LettreRead)
async def update_lettre(lettre_id: int, data: LettreUpdate, db: AsyncSession = Depends(get_db)):
    lettre = await db.get(Lettre, lettre_id)
    if not lettre:
        raise HTTPException(status_code=404, detail="Lettre not found")
    lettre.contenu = data.contenu
    await db.commit()
    await db.refresh(lettre)
    return lettre


@router.get("/{lettre_id}/pdf")
async def download_pdf(lettre_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response
    from app.services.pdf_generator import generate_letter_pdf
    lettre = await db.get(Lettre, lettre_id)
    if not lettre:
        raise HTTPException(status_code=404, detail="Lettre not found")
    offre = await db.get(Offre, lettre.offre_id) if lettre.offre_id else None
    pdf = generate_letter_pdf(
        lettre_contenu=lettre.contenu,
        entreprise=lettre.entreprise,
        titre_poste=offre.titre if offre else "Poste",
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="lettre_{lettre_id}.pdf"'},
    )


@router.get("/entreprise/{entreprise_name}", response_model=list[LettreRead])
async def get_lettres_by_entreprise(entreprise_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lettre)
        .where(Lettre.entreprise.ilike(f"%{entreprise_name}%"))
        .order_by(Lettre.version.desc())
    )
    return result.scalars().all()
