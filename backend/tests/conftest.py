import os
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# backend root → enables `from app.xxx` imports
_here = os.path.dirname(__file__)
_backend = os.path.abspath(os.path.join(_here, ".."))
sys.path.insert(0, os.path.join(_backend, "app"))  # `from workers_client import …`
sys.path.insert(0, _backend)                        # `from app.xxx import …`

# Override settings BEFORE pydantic-settings reads env at first Settings() instantiation.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/test_pe.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("CV_AUDIT_DEFAULT_RECIPIENT", "test@example.com")


@pytest_asyncio.fixture
async def session_factory():
    """Base SQLite en mémoire, tables créées, partagée par toutes les sessions du test."""
    from app.db.session import Base
    import app.models.candidature  # noqa: F401
    import app.models.cv  # noqa: F401
    import app.models.lettre  # noqa: F401
    import app.models.offre  # noqa: F401
    import app.models.appartement  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def api(session_factory):
    """Client HTTP authentifié sur l'app, branché sur la base de test."""
    from app.core.auth import get_current_user
    from app.db.session import get_db
    from app.main import app

    async def _get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: "admin"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
