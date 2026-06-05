from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CVRead(BaseModel):
    id: int
    filename: str
    texte_extrait: Optional[str] = None
    actif: bool
    cree_le: datetime

    class Config:
        from_attributes = True


class AuditConfig(BaseModel):
    email_destination: str
    jour_execution: int = 1


class AuditReport(BaseModel):
    points_forts: list[str]
    axes_amelioration: list[str]
    recommandations: list[str]
    score_global: Optional[int] = None
