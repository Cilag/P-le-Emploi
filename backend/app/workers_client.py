import os

from celery import Celery
from app.config import settings

# Mêmes URL que le worker (celery_app.py) : sinon les résultats écrits par le worker sont introuvables.
_celery = Celery(
    broker=os.environ.get("CELERY_BROKER_URL") or settings.redis_url,
    backend=os.environ.get("CELERY_RESULT_BACKEND") or settings.redis_url,
)


def _task(name: str):
    return _celery.signature(name)


class _ScanTask:
    @staticmethod
    def apply_async(kwargs: dict, queue: str = "scraping"):
        return _celery.send_task(
            "workers.tasks.scraping.run_scan",
            kwargs=kwargs,
            queue=queue,
        )


class _GenerateLetterTask:
    @staticmethod
    def apply_async(kwargs: dict, queue: str = "ai"):
        return _celery.send_task(
            "workers.tasks.ai.generate_letter",
            kwargs=kwargs,
            queue=queue,
        )


class _CvAuditTask:
    @staticmethod
    def apply_async(kwargs: dict, queue: str = "ai"):
        return _celery.send_task(
            "workers.tasks.cv_audit.run_cv_audit",
            kwargs=kwargs,
            queue=queue,
        )


run_scan_task = _ScanTask()
generate_letter_task = _GenerateLetterTask()
run_cv_audit_task = _CvAuditTask()


def get_celery_app() -> Celery:
    return _celery
