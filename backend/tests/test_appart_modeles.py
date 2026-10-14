import pytest
from pydantic import ValidationError

from app.config import settings
from app.models.appartement import AlerteEmail, Annonce, DossierLocataire
from app.schemas.appartement import AnnonceBrute, AnnonceUpdate, DossierUpdate


def test_reglages_par_defaut():
    assert settings.imap_host == "imap.gmail.com"
    assert settings.imap_dossier == "Appartements"
    assert (settings.appart_loyer_max, settings.appart_pieces_max, settings.appart_villes) == (700, 2, "Bordeaux;Talence")


@pytest.mark.asyncio
async def test_tables_et_valeurs_par_defaut(session_factory):
    async with session_factory() as db:
        alerte = AlerteEmail(message_id="<a@b>", expediteur="alertes@jinka.fr", statut="ok")
        db.add(alerte)
        await db.flush()
        a = Annonce(titre="T2 Chartrons", alerte_id=alerte.id)
        db.add_all([a, DossierLocataire(texte="")])
        await db.commit()
        await db.refresh(a)
    assert a.statut == "a_contacter" and a.vue is False and a.sites == "" and a.drapeaux == ""
    assert a.recue_le is not None and alerte.tentatives == 0


def test_annonce_brute_tolere_les_champs_absents():
    a = AnnonceBrute(titre="Studio")
    assert a.loyer is None and a.charges_comprises is None and a.lien is None


def test_statut_et_dossier_valides():
    assert AnnonceUpdate(statut="visite").statut == "visite"
    with pytest.raises(ValidationError):
        AnnonceUpdate(statut="perdu")
    with pytest.raises(ValidationError):
        DossierUpdate(texte="x" * 3001)
