"""Sources par API : Adzuna, Jooble (clé gratuite) et Remotive (sans clé)."""
import json

import httpx
import pytest

from app.config import settings
from app.services.scrapers import adzuna, jooble, remotive

KW = dict(secteur="informatique", region=None, type_contrat=None)


def _interdit(request):
    pytest.fail("aucune requête attendue")


# ── Adzuna ────────────────────────────────────────────────────────────────────

ADZUNA_JSON = {
    "results": [
        {
            "title": "Ingénieur <strong>DevOps</strong> H/F",
            "company": {"display_name": "Acme"},
            "location": {"display_name": "Bordeaux, Gironde"},
            "description": "Kubernetes et Terraform…",
            "redirect_url": "https://www.adzuna.fr/land/ad/123?se=x",
            "created": "2026-10-13T08:00:00Z",
            "contract_type": "permanent",
        },
        {"title": "SRE", "company": {}, "location": {}, "redirect_url": "https://www.adzuna.fr/land/ad/124",
         "contract_type": "contract"},
        {"title": "", "redirect_url": "https://x"},
    ]
}


@pytest.fixture
def cles(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "id1")
    monkeypatch.setattr(settings, "adzuna_app_key", "k" * 32)
    monkeypatch.setattr(settings, "jooble_api_key", "j" * 36)


@pytest.mark.asyncio
async def test_adzuna_requete_et_conversion(cles):
    vu = {}

    def handler(request):
        vu["url"] = request.url
        return httpx.Response(200, json=ADZUNA_JSON)

    offres = await adzuna.AdzunaScraper(transport=httpx.MockTransport(handler)).scrape(
        ville="Bordeaux", mots_cles="DevOps", **KW)
    p = vu["url"].params
    assert vu["url"].path == "/v1/api/jobs/fr/search/1"
    assert (p["app_id"], p["what"], p["where"], p["distance"], p["max_days_old"]) == (
        "id1", "DevOps", "Bordeaux", "30", "2")
    assert [(o.titre, o.entreprise, o.type_contrat) for o in offres] == [
        ("Ingénieur DevOps H/F", "Acme", "CDI"), ("SRE", "Inconnu", "CDD")]
    assert offres[0].ville == "Bordeaux, Gironde" and offres[0].source == "adzuna"
    assert offres[0].description == "Kubernetes et Terraform…" and offres[0].date_publication.year == 2026


@pytest.mark.asyncio
async def test_adzuna_sans_cle_ne_fait_rien(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "")
    s = adzuna.AdzunaScraper(transport=httpx.MockTransport(_interdit))
    assert await s.scrape(ville="Bordeaux", mots_cles="DevOps", **KW) == []


@pytest.mark.asyncio
async def test_adzuna_erreur_http(cles):
    t = httpx.MockTransport(lambda r: httpx.Response(401, json={"exception": "AUTH_FAIL"}))
    assert await adzuna.AdzunaScraper(transport=t).scrape(ville="Bordeaux", mots_cles="DevOps", **KW) == []


# ── Jooble ────────────────────────────────────────────────────────────────────

JOOBLE_JSON = {
    "totalCount": 2,
    "jobs": [
        {"title": "Administrateur Systèmes &amp; Réseaux", "company": "Globex", "location": "Bordeaux (33)",
         "snippet": "&nbsp;Linux, <b>Ansible</b>...", "link": "https://fr.jooble.org/desc/42", "type": "CDI",
         "updated": "2026-10-13T09:15:00.0000000"},
        {"title": "SRE", "company": "", "location": "", "snippet": "", "link": "https://fr.jooble.org/desc/43",
         "type": "Temps plein, contrat à durée indéterminée et autres très longues mentions"},
    ],
}


@pytest.mark.asyncio
async def test_jooble_requete_et_conversion(cles):
    vu = {}

    def handler(request):
        vu["url"], vu["body"] = str(request.url), json.loads(request.content)
        return httpx.Response(200, json=JOOBLE_JSON)

    offres = await jooble.JoobleScraper(transport=httpx.MockTransport(handler)).scrape(
        ville="Bordeaux", mots_cles="administrateur système", **KW)
    assert vu["url"] == "https://jooble.org/api/" + "j" * 36
    assert vu["body"] == {"keywords": "administrateur système", "location": "Bordeaux, France", "page": "1"}
    a, b = offres
    assert (a.titre, a.entreprise, a.ville, a.type_contrat) == (
        "Administrateur Systèmes & Réseaux", "Globex", "Bordeaux (33)", "CDI")
    assert a.description == "Linux, Ansible..." and a.source == "jooble" and a.date_publication.day == 13
    assert b.entreprise == "Inconnu" and len(b.type_contrat) <= 50


@pytest.mark.asyncio
async def test_jooble_sans_cle_ne_fait_rien(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "")
    s = jooble.JoobleScraper(transport=httpx.MockTransport(_interdit))
    assert await s.scrape(ville="Bordeaux", mots_cles="DevOps", **KW) == []


@pytest.mark.asyncio
async def test_jooble_erreur_http(cles):
    t = httpx.MockTransport(lambda r: httpx.Response(403))
    assert await jooble.JoobleScraper(transport=t).scrape(ville="Bordeaux", mots_cles="DevOps", **KW) == []


# ── Remotive ──────────────────────────────────────────────────────────────────

REMOTIVE_JSON = {
    "jobs": [
        {"url": "https://remotive.com/remote-jobs/devops/sre-1", "title": "Senior SRE", "company_name": "Initech",
         "job_type": "full_time", "publication_date": "2026-10-12T10:00:00",
         "candidate_required_location": "Europe", "description": "<p>Run <b>Kubernetes</b></p>"},
        {"url": "https://remotive.com/remote-jobs/devops/2", "title": "DevOps", "company_name": "US Only Inc",
         "job_type": "full_time", "candidate_required_location": "USA Only", "description": ""},
        {"url": "https://remotive.com/remote-jobs/devops/3", "title": "Cloud Engineer", "company_name": "Hooli",
         "job_type": "contract", "candidate_required_location": "Worldwide", "description": ""},
        {"url": "https://remotive.com/remote-jobs/devops/4", "title": "Platform Engineer", "company_name": "Pied",
         "job_type": "full_time", "candidate_required_location": "France, Germany", "description": ""},
    ]
}


@pytest.mark.asyncio
async def test_remotive_passe_teletravail_filtre_les_pays():
    vu = {}

    def handler(request):
        vu["url"] = request.url
        return httpx.Response(200, json=REMOTIVE_JSON)

    offres = await remotive.RemotiveScraper(transport=httpx.MockTransport(handler)).scrape(
        ville=None, mots_cles="SRE", remote=True, **KW)
    assert str(vu["url"]).startswith("https://remotive.com/api/remote-jobs")
    assert vu["url"].params["search"] == "SRE"
    assert [o.titre for o in offres] == ["Senior SRE", "Cloud Engineer", "Platform Engineer"]
    assert offres[0].description == "Run Kubernetes" and offres[0].ville == "Télétravail (Europe)"
    assert offres[0].source == "remotive" and offres[0].lien_source == "https://remotive.com/remote-jobs/devops/sre-1"


@pytest.mark.asyncio
async def test_remotive_hors_passe_teletravail_ne_fait_rien():
    s = remotive.RemotiveScraper(transport=httpx.MockTransport(_interdit))
    assert await s.scrape(ville="Bordeaux", mots_cles="SRE", **KW) == []


@pytest.mark.asyncio
async def test_remotive_erreur_reseau():
    def handler(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    s = remotive.RemotiveScraper(transport=httpx.MockTransport(handler))
    assert await s.scrape(ville=None, mots_cles="SRE", remote=True, **KW) == []


def test_sources_enregistrees():
    from app.services.scrapers import ALL_SCRAPERS

    assert ALL_SCRAPERS["adzuna"] is adzuna.AdzunaScraper
    assert ALL_SCRAPERS["jooble"] is jooble.JoobleScraper
    assert ALL_SCRAPERS["remotive"] is remotive.RemotiveScraper


def test_texte_brut_separe_les_blocs_sans_espacer_les_balises_en_ligne():
    from app.services.scrapers.api_commun import texte_brut

    assert texte_brut("<p>Missions</p><ul><li>Kubernetes</li><li>Terraform</li></ul>") == "Missions Kubernetes Terraform"
    assert texte_brut("Ligne 1<br>Ligne 2") == "Ligne 1 Ligne 2"
    assert texte_brut("<b>Dev</b><strong>Ops</strong> &amp; SRE&nbsp;!") == "DevOps & SRE !"
