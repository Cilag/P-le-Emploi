"""Traitement des e-mails d'alerte : extraction, filtre, dédoublonnage, analyse, enregistrement."""
import logging

from sqlalchemy import or_, select

from app.models.appartement import AlerteEmail, Annonce, DossierLocataire
from app.services.appartements.analyse import AnalyseError
from app.services.appartements.criteres import (
    Criteres, criteres_depuis_settings, empreinte, evaluer, lien_normalise,
)
from app.services.appartements.extraction import ExtractionError
from app.services.appartements.imap import EmailAlerte

logger = logging.getLogger(__name__)

MAX_TENTATIVES = 3


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


async def _deja_connue(db, ln: str | None, emp: str | None) -> Annonce | None:
    conditions = []
    if ln:
        conditions.append(Annonce.lien_norm == ln)
    if emp:
        conditions.append(Annonce.empreinte == emp)
    if not conditions:
        return None
    return (await db.execute(select(Annonce).where(or_(*conditions)).limit(1))).scalars().first()


async def traiter_alertes(session_factory, emails: list[EmailAlerte], extraire=None, analyser_fn=None,
                          criteres: Criteres | None = None) -> dict:
    if extraire is None:
        from app.services.appartements.extraction import extraire_annonces as extraire
    if analyser_fn is None:
        from app.services.appartements.analyse import analyser as analyser_fn
    criteres = criteres or criteres_depuis_settings()
    resultat = {"emails": 0, "annonces": 0, "erreurs": []}
    for mail in emails:
        async with session_factory() as db:
            alerte = (await db.execute(
                select(AlerteEmail).where(AlerteEmail.message_id == mail.message_id)
            )).scalars().first()
            if alerte and (alerte.statut in ("ok", "vide") or alerte.tentatives >= MAX_TENTATIVES):
                continue
            if not alerte:
                alerte = AlerteEmail(message_id=mail.message_id, expediteur=mail.expediteur[:320],
                                     sujet=mail.sujet[:998], recu_le=mail.recu_le, statut="erreur", tentatives=0)
                db.add(alerte)
                await db.flush()
            resultat["emails"] += 1
            try:
                brutes = extraire(mail.texte)
            except ExtractionError as e:
                alerte.statut, alerte.erreur = "erreur", str(e)
                alerte.tentatives += 1
                resultat["erreurs"].append(f"{mail.sujet[:60]} : {e}")
                await db.commit()
                continue
            dossier = await _dossier(db)
            nouvelles = 0
            for b in brutes:
                verdict = evaluer(b, criteres)
                if not verdict.garde:
                    logger.info("appartements : annonce écartée (%s) : %s", verdict.motif, b.titre)
                    continue
                ln = lien_normalise(b.lien)
                emp = empreinte(verdict.loyer_retenu, b.surface, b.ville)
                site = (b.site or "").strip().lower()
                existante = await _deja_connue(db, ln, emp)
                if existante:
                    sites = [s for s in existante.sites.split(",") if s]
                    if site and site not in sites:
                        existante.sites = ",".join(sites + [site])
                    continue
                annonce = Annonce(
                    titre=b.titre[:500], loyer=b.loyer, charges=b.charges, charges_comprises=b.charges_comprises,
                    loyer_retenu=verdict.loyer_retenu, surface=b.surface, pieces=b.pieces,
                    ville=b.ville[:255] if b.ville else None, quartier=b.quartier[:255] if b.quartier else None,
                    lien=b.lien, lien_norm=ln, empreinte=emp, sites=site, drapeaux=",".join(verdict.drapeaux),
                    alerte_id=alerte.id,
                )
                db.add(annonce)
                await db.flush()
                _appliquer_analyse(annonce, dossier, criteres, analyser_fn)
                nouvelles += 1
            alerte.statut = "ok" if brutes else "vide"
            alerte.nb_annonces, alerte.erreur = nouvelles, None
            await db.commit()
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
