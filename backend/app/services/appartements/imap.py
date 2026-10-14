"""Lecture des alertes d'annonces dans un dossier IMAP (libellé Gmail), en lecture seule."""
import email
import hashlib
import html as html_lib
import imaplib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email import policy
from email.utils import parsedate_to_datetime

from app.config import settings

_MOIS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_LIEN = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_BLOC = re.compile(r"</?(?:p|br|div|li|tr|h[1-6]|table)\b[^>]*>", re.I)
_BALISE = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)


class ImapError(Exception):
    pass


@dataclass
class EmailAlerte:
    message_id: str
    expediteur: str
    sujet: str
    recu_le: datetime | None
    texte: str


def html_vers_texte(html: str) -> str:
    """HTML → texte : liens gardés sous la forme « texte (url) », blocs séparés par des retours à la ligne."""
    h = _STYLE.sub(" ", html)
    h = _LIEN.sub(lambda m: f"{_BALISE.sub('', m.group(2)).strip()} ({m.group(1)})", h)
    h = _BALISE.sub("", _BLOC.sub("\n", h))
    lignes = (re.sub(r"\s+", " ", ligne).strip() for ligne in html_lib.unescape(h).splitlines())
    return "\n".join(ligne for ligne in lignes if ligne)


def _texte(msg) -> str:
    corps = msg.get_body(preferencelist=("plain",))
    if corps is not None:
        return corps.get_content()
    corps = msg.get_body(preferencelist=("html",))
    return html_vers_texte(corps.get_content()) if corps is not None else ""


def _depuis(jours: int) -> str:
    d = date.today() - timedelta(days=jours)
    return f"{d.day:02d}-{_MOIS[d.month - 1]}-{d.year}"


def lire_alertes(jours: int = 3, imap_factory=imaplib.IMAP4_SSL) -> list[EmailAlerte]:
    utilisateur = settings.imap_user or settings.smtp_user
    mot_de_passe = settings.imap_pass or settings.smtp_pass
    if not utilisateur or not mot_de_passe:
        raise ImapError("IMAP non configuré (IMAP_USER/IMAP_PASS ou SMTP_USER/SMTP_PASS)")
    dossier = settings.imap_dossier
    try:
        client = imap_factory(settings.imap_host, 993)
    except OSError as e:
        raise ImapError(f"Serveur IMAP injoignable : {e}") from e
    try:
        try:
            client.login(utilisateur, mot_de_passe)
        except imaplib.IMAP4.error as e:
            raise ImapError(f"Connexion IMAP refusée : {e}") from e
        statut, _ = client.select(f'"{dossier}"', readonly=True)
        if statut != "OK":
            raise ImapError(f"Dossier IMAP « {dossier} » introuvable : créez le libellé Gmail et son filtre")
        _, donnees = client.search(None, "SINCE", _depuis(jours))
        emails = []
        for num in (donnees[0] or b"").split():
            _, contenu = client.fetch(num, "(BODY.PEEK[])")
            brut = next(p[1] for p in contenu if isinstance(p, tuple))
            msg = email.message_from_bytes(brut, policy=policy.default)
            try:
                recu = parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
            except (TypeError, ValueError):
                recu = None
            emails.append(EmailAlerte(
                message_id=(msg["Message-ID"] or "").strip() or "sha256:" + hashlib.sha256(brut).hexdigest(),
                expediteur=str(msg["From"] or ""),
                sujet=str(msg["Subject"] or ""),
                recu_le=recu,
                texte=_texte(msg),
            ))
        return emails
    except imaplib.IMAP4.error as e:
        raise ImapError(f"Erreur IMAP : {e}") from e
    finally:
        try:
            client.logout()
        except Exception:
            pass
