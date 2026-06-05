import hashlib
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Offre(Base):
    __tablename__ = "offres"

    id: Mapped[int] = mapped_column(primary_key=True)
    titre: Mapped[str] = mapped_column(String(500))
    entreprise: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    lien_source: Mapped[str] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(50))
    ville: Mapped[str | None] = mapped_column(String(255))
    type_contrat: Mapped[str | None] = mapped_column(String(50))
    date_publication: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_import: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    statut: Mapped[str] = mapped_column(String(50), default="nouvelle")
    dedup_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    @staticmethod
    def compute_hash(titre: str, entreprise: str, ville: str) -> str:
        raw = f"{titre.lower().strip()}|{entreprise.lower().strip()}|{(ville or '').lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()
