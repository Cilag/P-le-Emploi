"""Critères de recherche (loyer, pièces, villes) et clés de dédoublonnage."""
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import settings
from app.schemas.appartement import AnnonceBrute

_PARAMS_SUIVI = {"utm", "xtor", "ref", "source"}


@dataclass
class Criteres:
    loyer_max: float
    pieces_max: int
    villes: list[str]


@dataclass
class Verdict:
    garde: bool
    loyer_retenu: float | None
    drapeaux: list[str] = field(default_factory=list)
    motif: str | None = None


def criteres_depuis_settings() -> Criteres:
    villes = [v.strip() for v in settings.appart_villes.split(";") if v.strip()]
    return Criteres(loyer_max=settings.appart_loyer_max, pieces_max=settings.appart_pieces_max, villes=villes)


def normaliser(s: str | None) -> str:
    if not s:
        return ""
    sans_accents = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return sans_accents.lower().strip()


def _loyer_retenu(a: AnnonceBrute) -> tuple[float | None, list[str]]:
    if a.loyer is None:
        return None, ["loyer_inconnu"]
    if a.charges_comprises:
        return a.loyer, []
    if a.charges is not None:
        return a.loyer + a.charges, []
    return a.loyer, ["charges_inconnues"]


def evaluer(a: AnnonceBrute, c: Criteres) -> Verdict:
    loyer, drapeaux = _loyer_retenu(a)
    if loyer is not None and loyer > c.loyer_max:
        return Verdict(False, loyer, drapeaux, f"loyer {loyer:.0f} € > {c.loyer_max:.0f} €")
    if a.pieces is None:
        drapeaux.append("pieces_inconnues")
    elif a.pieces > c.pieces_max:
        return Verdict(False, loyer, drapeaux, f"{a.pieces} pièces > {c.pieces_max}")
    villes = [normaliser(v) for v in c.villes]
    dans_ville = any(v in normaliser(a.ville) for v in villes) if a.ville else False
    dans_titre = any(v in normaliser(a.titre) for v in villes)
    if not dans_ville and not dans_titre:
        if a.ville:
            return Verdict(False, loyer, drapeaux, f"ville hors critères : {a.ville}")
        drapeaux.append("ville_inconnue")
    return Verdict(True, loyer, drapeaux)


def lien_normalise(lien: str | None) -> str | None:
    """Lien sans fragment ni paramètres de suivi (utm_*, xtor…) ; les paramètres d'identifiant restent."""
    if not lien:
        return None
    p = urlsplit(lien.strip())
    garde = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm") and k.lower() not in _PARAMS_SUIVI]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(garde), ""))


def empreinte(loyer_retenu: float | None, surface: float | None, ville: str | None) -> str | None:
    """Même loyer, même surface, même ville : la même annonce relayée par deux sites."""
    if loyer_retenu is None or surface is None:
        return None
    return f"{round(loyer_retenu)}|{round(surface)}|{normaliser(ville)}"
