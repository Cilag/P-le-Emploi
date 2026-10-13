from app.services.scrapers import france_travail as ft


def test_lieu_bordeaux_en_code_insee():
    assert ft.lieu_params("Bordeaux") == {"commune": "33063", "distance": 30}
    assert ft.lieu_params(" bordeaux ") == {"commune": "33063", "distance": 30}


def test_lieu_inconnu_ou_absent():
    assert ft.lieu_params("Trifouilly") == {}
    assert ft.lieu_params(None) == {}


def test_email_contact_valide_seulement():
    assert ft.email_contact({"contact": {"courriel": " rh@acme.fr "}}) == "rh@acme.fr"
    assert ft.email_contact({"contact": {"courriel": "Pour postuler : https://acme.fr/jobs"}}) is None
    assert ft.email_contact({}) is None


def test_to_offre():
    item = {
        "intitule": "Ingénieur DevOps",
        "entreprise": {"nom": "Acme"},
        "description": "K8s",
        "origineOffre": {"urlOrigine": "https://ft/1"},
        "lieuTravail": {"libelle": "33 - Bordeaux"},
        "typeContrat": "CDI",
        "dateCreation": "2026-10-12T08:00:00Z",
        "contact": {"courriel": "rh@acme.fr"},
    }
    o = ft.to_offre(item)
    assert (o.titre, o.entreprise, o.ville, o.email_contact) == ("Ingénieur DevOps", "Acme", "33 - Bordeaux", "rh@acme.fr")
    assert o.date_publication.year == 2026
