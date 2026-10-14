"""Verrou d'exécution et état de la dernière lecture des alertes (Redis)."""
import json
import uuid
from datetime import datetime, timezone

CLE_VERROU = "appartements:verrou"
CLE_ETAT = "appartements:etat"
# Une passe s'arrête d'elle-même après BUDGET_PASSE_S (voir la tâche) : le verrou dure nettement plus.
DUREE_VERROU = 900


def prendre_verrou(r) -> str | None:
    """Renvoie un jeton propre à cette passe, ou None si une autre passe tient le verrou."""
    jeton = uuid.uuid4().hex
    return jeton if r.set(CLE_VERROU, jeton, nx=True, ex=DUREE_VERROU) else None


def liberer_verrou(r, jeton: str) -> None:
    """Ne libère que son propre verrou (une passe ne supprime jamais celui d'une autre)."""
    valeur = r.get(CLE_VERROU)
    if valeur is not None and (valeur.decode() if isinstance(valeur, bytes) else valeur) == jeton:
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
