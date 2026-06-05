from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Candidature(Base):
    __tablename__ = "candidatures"

    id: Mapped[int] = mapped_column(primary_key=True)
    offre_id: Mapped[int] = mapped_column(Integer, ForeignKey("offres.id", ondelete="CASCADE"))
    lettre_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lettres.id", ondelete="SET NULL"), nullable=True)
    statut: Mapped[str] = mapped_column(String(50), default="en_attente")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
