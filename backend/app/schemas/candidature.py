from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr


class CandidatureCreate(BaseModel):
    offre_id: int
    lettre_id: Optional[int] = None


class CandidatureUpdate(BaseModel):
    statut: Literal["en_attente", "envoyee", "refusee", "entretien", "acceptee"]


class CandidatureRead(BaseModel):
    id: int
    offre_id: int
    lettre_id: Optional[int] = None
    statut: str
    cree_le: datetime
    modifie_le: datetime

    class Config:
        from_attributes = True


class SendEmailRequest(BaseModel):
    destinataire: EmailStr
    sujet: Optional[str] = None


class ExportRequest(BaseModel):
    candidature_ids: list[int]
