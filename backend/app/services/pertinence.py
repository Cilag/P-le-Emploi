"""Pertinence d'une offre par rapport aux mots-clés d'une recherche.

Plusieurs sources (Jooble, Adzuna, fin de liste France Travail) renvoient des offres sans rapport :
pour « architecture d'intérieur », Jooble répond « HR Operations Senior Manager ». On ne garde que
les offres dont le titre contient chaque terme, ou la description l'expression recherchée.
"""
import re
import unicodedata

_MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "en", "et", "au", "aux", "un", "une",
               "pour", "sur", "avec", "dans", "ou", "hf", "fh"}
# Racine commune : « architecture » et « architecte » → « architect » ; au-delà de 9 lettres
# on coupe, en deçà on garde le mot entier (« interi » attrapait « intérim »).
_RACINE = 9
_MOT = re.compile(r"[a-z0-9]+")


def _normalise(texte: str | None) -> str:
    return unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()


def groupes_de_termes(mots_cles: str | None) -> list[list[str]]:
    """« React, Python » → [["react"], ["python"]] : virgule et point-virgule séparent des alternatives."""
    groupes = []
    for partie in re.split(r"[,;]", mots_cles or ""):
        termes = [m[:_RACINE] for m in _MOT.findall(_normalise(partie))
                  if len(m) > 1 and m not in _MOTS_VIDES]
        if termes:
            groupes.append(termes)
    return groupes


def _mots(texte: str | None) -> list[str]:
    return [m for m in _MOT.findall(_normalise(texte)) if len(m) > 1 and m not in _MOTS_VIDES]


def _dans_le_titre(mots: list[str], groupe: list[str]) -> bool:
    return all(any(m.startswith(t) for m in mots) for t in groupe)


def _expression_dans(mots: list[str], groupe: list[str]) -> bool:
    n = len(groupe)
    return any(all(mots[i + k].startswith(t) for k, t in enumerate(groupe)) for i in range(len(mots) - n + 1))


def est_pertinente(titre: str | None, description: str | None, groupes: list[list[str]]) -> bool:
    """Vrai si un groupe a tous ses termes dans le titre (peu importe l'ordre), ou à la suite dans la
    description : « ministère de l'Intérieur » + « architecture » ailleurs ne vaut pas « architecture d'intérieur »."""
    if not groupes:
        return True
    mots_titre, mots_desc = _mots(titre), _mots(description)
    return any(_dans_le_titre(mots_titre, g) or _expression_dans(mots_desc, g) for g in groupes)
