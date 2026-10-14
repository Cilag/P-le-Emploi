import pytest
from sqlalchemy import func, select

from app.models.offre import Offre
from app.schemas.offre import OffreCreate
from app.services.scan import daily_scan_params, executer_passe, import_offres


def _o(titre, entreprise="Acme", ville="Bordeaux"):
    return OffreCreate(titre=titre, entreprise=entreprise, lien_source="https://x", source="test", ville=ville)


async def _count(session_factory):
    async with session_factory() as db:
        return (await db.execute(select(func.count()).select_from(Offre))).scalar()


@pytest.mark.asyncio
async def test_import_offres_doublon_dans_le_lot(session_factory):
    async with session_factory() as db:
        assert await import_offres(db, [_o("SRE"), _o("SRE"), _o("DevOps")]) == (2, 1)
    assert await _count(session_factory) == 2


@pytest.mark.asyncio
async def test_import_offres_doublon_en_base(session_factory):
    async with session_factory() as db:
        await import_offres(db, [_o("SRE")])
    async with session_factory() as db:
        assert await import_offres(db, [_o(" sre "), _o("Cloud")]) == (1, 1)
    assert await _count(session_factory) == 2


def test_daily_scan_params_defauts():
    passes = daily_scan_params({})
    assert len(passes) == 8
    assert passes[0] == {"secteur": "informatique", "mots_cles": "DevOps", "ville": "Bordeaux",
                         "sources": ["france_travail", "linkedin", "adzuna", "jooble",
                                     "welcome_to_the_jungle", "apec"]}
    assert passes[4] == {"secteur": "informatique", "mots_cles": "DevOps", "ville": None,
                         "sources": ["linkedin", "remotive"], "remote": True}
    assert [p["mots_cles"] for p in passes[:4]] == ["DevOps", "administrateur système", "SRE", "ingénieur cloud"]


def test_daily_scan_params_env():
    passes = daily_scan_params({"SCAN_MOTS_CLES": " SRE ; ;Cloud", "SCAN_VILLE": "Lyon", "SCAN_SOURCES": "linkedin"})
    assert [(p["mots_cles"], p["ville"], p["sources"]) for p in passes] == [
        ("SRE", "Lyon", ["linkedin"]), ("Cloud", "Lyon", ["linkedin"]),
        ("SRE", None, ["linkedin", "remotive"]), ("Cloud", None, ["linkedin", "remotive"])]


class _Ok:
    vu = {}

    async def scrape(self, **kw):
        _Ok.vu = kw
        return [_o("SRE"), _o("SRE")]


class _Boom:
    async def scrape(self, **kw):
        raise RuntimeError("site HS")


@pytest.mark.asyncio
async def test_executer_passe_isole_les_sources(session_factory):
    res = await executer_passe(
        {"mots_cles": "SRE", "ville": None, "sources": ["boom", "ok", "absente"], "remote": True},
        {"ok": _Ok, "boom": _Boom},
        session_factory,
    )
    assert res["imported"] == 1 and res["duplicates"] == 1
    assert res["par_source"] == {"ok": 1}
    assert res["errors"] == ["boom: site HS", "absente: source inconnue"]
    assert _Ok.vu["remote"] is True and _Ok.vu["mots_cles"] == "SRE"


@pytest.mark.asyncio
async def test_executer_passe_sans_remote_ne_transmet_pas_remote(session_factory):
    await executer_passe({"mots_cles": "SRE", "sources": ["ok"]}, {"ok": _Ok}, session_factory)
    assert "remote" not in _Ok.vu
