import json

import pytest

from app.models.appartement import Annonce
from app.services.ai.llm import LLMError
from app.services.appartements.analyse import AnalyseError, analyser
from app.services.appartements.criteres import Criteres

C = Criteres(700, 2, ["Bordeaux", "Talence"])


def _annonce():
    return Annonce(titre="T2 Chartrons", loyer_retenu=690, surface=38, pieces=2, ville="Bordeaux",
                   quartier="Chartrons", drapeaux="charges_inconnues", sites="jinka", lien="https://x")


def test_analyse_et_contenu_du_prompt():
    vu = {}

    def chat(system, user):
        vu["system"], vu["user"] = system, user
        return "```json\n" + json.dumps({"note": 8, "resume": "Bien situé.", "alertes": ["charges inconnues"],
                                         "message": "Bonjour, je suis intéressé…"}) + "\n```"

    a = analyser(_annonce(), "Alternant, 1 400 € net, garant Visale.", C, chat=chat)
    assert (a.note, a.resume, a.alertes, a.message) == (8, "Bien situé.", ["charges inconnues"], "Bonjour, je suis intéressé…")
    assert "T2 Chartrons" in vu["user"] and "690" in vu["user"] and "garant Visale" in vu["user"]
    assert "700" in vu["user"] and "vouvoiement" in vu["system"]


def test_note_bornee_et_champs_par_defaut():
    a = analyser(_annonce(), "", C, chat=lambda s, u: '{"note": 14, "message": "Bonjour"}')
    assert a.note == 10 and a.resume == "" and a.alertes == []


def test_dossier_vide_signale_dans_le_prompt():
    vu = {}

    def chat(s, u):
        vu["user"] = u
        return '{"note": 5, "resume": "", "alertes": [], "message": "m"}'

    analyser(_annonce(), "", C, chat=chat)
    assert "[précisez votre situation]" in vu["user"]


def test_reponse_illisible():
    with pytest.raises(AnalyseError):
        analyser(_annonce(), "", C, chat=lambda s, u: "pas de json")


def test_hermes_injoignable():
    def chat(s, u):
        raise LLMError("timeout")

    with pytest.raises(AnalyseError, match="timeout"):
        analyser(_annonce(), "", C, chat=chat)
