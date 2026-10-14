from unittest.mock import MagicMock, patch

import pytest

from app.models.appartement import AlerteEmail, Annonce


async def _annonces(sf):
    async with sf() as db:
        db.add_all([
            Annonce(titre="vue note 9", note=9, vue=True, ville="Bordeaux"),
            Annonce(titre="non vue note 5", note=5, vue=False, ville="Talence"),
            Annonce(titre="non vue note 8", note=8, vue=False, ville="Bordeaux"),
            Annonce(titre="non vue sans note", note=None, vue=False, ville="Bordeaux", statut="refuse"),
        ])
        await db.commit()


@pytest.mark.asyncio
async def test_liste_triee_et_filtres(api, session_factory):
    await _annonces(session_factory)
    titres = [a["titre"] for a in (await api.get("/appartements")).json()]
    assert titres == ["non vue note 8", "non vue note 5", "non vue sans note", "vue note 9"]
    assert [a["titre"] for a in (await api.get("/appartements", params={"ville": "talence"})).json()] == ["non vue note 5"]
    assert len((await api.get("/appartements", params={"note_min": 8})).json()) == 2
    assert [a["titre"] for a in (await api.get("/appartements", params={"statut": "refuse"})).json()] == ["non vue sans note"]


@pytest.mark.asyncio
async def test_detail_marque_vue_et_patch(api, session_factory):
    await _annonces(session_factory)
    a = (await api.get("/appartements")).json()[0]
    assert (await api.get(f"/appartements/{a['id']}")).json()["vue"] is True
    r = await api.patch(f"/appartements/{a['id']}", json={"statut": "visite"})
    assert r.status_code == 200 and r.json()["statut"] == "visite"
    assert (await api.patch(f"/appartements/{a['id']}", json={"statut": "perdu"})).status_code == 422
    assert (await api.get("/appartements/999")).status_code == 404


@pytest.mark.asyncio
async def test_dossier(api):
    assert (await api.get("/appartements/dossier")).json()["texte"] == ""
    r = await api.put("/appartements/dossier", json={"texte": "Alternant, garant Visale"})
    assert r.status_code == 200 and r.json()["texte"] == "Alternant, garant Visale"
    assert (await api.get("/appartements/dossier")).json()["texte"] == "Alternant, garant Visale"
    assert (await api.put("/appartements/dossier", json={"texte": "x" * 3001})).status_code == 422


@pytest.mark.asyncio
async def test_etat_affiche_l_erreur(api, session_factory):
    async with session_factory() as db:
        db.add_all([AlerteEmail(message_id="<1>", statut="ok", nb_annonces=2),
                    AlerteEmail(message_id="<2>", statut="erreur", tentatives=3, sujet="3 annonces Jinka",
                                erreur="Hermes injoignable"),
                    AlerteEmail(message_id="<3>", statut="erreur", tentatives=1, sujet="en cours")])
        await db.commit()
    with patch("app.api.routes.appartements.lire_etat",
               return_value={"derniere_lecture": "2026-10-14T08:00:00+00:00", "statut": "erreur",
                             "erreur": "Dossier IMAP « Appartements » introuvable"}):
        e = (await api.get("/appartements/etat")).json()
    assert e["dernier_statut"] == "erreur" and "introuvable" in e["derniere_erreur"]
    assert e["nb_alertes_24h"] == 3 and e["derniere_lecture"].startswith("2026-10-14")
    assert e["alertes_abandonnees"] == [{"sujet": "3 annonces Jinka", "erreur": "Hermes injoignable"}]


@pytest.mark.asyncio
async def test_lire_maintenant_et_relancer_analyse(api, session_factory):
    await _annonces(session_factory)
    with patch("app.workers_client.lire_alertes_task") as t:
        t.apply_async.return_value = MagicMock(id="t1")
        r = await api.post("/appartements/lire-maintenant")
    assert r.status_code == 202 and r.json()["task_id"] == "t1"
    a = (await api.get("/appartements")).json()[0]
    with patch("app.workers_client.analyser_annonce_task") as t:
        t.apply_async.return_value = MagicMock(id="t2")
        r = await api.post(f"/appartements/{a['id']}/analyser")
    assert r.status_code == 202 and t.apply_async.call_args.kwargs["kwargs"] == {"annonce_id": a["id"]}
    assert (await api.post("/appartements/999/analyser")).status_code == 404
