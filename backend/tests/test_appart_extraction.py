import json
from pathlib import Path

import pytest

from app.services.ai.llm import LLMError
from app.services.appartements import extraction

TEXTE = (Path(__file__).parent / "fixtures" / "alerte_jinka.txt").read_text(encoding="utf-8")
REPONSE = [
    {"titre": "Appartement 2 pièces 38 m² – Bordeaux Chartrons", "loyer": 690, "charges_comprises": True,
     "charges": None, "surface": 38, "pieces": 2, "ville": "Bordeaux", "quartier": "Chartrons",
     "lien": "https://www.jinka.fr/alert_result?ad=111&utm_source=mail", "site": "jinka"},
    {"titre": "Studio 24 m² – Talence", "loyer": 520, "charges_comprises": False, "charges": 40,
     "surface": 24, "pieces": 1, "ville": "Talence", "quartier": "Forum",
     "lien": "https://www.jinka.fr/alert_result?ad=222", "site": "jinka"},
]


def test_extraction_et_consignes():
    vu = {}

    def chat(system, user):
        vu["system"], vu["user"] = system, user
        return "Voici les annonces :\n```json\n" + json.dumps(REPONSE) + "\n```"

    annonces = extraction.extraire_annonces(TEXTE, chat=chat)
    assert [(a.ville, a.loyer, a.pieces) for a in annonces] == [("Bordeaux", 690, 2), ("Talence", 520, 1)]
    assert "JSON" in vu["system"] and "Chartrons" in vu["user"]


def test_texte_long_decoupe_en_plusieurs_appels():
    appels = []

    def chat(system, user):
        appels.append(user)
        return json.dumps([{"titre": f"annonce {len(appels)}"}])

    texte = "\n".join(f"ligne {i} " + "x" * 90 for i in range(150))
    annonces = extraction.extraire_annonces(texte, chat=chat)
    assert len(appels) == 3 and all(len(u) <= extraction.TEXTE_MAX + 100 for u in appels)
    assert [a.titre for a in annonces] == ["annonce 1", "annonce 2", "annonce 3"]
    assert "ligne 0 " in appels[0] and "ligne 149 " in appels[-1]


def test_ligne_unique_trop_longue_tronquee():
    vu = []
    extraction.extraire_annonces("A" * 9000, chat=lambda s, u: vu.append(u) or "[]")
    assert len(vu) == 1 and "A" * 7000 in vu[0] and "A" * 7001 not in vu[0]


def test_entree_invalide_ignoree():
    rep = json.dumps([{"loyer": 500}, {"titre": "T1", "loyer": "pas un nombre"}, {"titre": "T1 Talence", "loyer": 600}])
    annonces = extraction.extraire_annonces("x", chat=lambda s, u: rep)
    assert [a.titre for a in annonces] == ["T1 Talence"]


def test_liste_vide():
    assert extraction.extraire_annonces("x", chat=lambda s, u: "[]") == []


def test_reponse_illisible():
    with pytest.raises(extraction.ExtractionError, match="illisible"):
        extraction.extraire_annonces("x", chat=lambda s, u: "Désolé, je ne peux pas.")


def test_hermes_injoignable():
    def chat(s, u):
        raise LLMError("Hermes injoignable : timeout")

    with pytest.raises(extraction.ExtractionError, match="Hermes injoignable"):
        extraction.extraire_annonces("x", chat=chat)
