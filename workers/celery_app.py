import os
from celery import Celery
from celery.schedules import crontab

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

app = Celery("pole_emploi", broker=BROKER_URL, backend=RESULT_BACKEND)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# ── Beat schedule (configurable via API) ─────────────────────────────────────
# Default: monthly CV audit on the 1st at 09:00 Europe/Paris
_cv_schedule = os.environ.get("CV_AUDIT_SCHEDULE_CRON", "0 9 1 * *").split()
_minute, _hour, _day, _month, _dow = _cv_schedule

app.conf.beat_schedule = {
    "monthly-cv-audit": {
        "task": "workers.tasks.cv_audit.run_cv_audit",
        "schedule": crontab(
            minute=_minute,
            hour=_hour,
            day_of_month=_day,
            month_of_year=_month,
            day_of_week=_dow,
        ),
        "args": [],
        "kwargs": {"recipient": os.environ.get("CV_AUDIT_DEFAULT_RECIPIENT", "")},
    }
}
