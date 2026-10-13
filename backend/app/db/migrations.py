"""Colonnes ajoutées après la création des tables (pas d'Alembic : create_all n'altère pas l'existant)."""
from sqlalchemy import text

COLUMN_MIGRATIONS = [
    "ALTER TABLE offres ADD COLUMN IF NOT EXISTS email_contact VARCHAR(320)",
    "ALTER TABLE candidatures ADD COLUMN IF NOT EXISTS envoyee_le TIMESTAMPTZ",
]


async def apply_column_migrations(conn) -> int:
    """Exécute les ALTER idempotents ; PostgreSQL seulement (SQLite ne connaît pas IF NOT EXISTS ici)."""
    if conn.dialect.name != "postgresql":
        return 0
    for sql in COLUMN_MIGRATIONS:
        await conn.execute(text(sql))
    return len(COLUMN_MIGRATIONS)
