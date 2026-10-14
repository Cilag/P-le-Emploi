from app.schemas.appartement import AnnonceBrute
from app.services.appartements.criteres import (
    Criteres, criteres_depuis_settings, empreinte, evaluer, lien_normalise, normaliser,
)

C = Criteres(loyer_max=700, pieces_max=2, villes=["Bordeaux", "Talence"])


def A(**kw):
    base = dict(titre="T2", loyer=650, charges_comprises=True, pieces=2, ville="Bordeaux")
    base.update(kw)
    return AnnonceBrute(**base)


def test_cc_sous_le_plafond():
    v = evaluer(A(), C)
    assert v.garde and v.loyer_retenu == 650 and v.drapeaux == []


def test_hc_plus_charges_depasse():
    v = evaluer(A(loyer=650, charges_comprises=False, charges=80), C)
    assert not v.garde and v.loyer_retenu == 730 and "loyer" in v.motif


def test_hc_plus_charges_dans_le_plafond():
    v = evaluer(A(loyer=620, charges_comprises=False, charges=60), C)
    assert v.garde and v.loyer_retenu == 680


def test_hc_charges_inconnues_garde():
    v = evaluer(A(loyer=680, charges_comprises=False, charges=None), C)
    assert v.garde and v.loyer_retenu == 680 and "charges_inconnues" in v.drapeaux


def test_loyer_inconnu_garde_avec_drapeau():
    v = evaluer(A(loyer=None), C)
    assert v.garde and v.loyer_retenu is None and "loyer_inconnu" in v.drapeaux


def test_trop_de_pieces():
    assert not evaluer(A(pieces=3), C).garde


def test_pieces_inconnues():
    v = evaluer(A(pieces=None), C)
    assert v.garde and "pieces_inconnues" in v.drapeaux


def test_villes_accents_casse_et_titre():
    assert evaluer(A(ville="BORDEAUX (33000)"), C).garde
    assert evaluer(A(ville="talence"), C).garde
    assert evaluer(A(ville=None, titre="Studio à Talence"), C).garde
    assert not evaluer(A(ville="Mérignac", titre="T2 lumineux"), C).garde


def test_ville_inconnue():
    v = evaluer(A(ville=None, titre="T2 lumineux"), C)
    assert v.garde and "ville_inconnue" in v.drapeaux


def test_normaliser():
    assert normaliser("  Bègles ") == "begles" and normaliser(None) == ""


def test_lien_normalise():
    assert lien_normalise("https://www.jinka.fr/alert_result?ad=111&utm=x#top") == "https://www.jinka.fr/alert_result?ad=111"
    assert lien_normalise("https://www.leboncoin.fr/ad/locations/123?utm_source=mail") == "https://www.leboncoin.fr/ad/locations/123"
    assert lien_normalise(None) is None and lien_normalise("") is None


def test_empreinte():
    assert empreinte(690, 38.4, "Bordeaux (33000)") == "690|38|bordeaux (33000)"
    assert empreinte(690, None, "Bordeaux") is None
    assert empreinte(None, 38, "Bordeaux") is None


def test_criteres_depuis_settings():
    c = criteres_depuis_settings()
    assert (c.loyer_max, c.pieces_max, c.villes) == (700, 2, ["Bordeaux", "Talence"])
