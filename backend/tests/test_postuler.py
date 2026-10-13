from unittest.mock import MagicMock, patch

import pytest

from app.services.candidatures import DejaEnvoyee, envoyer_candidature_par_email

from app.config import settings
from app.models.candidature import Candidature
from app.models.cv import CV
from app.models.lettre import Lettre
from app.models.offre import Offre


async def _candidature(session_factory, email=None, avec_lettre=True, statut="en_attente"):
    async with session_factory() as db:
        o = Offre(titre="SRE", entreprise="Acme", lien_source="https://acme/job", source="test",
                  email_contact=email, dedup_hash=Offre.compute_hash("SRE", "Acme", ""))
        db.add(o)
        await db.flush()
        lettre = None
        if avec_lettre:
            lettre = Lettre(offre_id=o.id, entreprise="Acme", contenu="Ma lettre", version=1)
            db.add(lettre)
            await db.flush()
        c = Candidature(offre_id=o.id, lettre_id=lettre.id if lettre else None, statut=statut)
        db.add(c)
        await db.commit()
        return c.id, o.id


async def _cv_actif(session_factory, tmp_path):
    f = tmp_path / "cv.pdf"
    f.write_bytes(b"%PDF-1.4 cv")
    async with session_factory() as db:
        db.add(CV(filename="cv.pdf", filepath=str(f), texte_extrait="CV", actif=True))
        await db.commit()


@pytest.mark.asyncio
async def test_postuler_sans_lettre_409(api, session_factory):
    cid, _ = await _candidature(session_factory, avec_lettre=False)
    r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.status_code == 409 and "lettre" in r.json()["detail"]


@pytest.mark.asyncio
async def test_postuler_mode_site(api, session_factory):
    cid, _ = await _candidature(session_factory)
    r = await api.post(f"/candidatures/{cid}/postuler")
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "site" and body["lien"] == "https://acme/job"
    assert body["lettre_texte"] == "Ma lettre" and isinstance(body["lettre_id"], int)
    async with session_factory() as db:
        assert (await db.get(Candidature, cid)).statut == "en_attente"


@pytest.mark.asyncio
async def test_postuler_mode_email(api, session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "resend_api_key", "")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr")
    await _cv_actif(session_factory, tmp_path)
    with patch("app.services.candidatures.send_email_with_attachments", return_value=True) as send:
        r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.json() == {"mode": "email", "destinataire": "rh@acme.fr"}
    assert send.call_args.args[0] == "rh@acme.fr"
    assert any(name.startswith("lettre_") for name, _ in send.call_args.args[3])
    assert ("cv.pdf", b"%PDF-1.4 cv") in send.call_args.args[3]
    async with session_factory() as db:
        c = await db.get(Candidature, cid)
    assert c.statut == "envoyee" and c.envoyee_le is not None


@pytest.mark.asyncio
async def test_postuler_deja_envoyee_409(api, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr", statut="envoyee")
    with patch("app.services.candidatures.send_email_with_attachments", return_value=True) as send:
        r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.status_code == 409 and "déjà envoyée" in r.json()["detail"]
    send.assert_not_called()


@pytest.mark.asyncio
async def test_postuler_smtp_absent_503(api, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "resend_api_key", "")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr")
    r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.status_code == 503 and r.json()["detail"] == "SMTP non configuré"


@pytest.mark.asyncio
async def test_postuler_envoi_echoue_500(api, session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr")
    await _cv_actif(session_factory, tmp_path)
    with patch("app.services.candidatures.send_email_with_attachments", return_value=False):
        r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.status_code == 500
    async with session_factory() as db:
        c = await db.get(Candidature, cid)
    assert c.statut == "en_attente" and c.envoyee_le is None


@pytest.mark.asyncio
async def test_postuler_sans_cv_409(api, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr")
    with patch("app.services.candidatures.send_email_with_attachments", return_value=True) as send:
        r = await api.post(f"/candidatures/{cid}/postuler")
    assert r.status_code == 409 and "CV introuvable" in r.json()["detail"]
    send.assert_not_called()
    async with session_factory() as db:
        assert (await db.get(Candidature, cid)).statut == "en_attente"


@pytest.mark.asyncio
async def test_envoi_reservation_atomique(session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    cid, _ = await _candidature(session_factory, email="rh@acme.fr")
    await _cv_actif(session_factory, tmp_path)
    async with session_factory() as db1:
        c = await db1.get(Candidature, cid)
        async with session_factory() as db2:
            (await db2.get(Candidature, cid)).statut = "envoyee"
            await db2.commit()
        assert c.statut == "en_attente"
        with patch("app.services.candidatures.send_email_with_attachments", return_value=True) as send:
            with pytest.raises(DejaEnvoyee):
                await envoyer_candidature_par_email(db1, c, "rh@acme.fr")
        send.assert_not_called()


@pytest.mark.asyncio
async def test_postuler_inconnue_404(api):
    assert (await api.post("/candidatures/999/postuler")).status_code == 404


@pytest.mark.asyncio
async def test_marquer_envoyee(api, session_factory):
    cid, _ = await _candidature(session_factory)
    r = await api.post(f"/candidatures/{cid}/marquer-envoyee")
    assert r.status_code == 200 and r.json()["statut"] == "envoyee" and r.json()["envoyee_le"]


@pytest.mark.asyncio
async def test_liste_enrichie(api, session_factory):
    await _candidature(session_factory, email="rh@acme.fr")
    item = (await api.get("/candidatures")).json()[0]
    assert item["offre_titre"] == "SRE" and item["offre_entreprise"] == "Acme"
    assert item["offre_lien"] == "https://acme/job" and item["offre_email_contact"] == "rh@acme.fr"


@pytest.mark.asyncio
async def test_preparer_sans_cv_409(api, session_factory):
    _, oid = await _candidature(session_factory, avec_lettre=False)
    r = await api.post("/candidatures/preparer", json={"offre_id": oid})
    assert r.status_code == 409 and "CV" in r.json()["detail"]


@pytest.mark.asyncio
async def test_preparer_reprend_la_candidature_et_lance_la_lettre(api, session_factory):
    cid, oid = await _candidature(session_factory, avec_lettre=False)
    async with session_factory() as db:
        db.add(CV(filename="cv.pdf", filepath="/x", texte_extrait="CV", actif=True))
        await db.commit()
    with patch("app.workers_client.generate_letter_task") as task:
        task.apply_async.return_value = MagicMock(id="t1")
        r = await api.post("/candidatures/preparer", json={"offre_id": oid})
    assert r.status_code == 202
    assert r.json() == {"candidature_id": cid, "task_id": "t1", "status": "queued"}
    kwargs = task.apply_async.call_args.kwargs
    assert kwargs["kwargs"] == {"offre_id": oid, "force_regenerate": False, "candidature_id": cid}
    assert kwargs["queue"] == "ai"


@pytest.mark.asyncio
async def test_preparer_offre_inconnue_404(api):
    assert (await api.post("/candidatures/preparer", json={"offre_id": 999})).status_code == 404


@pytest.mark.asyncio
async def test_fichier_cv_actif(api, session_factory, tmp_path):
    assert (await api.get("/cv/actif/fichier")).status_code == 404
    f = tmp_path / "cv.pdf"
    f.write_bytes(b"%PDF-1.4 cv")
    async with session_factory() as db:
        db.add(CV(filename="cv.pdf", filepath=str(f), texte_extrait="CV", actif=True))
        await db.commit()
    r = await api.get("/cv/actif/fichier")
    assert r.status_code == 200 and r.content == b"%PDF-1.4 cv"
