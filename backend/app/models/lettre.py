from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Lettre(Base):
    __tablename__ = "lettres"

    id: Mapped[int] = mapped_column(primary_key=True)
    offre_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("offres.id", ondelete="SET NULL"), nullable=True)
    entreprise: Mapped[str] = mapped_column(String(255), index=True)
    contenu: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
