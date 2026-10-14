"""Verrou d'exécution et état de la dernière lecture des alertes (Redis)."""
import json
from datetime import datetime, timezone

CLE_VERROU = "appartements:verrou"
CLE_ETAT = "appartements:etat"
DUREE_VERROU = 600


def prendre_verrou(r) -> bool:
    return bool(r.set(CLE_VERROU, "1", nx=True, ex=DUREE_VERROU))


def liberer_verrou(r) -> None:
    r.delete(CLE_VERROU)


def ecrire_etat(r, statut: str, erreur: str | None = None) -> None:
    r.set(CLE_ETAT, json.dumps({
        "derniere_lecture": datetime.now(timezone.utc).isoformat(),
        "statut": statut,
        "erreur": erreur,
    }))


def lire_etat(r) -> dict:
    brut = r.get(CLE_ETAT)
    if not brut:
        return {"derniere_lecture": None, "statut": None, "erreur": None}
    return json.loads(brut)
