from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

StatutAnnonce = Literal["a_contacter", "contacte", "visite", "refuse", "retenu"]


class AnnonceBrute(BaseModel):
    """Annonce telle qu'extraite d'un e-mail d'alerte par Hermes."""
    titre: str
    loyer: Optional[float] = None
    charges_comprises: Optional[bool] = None
    charges: Optional[float] = None
    surface: Optional[float] = None
    pieces: Optional[int] = None
    ville: Optional[str] = None
    quartier: Optional[str] = None
    lien: Optional[str] = None
    site: Optional[str] = None


class AnnonceRead(BaseModel):
    id: int
    titre: str
    loyer: Optional[float] = None
    charges: Optional[float] = None
    charges_comprises: Optional[bool] = None
    loyer_retenu: Optional[float] = None
    surface: Optional[float] = None
    pieces: Optional[int] = None
    ville: Optional[str] = None
    quartier: Optional[str] = None
    lien: Optional[str] = None
    sites: str
    drapeaux: str
    recue_le: datetime
    note: Optional[int] = None
    resume: Optional[str] = None
    alertes: Optional[str] = None
    message: Optional[str] = None
    statut: str
    vue: bool
    analyse_erreur: Optional[str] = None

    class Config:
        from_attributes = True


class AnnonceUpdate(BaseModel):
    statut: StatutAnnonce


class DossierUpdate(BaseModel):
    texte: str = Field(max_length=3000)


class DossierRead(BaseModel):
    texte: str
    modifie_le: Optional[datetime] = None
