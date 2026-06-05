import os

# Override DB URL before any app module loads so SQLAlchemy uses aiosqlite (no asyncpg needed)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret")
