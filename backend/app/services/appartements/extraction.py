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


MAX_MORCEAUX = 4


def decouper(texte: str, taille: int = TEXTE_MAX) -> list[str]:
    """Découpe aux fins de ligne en morceaux d'au plus `taille` caractères (une ligne trop longue est tronquée)."""
    morceaux, courant = [], ""
    for ligne in texte.splitlines():
        ligne = ligne[:taille]
        if courant and len(courant) + 1 + len(ligne) > taille:
            morceaux.append(courant)
            courant = ligne
        else:
            courant = f"{courant}\n{ligne}" if courant else ligne
    if courant:
        morceaux.append(courant)
    return morceaux or [""]


def extraire_annonces(texte_email: str, chat=None) -> list[AnnonceBrute]:
    """Une alerte longue (beaucoup d'annonces et de liens) est traitée en plusieurs appels, sans rien perdre."""
    morceaux = decouper(texte_email)
    if len(morceaux) > MAX_MORCEAUX:
        logger.warning("appartements : alerte de %d caractères, seuls les %d premiers morceaux sont lus",
                       len(texte_email), MAX_MORCEAUX)
    annonces = []
    for morceau in morceaux[:MAX_MORCEAUX]:
        annonces.extend(_extraire_morceau(morceau, chat))
    return annonces


def _extraire_morceau(texte: str, chat=None) -> list[AnnonceBrute]:
    if chat is None:
        from app.services.ai.llm import chat
    try:
        reponse = chat(CONSIGNES, "E-mail d'alerte :\n\n" + texte)
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
