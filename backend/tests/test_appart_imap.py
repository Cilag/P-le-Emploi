import imaplib
from email.message import EmailMessage

import pytest

from app.config import settings
from app.services.appartements import imap


def _brut(message_id="<m1@jinka.fr>", html=None, texte=None):
    m = EmailMessage()
    m["From"] = "Jinka <alertes@jinka.fr>"
    m["Subject"] = "3 nouvelles annonces"
    m["Date"] = "Wed, 14 Oct 2026 08:00:00 +0200"
    if message_id:
        m["Message-ID"] = message_id
    if texte:
        m.set_content(texte)
    if html:
        if texte:
            m.add_alternative(html, subtype="html")
        else:
            m.set_content(html, subtype="html")
    return m.as_bytes()


class FakeImap:
    def __init__(self, messages, dossier_ok=True, login_ok=True):
        self.messages, self.dossier_ok, self.login_ok = messages, dossier_ok, login_ok
        self.appels = []

    def __call__(self, host, port, timeout=None):
        self.appels.append(("connect", host, port))
        self.timeout = timeout
        return self

    def login(self, user, pw):
        self.appels.append(("login", user, pw))
        if not self.login_ok:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        return "OK", [b""]

    def select(self, dossier, readonly=False):
        self.appels.append(("select", dossier, readonly))
        return ("OK", [b"1"]) if self.dossier_ok else ("NO", [b"[NONEXISTENT] Unknown Mailbox"])

    def search(self, charset, *criteres):
        self.appels.append(("search",) + criteres)
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.messages)))]

    def fetch(self, num, quoi):
        self.appels.append(("fetch", num, quoi))
        brut = self.messages[int(num) - 1]
        if brut is None:
            return "OK", [None]
        if "HEADER.FIELDS" in quoi:
            sep = b"\r\n\r\n" if b"\r\n\r\n" in brut else b"\n\n"
            return "OK", [(b"1 (BODY[HEADER.FIELDS (MESSAGE-ID)] {n})", brut.split(sep, 1)[0]), b")"]
        return "OK", [(b"1 (BODY[] {n})", brut), b")"]

    def logout(self):
        self.appels.append(("logout",))


@pytest.fixture
def identifiants(monkeypatch):
    monkeypatch.setattr(settings, "imap_user", "")
    monkeypatch.setattr(settings, "imap_pass", "")
    monkeypatch.setattr(settings, "smtp_user", "moi@gmail.com")
    monkeypatch.setattr(settings, "smtp_pass", "secret")


def test_lecture_seule_et_repli_smtp(identifiants):
    f = FakeImap([_brut(texte="T2 Chartrons 690 €")])
    emails = imap.lire_alertes(imap_factory=f)
    assert ("connect", "imap.gmail.com", 993) in f.appels
    assert ("login", "moi@gmail.com", "secret") in f.appels
    assert ("select", '"Appartements"', True) in f.appels
    assert all(a[2].startswith("(BODY.PEEK[") for a in f.appels if a[0] == "fetch")
    assert f.timeout == 60
    assert f.appels[-1] == ("logout",)
    e = emails[0]
    assert (e.message_id, e.expediteur, e.sujet) == ("<m1@jinka.fr>", "Jinka <alertes@jinka.fr>", "3 nouvelles annonces")
    assert "T2 Chartrons 690 €" in e.texte and e.recu_le.year == 2026


def test_recherche_depuis_trois_jours_en_anglais(identifiants):
    f = FakeImap([])
    imap.lire_alertes(imap_factory=f)
    recherche = next(a for a in f.appels if a[0] == "search")
    assert recherche[1] == "SINCE" and recherche[2][3:6] in (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def test_html_converti_avec_les_liens(identifiants):
    html = '<p>T2 <b>Talence</b> 650&nbsp;€</p><a href="https://www.leboncoin.fr/ad/locations/1">Voir l\'annonce</a>'
    e = imap.lire_alertes(imap_factory=FakeImap([_brut(html=html)]))[0]
    assert "T2 Talence 650 €" in e.texte
    assert "Voir l'annonce (https://www.leboncoin.fr/ad/locations/1)" in e.texte


def test_message_id_absent_remplace_par_une_empreinte(identifiants):
    e = imap.lire_alertes(imap_factory=FakeImap([_brut(message_id=None, texte="x")]))[0]
    assert e.message_id.startswith("sha256:")


def test_dossier_absent_erreur_lisible(identifiants):
    with pytest.raises(imap.ImapError, match="Dossier IMAP « Appartements » introuvable"):
        imap.lire_alertes(imap_factory=FakeImap([], dossier_ok=False))


def test_identifiants_refuses(identifiants):
    with pytest.raises(imap.ImapError, match="Connexion IMAP refusée"):
        imap.lire_alertes(imap_factory=FakeImap([], login_ok=False))


def test_non_configure(monkeypatch):
    for k in ("imap_user", "imap_pass", "smtp_user", "smtp_pass"):
        monkeypatch.setattr(settings, k, "")
    with pytest.raises(imap.ImapError, match="IMAP non configuré"):
        imap.lire_alertes(imap_factory=FakeImap([]))


def test_messages_deja_traites_non_telecharges(identifiants):
    f = FakeImap([_brut("<deja@x>", texte="vieux"), _brut("<nouveau@x>", texte="neuf")])
    emails = imap.lire_alertes(imap_factory=f, ignorer=lambda mid: mid == "<deja@x>")
    assert [e.message_id for e in emails] == ["<nouveau@x>"]
    complets = [a for a in f.appels if a[0] == "fetch" and a[2] == "(BODY.PEEK[])"]
    assert [a[1] for a in complets] == [b"2"]


def test_message_illisible_ignore(identifiants):
    emails = imap.lire_alertes(imap_factory=FakeImap([None, _brut(texte="ok")]))
    assert [e.message_id for e in emails] == ["<m1@jinka.fr>"]


def test_dossier_non_ascii_erreur_lisible(identifiants, monkeypatch):
    monkeypatch.setattr(settings, "imap_dossier", "Locations à Bordeaux")
    with pytest.raises(imap.ImapError, match="ASCII"):
        imap.lire_alertes(imap_factory=FakeImap([]))
