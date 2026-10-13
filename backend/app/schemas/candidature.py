from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr


StatutCandidature = Literal["en_attente", "envoyee", "refusee", "entretien", "acceptee"]


class CandidatureCreate(BaseModel):
    offre_id: int
    lettre_id: Optional[int] = None


class CandidatureUpdate(BaseModel):
    statut: StatutCandidature


class CandidatureRead(BaseModel):
    id: int
    offre_id: int
    lettre_id: Optional[int] = None
    statut: str
    cree_le: datetime
    modifie_le: datetime
    envoyee_le: Optional[datetime] = None
    offre_titre: Optional[str] = None
    offre_entreprise: Optional[str] = None
    offre_lien: Optional[str] = None
    offre_email_contact: Optional[str] = None

    class Config:
        from_attributes = True


class PreparerRequest(BaseModel):
    offre_id: int


class SendEmailRequest(BaseModel):
    destinataire: EmailStr
    sujet: Optional[str] = None


class ExportRequest(BaseModel):
    candidature_ids: list[int]
