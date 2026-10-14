from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models.appartement import AlerteEmail, Annonce, DossierLocataire
from app.schemas.appartement import AnnonceBrute
from app.services.appartements import etat
from app.services.appartements.analyse import Analyse, AnalyseError
from app.services.appartements.criteres import Criteres
from app.services.appartements.extraction import ExtractionError
from app.services.appartements.imap import EmailAlerte
from app.services.appartements.pipeline import MAX_TENTATIVES, analyser_annonce, traiter_alertes

C = Criteres(700, 2, ["Bordeaux", "Talence"])


def E(mid, texte="x"):
    return EmailAlerte(mid, "alertes@site.fr", "Nouvelles annonces", datetime(2026, 10, 14, tzinfo=timezone.utc), texte)


def B(**kw):
    base = dict(titre="T2 Chartrons", loyer=690, charges_comprises=True, surface=38, pieces=2,
                ville="Bordeaux", lien="https://www.jinka.fr/a?ad=1&utm_source=m", site="jinka")
    base.update(kw)
    return AnnonceBrute(**base)


def ok_analyse(annonce, dossier, criteres):
    return Analyse(note=7, resume="r", alertes=["a1", "a2"], message="m")


async def _compte(sf, modele):
    async with sf() as db:
        return (await db.execute(select(func.count()).select_from(modele))).scalar()


@pytest.mark.asyncio
async def test_traitement_complet(session_factory):
    async with session_factory() as db:
        db.add(DossierLocataire(texte="Alternant"))
        await db.commit()
    vu = {}

    def analyse(annonce, dossier, criteres):
        vu["dossier"] = dossier
        return ok_analyse(annonce, dossier, criteres)

    res = await traiter_alertes(session_factory, [E("<1>")],
                                extraire=lambda t: [B(), B(ville="Mérignac", lien="https://x/2")],
                                analyser_fn=analyse, criteres=C)
    assert res == {"emails": 1, "annonces": 1, "erreurs": []}
    async with session_factory() as db:
        a = (await db.execute(select(Annonce))).scalars().one()
        alerte = (await db.execute(select(AlerteEmail))).scalars().one()
    assert (a.loyer_retenu, a.lien_norm, a.empreinte, a.sites) == (690, "https://www.jinka.fr/a?ad=1", "690|38|bordeaux", "jinka")
    assert (a.note, a.resume, a.alertes, a.message) == (7, "r", "a1\na2", "m")
    assert (alerte.statut, alerte.nb_annonces, alerte.expediteur) == ("ok", 1, "alertes@site.fr")
    assert vu["dossier"] == "Alternant"


@pytest.mark.asyncio
async def test_meme_annonce_deux_sites_une_seule_carte(session_factory):
    extraits = {"<1>": [B()], "<2>": [B(lien="https://www.leboncoin.fr/ad/locations/9", site="leboncoin")]}
    await traiter_alertes(session_factory, [E("<1>", "<1>"), E("<2>", "<2>")], extraire=lambda t: extraits[t],
                          analyser_fn=ok_analyse, criteres=C)
    async with session_factory() as db:
        annonces = (await db.execute(select(Annonce))).scalars().all()
    assert len(annonces) == 1 and annonces[0].sites == "jinka,leboncoin"


@pytest.mark.asyncio
async def test_meme_lien_pas_de_doublon(session_factory):
    await traiter_alertes(session_factory, [E("<1>"), E("<2>")], extraire=lambda t: [B(surface=None)],
                          analyser_fn=ok_analyse, criteres=C)
    assert await _compte(session_factory, Annonce) == 1


@pytest.mark.asyncio
async def test_email_sans_annonce_vide_non_retraite(session_factory):
    appels = []

    def extraire(t):
        appels.append(t)
        return []

    await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    async with session_factory() as db:
        alerte = (await db.execute(select(AlerteEmail))).scalars().one()
    assert alerte.statut == "vide" and len(appels) == 1


@pytest.mark.asyncio
async def test_email_deja_traite_ignore(session_factory):
    appels = []

    def extraire(t):
        appels.append(t)
        return [B()]

    for _ in range(2):
        await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    assert len(appels) == 1


@pytest.mark.asyncio
async def test_email_en_erreur_retente_trois_fois(session_factory):
    appels = []

    def extraire(t):
        appels.append(t)
        raise ExtractionError("Hermes injoignable : timeout")

    for _ in range(MAX_TENTATIVES + 2):
        await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    async with session_factory() as db:
        alerte = (await db.execute(select(AlerteEmail))).scalars().one()
    assert len(appels) == MAX_TENTATIVES == 3
    assert alerte.statut == "erreur" and alerte.tentatives == 3 and "Hermes injoignable" in alerte.erreur


@pytest.mark.asyncio
async def test_erreur_puis_succes(session_factory):
    etats = iter([ExtractionError("timeout"), [B()]])

    def extraire(t):
        r = next(etats)
        if isinstance(r, Exception):
            raise r
        return r

    r1 = await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    r2 = await traiter_alertes(session_factory, [E("<1>")], extraire=extraire, analyser_fn=ok_analyse, criteres=C)
    assert r1["erreurs"] and r2["annonces"] == 1


@pytest.mark.asyncio
async def test_analyse_en_echec_conservee_sans_note_puis_relancee(session_factory):
    def ko(annonce, dossier, criteres):
        raise AnalyseError("timeout")

    await traiter_alertes(session_factory, [E("<1>")], extraire=lambda t: [B()], analyser_fn=ko, criteres=C)
    async with session_factory() as db:
        a = (await db.execute(select(Annonce))).scalars().one()
    assert a.note is None and a.analyse_erreur == "timeout"
    assert await analyser_annonce(session_factory, a.id, analyser_fn=ok_analyse) is True
    async with session_factory() as db:
        a = await db.get(Annonce, a.id)
    assert a.note == 7 and a.analyse_erreur is None
    assert await analyser_annonce(session_factory, 999, analyser_fn=ok_analyse) is False


class FakeRedis:
    def __init__(self):
        self.d = {}

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.d:
            return None
        self.d[k] = v
        return True

    def get(self, k):
        v = self.d.get(k)
        return v.encode() if isinstance(v, str) else v

    def delete(self, k):
        self.d.pop(k, None)


def test_verrou_et_etat():
    r = FakeRedis()
    assert etat.prendre_verrou(r) is True and etat.prendre_verrou(r) is False
    etat.liberer_verrou(r)
    assert etat.prendre_verrou(r) is True
    assert etat.lire_etat(r) == {"derniere_lecture": None, "statut": None, "erreur": None}
    etat.ecrire_etat(r, "erreur", "Dossier IMAP « Appartements » introuvable")
    e = etat.lire_etat(r)
    assert e["statut"] == "erreur" and "introuvable" in e["erreur"] and e["derniere_lecture"].startswith("20")
