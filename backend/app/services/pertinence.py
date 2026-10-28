"""Pertinence d'une offre par rapport aux mots-clés d'une recherche.

Plusieurs sources (Jooble, Adzuna, fin de liste France Travail) renvoient des offres sans rapport :
pour « architecture d'intérieur », Jooble répond « HR Operations Senior Manager ». On ne garde que
les offres dont le titre ou la description contient chaque terme de la recherche.
"""
import re
import unicodedata

_MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "en", "et", "au", "aux", "un", "une",
               "pour", "sur", "avec", "dans", "ou", "hf", "fh"}
# Racine commune : « architecture » et « architecte » → « archit ».
_RACINE = 6
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


def est_pertinente(titre: str | None, description: str | None, groupes: list[list[str]]) -> bool:
    """Vrai si un groupe a tous ses termes en début de mot dans le titre ou la description."""
    if not groupes:
        return True
    mots = set(_MOT.findall(_normalise(f"{titre or ''} {description or ''}")))
    return any(all(any(m.startswith(t) for m in mots) for t in groupe) for groupe in groupes)
