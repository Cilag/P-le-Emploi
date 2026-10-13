from unittest.mock import MagicMock, patch

import pytest

from app.models.candidature import Candidature
from app.models.cv import CV
from app.models.lettre import Lettre
from app.models.offre import Offre
from app.services.lettres import generer_lettre_pour_offre


async def _offre(db, titre="SRE", entreprise="Acme"):
    o = Offre(titre=titre, entreprise=entreprise, lien_source="https://x", source="test",
              dedup_hash=Offre.compute_hash(titre, entreprise, ""))
    db.add(o)
    await db.commit()
    return o


@pytest.mark.asyncio
async def test_genere_avec_le_cv_actif(session_factory):
    vu = {}

    def fake(**kw):
        vu.update(kw)
        return "Lettre"

    async with session_factory() as db:
        o = await _offre(db)
        db.add(CV(filename="cv.pdf", filepath="/x", texte_extrait="Mon CV", actif=True))
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, generate=fake)
        lettre = await db.get(Lettre, out["lettre_id"])
    assert out["reused"] is False
    assert vu["cv_text"] == "Mon CV" and vu["offre_entreprise"] == "Acme"
    assert lettre.contenu == "Lettre" and lettre.version == 1


@pytest.mark.asyncio
async def test_reutilise_derniere_version_sans_planter(session_factory):
    async with session_factory() as db:
        o = await _offre(db)
        db.add_all([Lettre(entreprise="Acme", contenu="v1", version=1),
                    Lettre(entreprise="Acme", contenu="v2", version=2)])
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: pytest.fail("ne doit pas générer"))
        lettre = await db.get(Lettre, out["lettre_id"])
    assert out["reused"] is True and lettre.contenu == "v2"


@pytest.mark.asyncio
async def test_force_regenerate_cree_version_suivante(session_factory):
    async with session_factory() as db:
        o = await _offre(db)
        db.add_all([Lettre(entreprise="Acme", contenu="v1", version=1),
                    Lettre(entreprise="Acme", contenu="v2", version=2)])
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, force_regenerate=True, generate=lambda **kw: "v3")
        lettre = await db.get(Lettre, out["lettre_id"])
    assert out["reused"] is False and lettre.version == 3


@pytest.mark.asyncio
async def test_rattache_la_lettre_a_la_candidature(session_factory):
    async with session_factory() as db:
        o = await _offre(db)
        c = Candidature(offre_id=o.id)
        db.add(c)
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, candidature_id=c.id, generate=lambda **kw: "L")
        await db.refresh(c)
    assert c.lettre_id == out["lettre_id"]


@pytest.mark.asyncio
async def test_offre_inconnue(session_factory):
    async with session_factory() as db:
        assert await generer_lettre_pour_offre(db, 999) == {"error": "Offre not found"}


@pytest.mark.asyncio
async def test_statut_generation_echec_renvoie_le_message(api):
    res = MagicMock()
    res.failed.return_value = True
    res.result = RuntimeError("Hermes injoignable : timeout")
    with patch("app.workers_client.get_celery_app") as gca:
        gca.return_value.AsyncResult.return_value = res
        r = await api.get("/lettres/generate/abc")
    assert r.status_code == 200
    assert r.json() == {"task_id": "abc", "status": "FAILURE", "result": None,
                        "error": "Hermes injoignable : timeout"}


@pytest.mark.asyncio
async def test_statut_scan_echec_renvoie_le_message(api):
    res = MagicMock()
    res.failed.return_value = True
    res.result = RuntimeError("boom")
    with patch("app.workers_client.get_celery_app") as gca:
        gca.return_value.AsyncResult.return_value = res
        r = await api.get("/offres/scan/abc")
    assert r.json()["error"] == "boom"


def test_backend_lit_les_resultats_dans_celery_result_backend(monkeypatch):
    import importlib

    import app.workers_client as wc

    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    wc = importlib.reload(wc)
    assert wc._celery.conf.result_backend == "redis://redis:6379/1"
    assert wc._celery.conf.broker_url == "redis://redis:6379/0"
