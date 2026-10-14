"""Traitement des e-mails d'alerte : extraction, filtre, dédoublonnage, analyse, enregistrement."""
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import and_, or_, select

from app.models.appartement import AlerteEmail, Annonce, DossierLocataire
from app.services.appartements.analyse import AnalyseError
from app.services.appartements.criteres import (
    Criteres, criteres_depuis_settings, empreinte, evaluer, lien_normalise,
)
from app.services.appartements.extraction import ExtractionError
from app.services.appartements.imap import EmailAlerte

logger = logging.getLogger(__name__)

MAX_TENTATIVES = 3
LIEN_MAX = 2048
# Deux annonces de même loyer/surface/ville ne sont fusionnées que si la première est récente.
FENETRE_EMPREINTE = timedelta(days=30)


async def _dossier(db) -> str:
    d = (await db.execute(select(DossierLocataire).limit(1))).scalars().first()
    return d.texte if d else ""


def _appliquer_analyse(annonce: Annonce, dossier: str, criteres: Criteres, analyser_fn) -> None:
    try:
        r = analyser_fn(annonce, dossier, criteres)
    except AnalyseError as e:
        annonce.analyse_erreur = str(e)
        return
    annonce.note, annonce.resume = r.note, r.resume
    annonce.alertes, annonce.message = "\n".join(r.alertes), r.message
    annonce.analyse_erreur = None


def _lien_sur(lien: str | None) -> str | None:
    """Seuls les liens http(s) sont gardés (un lien « javascript: » venu d'un e-mail ne doit jamais s'afficher)."""
    if not lien:
        return None
    lien = lien.strip()
    return lien[:LIEN_MAX] if urlsplit(lien).scheme.lower() in ("http", "https") else None


async def _deja_connue(db, ln: str | None, emp: str | None) -> Annonce | None:
    conditions = []
    if ln:
        conditions.append(Annonce.lien_norm == ln)
    if emp:
        limite = datetime.now(timezone.utc) - FENETRE_EMPREINTE
        conditions.append(and_(Annonce.empreinte == emp, Annonce.recue_le >= limite))
    if not conditions:
        return None
    return (await db.execute(select(Annonce).where(or_(*conditions)).limit(1))).scalars().first()


async def ids_termines(session_factory) -> set[str]:
    """E-mails à ne plus télécharger : traités (ok, vide) ou abandonnés après MAX_TENTATIVES."""
    async with session_factory() as db:
        lignes = await db.execute(select(AlerteEmail.message_id).where(or_(
            AlerteEmail.statut.in_(("ok", "vide")), AlerteEmail.tentatives >= MAX_TENTATIVES,
        )))
        return {mid for (mid,) in lignes.all()}


async def _marquer_echec(session_factory, mail: EmailAlerte, erreur: str) -> None:
    try:
        async with session_factory() as db:
            alerte = (await db.execute(
                select(AlerteEmail).where(AlerteEmail.message_id == mail.message_id)
            )).scalars().first()
            if not alerte:
                alerte = AlerteEmail(message_id=mail.message_id, expediteur=mail.expediteur[:320],
                                     sujet=mail.sujet[:998], recu_le=mail.recu_le, statut="erreur", tentatives=0)
                db.add(alerte)
            alerte.statut, alerte.erreur = "erreur", erreur[:500]
            alerte.tentatives = (alerte.tentatives or 0) + 1
            await db.commit()
    except Exception:
        logger.exception("appartements : impossible d'enregistrer l'échec de %s", mail.message_id)


async def _traiter_email(db, mail: EmailAlerte, extraire, analyser_fn, criteres: Criteres) -> int | None:
    """Traite un e-mail dans la session donnée. None = déjà traité ; sinon nombre d'annonces créées."""
    alerte = (await db.execute(
        select(AlerteEmail).where(AlerteEmail.message_id == mail.message_id)
    )).scalars().first()
    if alerte and (alerte.statut in ("ok", "vide") or alerte.tentatives >= MAX_TENTATIVES):
        return None
    if not alerte:
        alerte = AlerteEmail(message_id=mail.message_id, expediteur=mail.expediteur[:320],
                             sujet=mail.sujet[:998], recu_le=mail.recu_le, statut="erreur", tentatives=0)
        db.add(alerte)
        await db.flush()
    try:
        brutes = extraire(mail.texte)
    except ExtractionError as e:
        alerte.statut, alerte.erreur = "erreur", str(e)[:500]
        alerte.tentatives += 1
        await db.commit()
        raise
    dossier = await _dossier(db)
    nouvelles = 0
    for b in brutes:
        verdict = evaluer(b, criteres)
        if not verdict.garde:
            logger.info("appartements : annonce écartée (%s) : %s", verdict.motif, b.titre)
            continue
        lien = _lien_sur(b.lien)
        ln = (lien_normalise(lien) or "")[:LIEN_MAX] or None
        emp = empreinte(verdict.loyer_retenu, b.surface, verdict.ville_canonique or b.ville)
        emp = emp[:255] if emp else None
        site = (b.site or "").strip().lower()[:40]
        existante = await _deja_connue(db, ln, emp)
        if existante:
            sites = [s for s in existante.sites.split(",") if s]
            if site and site not in sites and len(existante.sites) + len(site) < 250:
                existante.sites = ",".join(sites + [site])
            continue
        annonce = Annonce(
            titre=b.titre[:500], loyer=b.loyer, charges=b.charges, charges_comprises=b.charges_comprises,
            loyer_retenu=verdict.loyer_retenu, surface=b.surface, pieces=b.pieces,
            ville=b.ville[:255] if b.ville else None, quartier=b.quartier[:255] if b.quartier else None,
            lien=lien, lien_norm=ln, empreinte=emp, sites=site, drapeaux=",".join(verdict.drapeaux),
            alerte_id=alerte.id,
        )
        db.add(annonce)
        await db.flush()
        _appliquer_analyse(annonce, dossier, criteres, analyser_fn)
        nouvelles += 1
    alerte.statut = "ok" if brutes else "vide"
    alerte.nb_annonces, alerte.erreur = nouvelles, None
    await db.commit()
    return nouvelles


async def traiter_alertes(session_factory, emails: list[EmailAlerte], extraire=None, analyser_fn=None,
                          criteres: Criteres | None = None, budget_s: float | None = None,
                          horloge=time.monotonic) -> dict:
    """Une erreur sur un e-mail (quelle qu'elle soit) compte une tentative et n'arrête pas les suivants.
    Avec `budget_s`, la passe s'interrompt une fois le budget dépassé ; le reste sera lu au passage suivant."""
    if extraire is None:
        from app.services.appartements.extraction import extraire_annonces as extraire
    if analyser_fn is None:
        from app.services.appartements.analyse import analyser as analyser_fn
    criteres = criteres or criteres_depuis_settings()
    resultat = {"emails": 0, "annonces": 0, "erreurs": [], "interrompu": False}
    debut = horloge()
    for mail in emails:
        if budget_s is not None and horloge() - debut > budget_s:
            resultat["interrompu"] = True
            break
        try:
            async with session_factory() as db:
                nouvelles = await _traiter_email(db, mail, extraire, analyser_fn, criteres)
        except ExtractionError as e:
            resultat["emails"] += 1
            resultat["erreurs"].append(f"{mail.sujet[:60]} : {e}")
            continue
        except Exception as e:
            logger.exception("appartements : échec du traitement de %s", mail.message_id)
            await _marquer_echec(session_factory, mail, f"{type(e).__name__} : {e}")
            resultat["emails"] += 1
            resultat["erreurs"].append(f"{mail.sujet[:60]} : {type(e).__name__}")
            continue
        if nouvelles is None:
            continue
        resultat["emails"] += 1
        resultat["annonces"] += nouvelles
    return resultat


async def analyser_annonce(session_factory, annonce_id: int, analyser_fn=None) -> bool:
    if analyser_fn is None:
        from app.services.appartements.analyse import analyser as analyser_fn
    async with session_factory() as db:
        annonce = await db.get(Annonce, annonce_id)
        if not annonce:
            return False
        _appliquer_analyse(annonce, await _dossier(db), criteres_depuis_settings(), analyser_fn)
        await db.commit()
        return True
