from pathlib import Path

import httpx
import pytest

from app.services.scrapers import linkedin

HTML = (Path(__file__).parent / "fixtures" / "linkedin_cards.html").read_text(encoding="utf-8")


def test_parse_cartes():
    offres = linkedin.parse_linkedin_cards(HTML)
    assert [(o.titre, o.entreprise) for o in offres] == [("Ingénieur DevOps", "Acme"), ("SRE", "Globex")]
    assert offres[0].ville == "Bordeaux, Nouvelle-Aquitaine, France"
    assert offres[0].lien_source == "https://fr.linkedin.com/jobs/view/ingenieur-devops-at-acme-4011"
    assert offres[1].ville is None
    assert all(o.source == "linkedin" for o in offres)


def test_parse_page_vide():
    assert linkedin.parse_linkedin_cards("") == []
    assert linkedin.parse_linkedin_cards("<html><body>Connectez-vous</body></html>") == []


def test_params_bordeaux_et_remote():
    assert linkedin.build_params("DevOps", "Bordeaux", False) == {
        "keywords": "DevOps", "location": "Bordeaux", "f_TPR": "r86400", "start": "0"}
    assert linkedin.build_params("SRE", None, True) == {
        "keywords": "SRE", "location": "France", "f_TPR": "r86400", "start": "0", "f_WT": "2"}


@pytest.mark.asyncio
async def test_scrape_encode_les_parametres():
    vu = {}

    def handler(request):
        vu["url"] = request.url
        return httpx.Response(200, text=HTML)

    s = linkedin.LinkedInScraper(transport=httpx.MockTransport(handler))
    offres = await s.scrape("informatique", None, "Bordeaux", None, "administrateur système")
    assert len(offres) == 2
    assert vu["url"].host == "www.linkedin.com"
    assert vu["url"].params["keywords"] == "administrateur système"
    assert "administrateur+syst%C3%A8me" in str(vu["url"]) or "administrateur%20syst%C3%A8me" in str(vu["url"])


@pytest.mark.asyncio
async def test_scrape_http_429_renvoie_liste_vide():
    s = linkedin.LinkedInScraper(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    assert await s.scrape("informatique", None, "Bordeaux", None, "DevOps") == []
