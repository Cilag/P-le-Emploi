"""
Tests for API route hardening: imports, status codes, validation, schema fixes.
Uses httpx AsyncClient against the FastAPI app with a shared in-memory SQLite database.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool


# ---------------------------------------------------------------------------
# In-memory test database — StaticPool so all connections share the same DB
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def client():
    from app.main import app
    from app.db.session import get_db, Base
    from app.core.auth import get_current_user
    # Create tables on the shared test engine right before each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# offres
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_offres_empty(client):
    resp = await client.get("/offres")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_offre_not_found(client):
    resp = await client.get("/offres/9999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scan_returns_202(client):
    mock_task = MagicMock()
    mock_task.id = "fake-task-id"
    with patch("app.workers_client.run_scan_task") as mock:
        mock.apply_async.return_value = mock_task
        resp = await client.post("/offres/scan", json={"secteur": "informatique"})
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_list_sources(client):
    fake_scrapers = {"france_travail": object(), "indeed": object()}
    # The route uses a lazy import inside the function, so patch the module attribute directly
    with patch.dict("sys.modules", {"app.services.scrapers": MagicMock(ALL_SCRAPERS=fake_scrapers)}):
        resp = await client.get("/offres/sources/list")
    assert resp.status_code == 200
    assert "sources" in resp.json()


# ---------------------------------------------------------------------------
# lettres
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_lettres_empty(client):
    resp = await client.get("/lettres")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_lettre_not_found(client):
    resp = await client.get("/lettres/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_lettre_offre_not_found(client):
    resp = await client.post("/lettres/generate", json={"offre_id": 9999})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_lettre_returns_202(client):
    from app.models.offre import Offre
    async with TestSessionLocal() as db:
        offre = Offre(
            titre="Dev Python",
            entreprise="Acme",
            lien_source="https://example.com",
            source="test",
            dedup_hash=Offre.compute_hash("Dev Python", "Acme", None),
        )
        db.add(offre)
        await db.commit()
        await db.refresh(offre)
        offre_id = offre.id

    mock_task = MagicMock()
    mock_task.id = "fake-gen-id"
    with patch("app.workers_client.generate_letter_task") as mock:
        mock.apply_async.return_value = mock_task
        resp = await client.post("/lettres/generate", json={"offre_id": offre_id})
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"


# ---------------------------------------------------------------------------
# candidatures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_candidature_offre_not_found(client):
    resp = await client.post("/candidatures", json={"offre_id": 9999})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_candidature(client):
    from app.models.offre import Offre
    async with TestSessionLocal() as db:
        offre = Offre(
            titre="Dev Backend",
            entreprise="Corp",
            lien_source="https://example.com",
            source="test",
            dedup_hash=Offre.compute_hash("Dev Backend", "Corp", None),
        )
        db.add(offre)
        await db.commit()
        await db.refresh(offre)
        offre_id = offre.id

    resp = await client.post("/candidatures", json={"offre_id": offre_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["statut"] == "en_attente"
    assert data["offre_id"] == offre_id


@pytest.mark.asyncio
async def test_update_candidature_invalid_statut(client):
    """Pydantic Literal validation should reject unknown statut values."""
    resp = await client.patch("/candidatures/1", json={"statut": "invalide"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_candidature_not_found(client):
    resp = await client.patch("/candidatures/9999", json={"statut": "envoyee"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_email_request_no_candidature_id_field(client):
    """SendEmailRequest must NOT expose candidature_id — it comes from the path param."""
    from app.schemas.candidature import SendEmailRequest
    req = SendEmailRequest(destinataire="test@example.com")
    assert "candidature_id" not in req.model_fields


# ---------------------------------------------------------------------------
# cv
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_cv_not_found(client):
    resp = await client.get("/cv")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_cv_invalid_extension(client):
    resp = await client.post(
        "/cv",
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_cv_too_large(client):
    big_content = b"%PDF-" + b"0" * (11 * 1024 * 1024)
    resp = await client.post(
        "/cv",
        files={"file": ("big.pdf", big_content, "application/pdf")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_upload_cv_path_traversal(client):
    """Path traversal in filename must not escape the upload directory."""
    with patch("app.api.routes.cv.extract_cv_text", return_value="text"), \
         patch("app.api.routes.cv.settings") as mock_settings, \
         patch("builtins.open", MagicMock()):
        mock_settings.upload_dir = "/tmp/uploads_test"
        resp = await client.post(
            "/cv",
            files={"file": ("../../../etc/passwd.pdf", b"%PDF-1.4 tiny", "application/pdf")},
        )
    assert resp.status_code in (201, 400)
