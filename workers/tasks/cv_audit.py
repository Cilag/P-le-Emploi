import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from celery_app import app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="workers.tasks.cv_audit.run_cv_audit", bind=True, max_retries=3)
def run_cv_audit(self, recipient: str = "", **kwargs):
    from app.db.session import AsyncSessionLocal
    from app.models.cv import CV
    from app.models.offre import Offre
    from app.services.ai.letter_generator import generate_cv_audit
    from app.services.email_service import send_email_with_attachments
    from sqlalchemy import select

    async def _run():
        async with AsyncSessionLocal() as db:
            cv_result = await db.execute(select(CV).where(CV.actif == True).limit(1))
            cv = cv_result.scalar_one_or_none()
            if not cv or not cv.texte_extrait:
                return {"error": "No active CV found"}

            offres_result = await db.execute(
                select(Offre.titre).order_by(Offre.date_import.desc()).limit(20)
            )
            offres_recentes = [r[0] for r in offres_result.all()]
            report = generate_cv_audit(cv.texte_extrait, offres_recentes)

            report_text = f"""RAPPORT D'AUDIT CV — {cv.filename}

Score global : {report.get('score_global', 'N/A')}/10

POINTS FORTS :
{chr(10).join(f'• {p}' for p in report.get('points_forts', []))}

AXES D'AMÉLIORATION :
{chr(10).join(f'• {a}' for a in report.get('axes_amelioration', []))}

RECOMMANDATIONS :
{chr(10).join(f'• {r}' for r in report.get('recommandations', []))}

COMPÉTENCES À DÉVELOPPER :
{chr(10).join(f'• {c}' for c in report.get('competences_manquantes', []))}

RÉSUMÉ EXÉCUTIF :
{report.get('resume_executif', '')}
"""
            if recipient:
                send_email_with_attachments(
                    to=recipient,
                    subject="Audit mensuel de votre CV — Pôle Emploi Assistant",
                    body=report_text,
                )
            return {"status": "ok", "recipient": recipient, "score": report.get("score_global")}

    try:
        return run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * 5)
