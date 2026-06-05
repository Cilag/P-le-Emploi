import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.cv import CV
from app.schemas.cv import CVRead, AuditConfig
from app.services.cv_parser import extract_cv_text
from app.core.config import settings

router = APIRouter(prefix="/cv", tags=["cv"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("", response_model=CVRead, status_code=201)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type. Use: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    texte = extract_cv_text(file.filename or "cv", content)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(settings.UPLOAD_DIR, file.filename or "cv")
    # Prevent path traversal
    filepath = os.path.realpath(filepath)
    if not filepath.startswith(os.path.realpath(settings.UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(filepath, "wb") as f:
        f.write(content)

    # Deactivate previous CVs
    await db.execute(
        select(CV).where(CV.actif == True).execution_options(synchronize_session="fetch")
    )
    existing = await db.execute(select(CV).where(CV.actif == True))
    for old_cv in existing.scalars().all():
        old_cv.actif = False

    cv = CV(filename=file.filename, filepath=filepath, texte_extrait=texte, actif=True)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv


@router.get("", response_model=CVRead)
async def get_active_cv(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CV).where(CV.actif == True).limit(1))
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="No active CV found")
    return cv


@router.post("/audit")
async def trigger_audit(config: AuditConfig):
    from workers_client import run_cv_audit_task
    task = run_cv_audit_task.apply_async(
        kwargs={"email_destination": config.email_destination},
        queue="ai",
    )
    return {"task_id": task.id, "status": "queued"}
