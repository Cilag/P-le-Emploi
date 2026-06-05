from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CandidatureCreate(BaseModel):
    offre_id: int
    lettre_id: Optional[int] = None


class CandidatureUpdate(BaseModel):
    statut: str


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
    candidature_id: int
    destinataire: str
    sujet: Optional[str] = None


class ExportRequest(BaseModel):
    candidature_ids: list[int]
