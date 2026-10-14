from pathlib import Path

import httpx
import pytest

from app.services.scrapers import linkedin

HTML = (Path(__file__).parent / "fixtures" / "linkedin_job_posting.html").read_text(encoding="utf-8")


def test_job_id_depuis_le_lien():
    assert linkedin.job_id("https://fr.linkedin.com/jobs/view/sre-at-acme-4460019972") == "4460019972"
    assert linkedin.job_id(
        "https://fr.linkedin.com/jobs/view/technicien-at-vyv-4460019972?position=1&refId=abc%3D%3D"
    ) == "4460019972"
    assert linkedin.job_id("https://example.com/offre") is None
    assert linkedin.job_id("") is None


def test_parse_description():
    texte = linkedin.parse_description(HTML)
    assert texte.startswith("À propos de nous")
    assert "Acme exploite 40 clusters Kubernetes." in texte
    assert "Automatiser avec Terraform & Ansible" in texte
    assert "\n\n\n" not in texte


def test_parse_description_absente():
    assert linkedin.parse_description("<html><body>Connectez-vous</body></html>") is None


@pytest.mark.asyncio
async def test_fetch_description_appelle_l_endpoint_public():
    vu = {}

    def handler(request):
        vu["url"] = str(request.url)
        return httpx.Response(200, text=HTML)

    texte = await linkedin.fetch_description(
        "https://fr.linkedin.com/jobs/view/sre-at-acme-4460019972?position=1",
        transport=httpx.MockTransport(handler),
    )
    assert vu["url"] == "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4460019972"
    assert "Kubernetes" in texte


@pytest.mark.asyncio
async def test_fetch_description_429_renvoie_none():
    t = httpx.MockTransport(lambda r: httpx.Response(429))
    assert await linkedin.fetch_description("https://fr.linkedin.com/jobs/view/x-4460019972", transport=t) is None


@pytest.mark.asyncio
async def test_fetch_description_erreur_reseau_renvoie_none():
    def handler(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    t = httpx.MockTransport(handler)
    assert await linkedin.fetch_description("https://fr.linkedin.com/jobs/view/x-4460019972", transport=t) is None


@pytest.mark.asyncio
async def test_fetch_description_lien_sans_id_ne_fait_aucune_requete():
    def handler(request):
        pytest.fail("aucune requête attendue")

    assert await linkedin.fetch_description("https://example.com/offre", transport=httpx.MockTransport(handler)) is None
