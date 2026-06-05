"""Scheduler management API — lets the frontend configure Celery Beat schedules."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import redis
import json
import os

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
SCHEDULER_CONFIG_KEY = "scheduler:cv_audit:config"


class SchedulerConfig(BaseModel):
    cron: str  # "minute hour day month dow" — e.g. "0 9 1 * *"
    recipient: EmailStr


@router.get("/cv-audit", response_model=SchedulerConfig)
async def get_cv_audit_config():
    raw = _redis.get(SCHEDULER_CONFIG_KEY)
    if not raw:
        return SchedulerConfig(
            cron=os.environ.get("CV_AUDIT_SCHEDULE_CRON", "0 9 1 * *"),
            recipient=os.environ.get("CV_AUDIT_DEFAULT_RECIPIENT", ""),
        )
    return SchedulerConfig(**json.loads(raw))


@router.put("/cv-audit", response_model=SchedulerConfig)
async def update_cv_audit_config(config: SchedulerConfig):
    parts = config.cron.split()
    if len(parts) != 5:
        raise HTTPException(status_code=422, detail="cron must have 5 fields: minute hour day month dow")
    _redis.set(SCHEDULER_CONFIG_KEY, config.model_dump_json())
    return config
