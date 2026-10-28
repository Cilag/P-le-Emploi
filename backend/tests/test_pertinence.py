from app.services.pertinence import est_pertinente, groupes_de_termes


def test_groupes_retire_accents_mots_vides_et_elisions():
    assert groupes_de_termes("Architecture d'Intérieur") == [["archit", "interi"]]


def test_groupes_virgule_ou_point_virgule_separent_des_alternatives():
    assert groupes_de_termes("React, Python;DevOps") == [["react"], ["python"], ["devops"]]


def test_groupes_vides():
    assert groupes_de_termes(None) == []
    assert groupes_de_termes(" , d' ") == []


def test_architecture_interieur_garde_le_metier():
    g = groupes_de_termes("architecture d'interieur")
    assert est_pertinente("Architecte d'intérieur (H/F)", None, g)
    assert est_pertinente("Dessinateur en Architecture d'Intérieur Luxe H/F", "", g)
    assert est_pertinente("Designer d'Espace", "Agence d'architecture intérieure à Bordeaux", g)


def test_architecture_interieur_ecarte_les_offres_hors_sujet():
    g = groupes_de_termes("architecture d'interieur")
    assert not est_pertinente("HR Operations Senior Manager", "Manage HR processes", g)
    assert not est_pertinente("Battery Pack Architect M/F", "Design battery architecture", g)
    assert not est_pertinente("Assistant de direction H/F", "Accueil, agenda, courrier", g)


def test_une_alternative_suffit():
    g = groupes_de_termes("React, Python")
    assert est_pertinente("Développeur Python", None, g)
    assert not est_pertinente("Développeur Java", None, g)


def test_sans_termes_tout_est_pertinent():
    assert est_pertinente("N'importe quoi", None, [])


def test_le_terme_doit_commencer_un_mot():
    g = groupes_de_termes("SRE")
    assert est_pertinente("Ingénieur SRE", None, g)
    assert not est_pertinente("Commissaire aux comptes", "chaussures", g)
