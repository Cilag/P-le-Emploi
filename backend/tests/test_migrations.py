from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.migrations import COLUMN_MIGRATIONS, apply_column_migrations


@pytest.mark.asyncio
async def test_migrations_ignorees_hors_postgresql():
    conn = MagicMock()
    conn.dialect.name = "sqlite"
    conn.execute = AsyncMock()
    assert await apply_column_migrations(conn) == 0
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_migrations_executees_sur_postgresql():
    conn = MagicMock()
    conn.dialect.name = "postgresql"
    conn.execute = AsyncMock()
    assert await apply_column_migrations(conn) == 2
    sql = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert sql == COLUMN_MIGRATIONS
    assert all("IF NOT EXISTS" in s for s in sql)


@pytest.mark.asyncio
async def test_patch_offre_email_contact(api, session_factory):
    from app.models.offre import Offre

    async with session_factory() as db:
        o = Offre(titre="SRE", entreprise="Acme", lien_source="https://x", source="test",
                  dedup_hash=Offre.compute_hash("SRE", "Acme", ""))
        db.add(o)
        await db.commit()
    r = await api.patch(f"/offres/{o.id}", json={"email_contact": "rh@acme.fr"})
    assert r.status_code == 200 and r.json()["email_contact"] == "rh@acme.fr"
    assert (await api.patch(f"/offres/{o.id}", json={"email_contact": "pas-un-email"})).status_code == 422
    assert (await api.patch("/offres/999", json={"email_contact": None})).status_code == 404
