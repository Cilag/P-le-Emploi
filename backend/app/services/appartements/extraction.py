"""Extraction des annonces d'un e-mail d'alerte (format variable selon le site) par Hermes."""
import json
import logging

from pydantic import ValidationError

from app.schemas.appartement import AnnonceBrute
from app.services.ai.llm import LLMError

logger = logging.getLogger(__name__)

TEXTE_MAX = 7000

CONSIGNES = """Tu extrais des annonces de location immobilière d'un e-mail d'alerte (Jinka, Leboncoin, SeLoger,
Bien'ici, PAP…). Réponds UNIQUEMENT par un tableau JSON, sans texte autour. Un objet par annonce :
{"titre": str, "loyer": nombre|null, "charges_comprises": true|false|null, "charges": nombre|null,
 "surface": nombre|null, "pieces": entier|null, "ville": str|null, "quartier": str|null,
 "lien": str|null, "site": str|null}
Règles : loyer mensuel en euros sans symbole ; charges_comprises vrai si « CC » ou « charges comprises »,
faux si « HC » ou « hors charges » ; studio = 1 pièce, T1 = 1, T2 = 2 ; lien = l'URL de l'annonce
(pas les liens de désabonnement ou de paramètres) ; n'invente rien, mets null si absent.
Aucune annonce → []."""


class ExtractionError(Exception):
    pass


def extraire_annonces(texte_email: str, chat=None) -> list[AnnonceBrute]:
    if chat is None:
        from app.services.ai.llm import chat
    try:
        reponse = chat(CONSIGNES, "E-mail d'alerte :\n\n" + texte_email[:TEXTE_MAX])
    except LLMError as e:
        raise ExtractionError(str(e)) from e
    debut, fin = reponse.find("["), reponse.rfind("]")
    if debut < 0 or fin < debut:
        raise ExtractionError(f"réponse illisible d'Hermes : {reponse[:120]!r}")
    try:
        brutes = json.loads(reponse[debut:fin + 1])
    except json.JSONDecodeError as e:
        raise ExtractionError(f"réponse illisible d'Hermes : {e}") from e
    annonces = []
    for b in brutes if isinstance(brutes, list) else []:
        try:
            annonces.append(AnnonceBrute.model_validate(b))
        except ValidationError:
            logger.info("appartements : entrée d'annonce invalide ignorée : %r", b)
    return annonces
