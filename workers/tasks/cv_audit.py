"""Celery task: monthly CV audit.

Triggered by Celery Beat on a configurable cron schedule.
Schedule and recipient can be updated via the backend scheduler API.
"""
from celery_app import app


@app.task(name="workers.tasks.cv_audit.run_cv_audit", bind=True, max_retries=3)
def run_cv_audit(self, recipient: str = "", **kwargs):
    """Run monthly CV audit and send report to recipient."""
    try:
        # TODO: implement CV analysis with Anthropic Claude + send email report
        print(f"[cv_audit] Running monthly audit → recipient={recipient!r}")
        return {"status": "ok", "recipient": recipient}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * 5)
