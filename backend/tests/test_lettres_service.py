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
        db.add_all([Lettre(offre_id=o.id, entreprise="Acme", contenu="v1", version=1),
                    Lettre(offre_id=o.id, entreprise="Acme", contenu="v2", version=2)])
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: pytest.fail("ne doit pas générer"))
        lettre = await db.get(Lettre, out["lettre_id"])
    assert out["reused"] is True and lettre.contenu == "v2"


@pytest.mark.asyncio
async def test_ne_reutilise_pas_la_lettre_d_une_autre_offre_de_la_meme_entreprise(session_factory):
    appels = []

    def fake(**kw):
        appels.append(kw)
        return "Lettre DevOps"

    async with session_factory() as db:
        autre = await _offre(db, titre="Comptable", entreprise="Inconnu")
        o = await _offre(db, titre="DevOps", entreprise="Inconnu")
        db.add(Lettre(offre_id=autre.id, entreprise="Inconnu", contenu="Lettre comptable", version=1))
        await db.commit()
        out = await generer_lettre_pour_offre(db, o.id, generate=fake)
        lettre = await db.get(Lettre, out["lettre_id"])
    assert out["reused"] is False and len(appels) == 1 and appels[0]["offre_titre"] == "DevOps"
    assert lettre.offre_id == o.id and lettre.contenu == "Lettre DevOps" and lettre.version == 2


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


def test_backend_retombe_sur_les_defauts_du_worker(monkeypatch):
    import importlib

    import app.workers_client as wc

    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    wc = importlib.reload(wc)
    assert wc._celery.conf.result_backend == "redis://redis:6379/1"
    assert wc._celery.conf.broker_url == "redis://redis:6379/0"


async def _offre_linkedin(db, description=None):
    o = Offre(titre="SRE", entreprise="Acme", source="linkedin", description=description,
              lien_source="https://fr.linkedin.com/jobs/view/sre-at-acme-4460019972",
              dedup_hash=Offre.compute_hash("SRE", "Acme", "linkedin"))
    db.add(o)
    await db.commit()
    return o


@pytest.mark.asyncio
async def test_linkedin_sans_description_la_recupere_avant_la_lettre(session_factory):
    vu = {}

    async def fake_fetch(lien):
        vu["lien"] = lien
        return "Kubernetes, Terraform"

    def fake_generate(**kw):
        vu.update(kw)
        return "Lettre"

    async with session_factory() as db:
        o = await _offre_linkedin(db)
        await generer_lettre_pour_offre(db, o.id, generate=fake_generate, fetch_description=fake_fetch)
        await db.refresh(o)
    assert vu["lien"] == "https://fr.linkedin.com/jobs/view/sre-at-acme-4460019972"
    assert vu["offre_description"] == "Kubernetes, Terraform"
    assert o.description == "Kubernetes, Terraform"


@pytest.mark.asyncio
async def test_linkedin_description_indisponible_ecrit_quand_meme(session_factory):
    async def fake_fetch(lien):
        return None

    async with session_factory() as db:
        o = await _offre_linkedin(db)
        out = await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: "Lettre", fetch_description=fake_fetch)
        await db.refresh(o)
    assert out["reused"] is False and o.description is None


@pytest.mark.asyncio
async def test_description_deja_connue_pas_de_requete(session_factory):
    async def fake_fetch(lien):
        pytest.fail("aucune requête attendue")

    async with session_factory() as db:
        o = await _offre_linkedin(db, description="Déjà là")
        await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: "Lettre", fetch_description=fake_fetch)


@pytest.mark.asyncio
async def test_autre_source_pas_de_requete(session_factory):
    async def fake_fetch(lien):
        pytest.fail("aucune requête attendue")

    async with session_factory() as db:
        o = await _offre(db)
        await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: "Lettre", fetch_description=fake_fetch)


@pytest.mark.asyncio
async def test_linkedin_erreur_inattendue_ecrit_quand_meme(session_factory):
    async def fake_fetch(lien):
        raise ValueError("page inattendue")

    async with session_factory() as db:
        o = await _offre_linkedin(db)
        out = await generer_lettre_pour_offre(db, o.id, generate=lambda **kw: "Lettre", fetch_description=fake_fetch)
    assert out["reused"] is False and "lettre_id" in out
