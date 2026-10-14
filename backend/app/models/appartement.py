from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AlerteEmail(Base):
    __tablename__ = "alertes_email"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(998), unique=True, index=True)
    expediteur: Mapped[str | None] = mapped_column(String(320), nullable=True)
    sujet: Mapped[str | None] = mapped_column(String(998), nullable=True)
    recu_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    traite_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    statut: Mapped[str] = mapped_column(String(20))
    nb_annonces: Mapped[int] = mapped_column(Integer, default=0)
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)


class Annonce(Base):
    __tablename__ = "annonces"

    id: Mapped[int] = mapped_column(primary_key=True)
    titre: Mapped[str] = mapped_column(String(500))
    loyer: Mapped[float | None] = mapped_column(Float, nullable=True)
    charges: Mapped[float | None] = mapped_column(Float, nullable=True)
    charges_comprises: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    loyer_retenu: Mapped[float | None] = mapped_column(Float, nullable=True)
    surface: Mapped[float | None] = mapped_column(Float, nullable=True)
    pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quartier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lien: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    lien_norm: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    empreinte: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sites: Mapped[str] = mapped_column(String(255), default="")
    drapeaux: Mapped[str] = mapped_column(String(255), default="")
    alerte_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("alertes_email.id", ondelete="SET NULL"), nullable=True)
    recue_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume: Mapped[str | None] = mapped_column(Text, nullable=True)
    alertes: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="a_contacter")
    vue: Mapped[bool] = mapped_column(Boolean, default=False)
    analyse_erreur: Mapped[str | None] = mapped_column(Text, nullable=True)


class DossierLocataire(Base):
    __tablename__ = "dossier_locataire"

    id: Mapped[int] = mapped_column(primary_key=True)
    texte: Mapped[str] = mapped_column(Text, default="")
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
