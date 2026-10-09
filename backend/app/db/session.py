import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings

_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://").replace(
    "postgresql+psycopg2://", "postgresql+asyncpg://"
)
# Les workers Celery ouvrent une boucle d'evenements neuve par tache (run_async).
# Un pool y conserverait des connexions asyncpg rattachees a une boucle deja
# fermee : la tache suivante echoue alors sur
#   RuntimeError: got Future <...> attached to a different loop
# NullPool ouvre une connexion par session, toujours liee a la boucle courante.
# L'API FastAPI tourne sur une boucle unique et garde son pool.
_pool_kwargs = (
    {"poolclass": NullPool}
    if os.getenv("DB_DISABLE_POOL") == "1"
    else {"pool_pre_ping": True}
)

engine = create_async_engine(_db_url, echo=False, **_pool_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
