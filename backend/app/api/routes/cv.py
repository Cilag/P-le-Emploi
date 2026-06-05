import os
from typing import Annotated

import magic
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.cv import CV
from app.schemas.cv import AuditConfig, CVRead
from app.services.cv_parser import extract_cv_text

router = APIRouter(prefix="/cv", tags=["cv"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("", response_model=CVRead, status_code=201)
async def upload_cv(
    _user: Annotated[str, Depends(get_current_user)],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type. Use: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # SEC-03: verify actual MIME type, not just extension
    detected_mime = magic.from_buffer(content[:4096], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"File content does not match an allowed type. Detected: {detected_mime}",
        )

    texte = extract_cv_text(file.filename or "cv", content)

    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, file.filename or "cv")
    # Prevent path traversal
    filepath = os.path.realpath(filepath)
    if not filepath.startswith(os.path.realpath(settings.upload_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(filepath, "wb") as f:
        f.write(content)

    await db.execute(update(CV).where(CV.actif == True).values(actif=False))

    cv = CV(filename=file.filename, filepath=filepath, texte_extrait=texte, actif=True)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv


@router.get("", response_model=CVRead)
async def get_active_cv(
    _user: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CV).where(CV.actif == True).limit(1))
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="No active CV found")
    return cv


@router.post("/audit", status_code=202)
@limiter.limit("5/minute")
async def trigger_audit(
    request: Request,
    config: AuditConfig,
    _user: Annotated[str, Depends(get_current_user)],
):
    # SEC-02: audit report must be sent to the configured user email only
    if settings.user_email and config.email_destination != settings.user_email:
        raise HTTPException(
            status_code=403,
            detail="Audit report can only be sent to the authenticated user's email address.",
        )
    from app.workers_client import run_cv_audit_task
    task = run_cv_audit_task.apply_async(
        kwargs={"email_destination": config.email_destination},
        queue="ai",
    )
    return {"task_id": task.id, "status": "queued"}
