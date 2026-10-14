"""Note, résumé, signaux d'alerte et message au propriétaire pour une annonce (Hermes)."""
import json
from dataclasses import dataclass, field

from app.models.appartement import Annonce
from app.services.ai.llm import LLMError
from app.services.appartements.criteres import Criteres

CONSIGNES = """Tu aides un candidat locataire à trier des annonces de location. Réponds UNIQUEMENT par un objet
JSON, sans texte autour : {"note": entier 0-10, "resume": str, "alertes": [str], "message": str}.
- note : adéquation aux critères, rapport qualité/prix, quartier, date de disponibilité si mentionnée.
- resume : 2 à 3 phrases (quartier, accès au tram si mentionné, points forts).
- alertes : points à vérifier (colocation, frais d'agence élevés, charges inconnues, signes d'arnaque :
  loyer anormalement bas, demande de virement ou de mandat, propriétaire à l'étranger…). Liste vide si rien.
- message : message au propriétaire en français, 80 à 150 mots, vouvoiement, poli et concret, qui demande
  une visite ; n'invente aucune information absente du dossier du candidat."""


class AnalyseError(Exception):
    pass


@dataclass
class Analyse:
    note: int
    resume: str
    alertes: list[str] = field(default_factory=list)
    message: str = ""


def _description(a: Annonce) -> str:
    champs = [
        ("Titre", a.titre), ("Loyer retenu (€/mois)", a.loyer_retenu), ("Surface (m²)", a.surface),
        ("Pièces", a.pieces), ("Ville", a.ville), ("Quartier", a.quartier), ("Sites", a.sites),
        ("Remarques automatiques", a.drapeaux), ("Lien", a.lien),
    ]
    return "\n".join(f"{nom} : {val}" for nom, val in champs if val not in (None, ""))


def analyser(annonce: Annonce, dossier: str, criteres: Criteres, chat=None) -> Analyse:
    if chat is None:
        from app.services.ai.llm import chat
    demande = (
        f"Critères : {criteres.loyer_max:.0f} € charges comprises maximum, {criteres.pieces_max} pièces maximum, "
        f"villes : {', '.join(criteres.villes)}.\n\n"
        f"Annonce :\n{_description(annonce)}\n\n"
        f"Dossier du candidat :\n{dossier.strip() or '[précisez votre situation]'}"
    )
    try:
        reponse = chat(CONSIGNES, demande)
    except LLMError as e:
        raise AnalyseError(str(e)) from e
    debut, fin = reponse.find("{"), reponse.rfind("}")
    try:
        data = json.loads(reponse[debut:fin + 1]) if 0 <= debut < fin else None
        note = max(0, min(10, int(data["note"])))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise AnalyseError(f"réponse illisible d'Hermes : {reponse[:120]!r}") from e
    alertes = data.get("alertes") or []
    return Analyse(
        note=note,
        resume=str(data.get("resume") or ""),
        alertes=[str(x) for x in alertes] if isinstance(alertes, list) else [str(alertes)],
        message=str(data.get("message") or ""),
    )
