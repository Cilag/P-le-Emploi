import os

from celery import Celery

# Mêmes URL et mêmes défauts que le worker (workers/celery_app.py) : sinon les résultats écrits
# par le worker sont introuvables.
DEFAULT_BROKER_URL = "redis://redis:6379/0"
DEFAULT_RESULT_BACKEND = "redis://redis:6379/1"

_celery = Celery(
    broker=os.environ.get("CELERY_BROKER_URL") or DEFAULT_BROKER_URL,
    backend=os.environ.get("CELERY_RESULT_BACKEND") or DEFAULT_RESULT_BACKEND,
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


class _LireAlertesTask:
    @staticmethod
    def apply_async(kwargs: dict, queue: str = "default"):
        return _celery.send_task("workers.tasks.appartements.lire_alertes", kwargs=kwargs, queue=queue)


class _AnalyserAnnonceTask:
    @staticmethod
    def apply_async(kwargs: dict, queue: str = "default"):
        return _celery.send_task("workers.tasks.appartements.analyser_annonce", kwargs=kwargs, queue=queue)


run_scan_task = _ScanTask()
generate_letter_task = _GenerateLetterTask()
run_cv_audit_task = _CvAuditTask()
lire_alertes_task = _LireAlertesTask()
analyser_annonce_task = _AnalyserAnnonceTask()


def get_celery_app() -> Celery:
    return _celery
