from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class LettreBase(BaseModel):
    entreprise: str
    contenu: str


class LettreCreate(LettreBase):
    offre_id: Optional[int] = None


class LettreUpdate(BaseModel):
    contenu: str


class LettreRead(LettreBase):
    id: int
    offre_id: Optional[int] = None
    version: int
    cree_le: datetime
    modifie_le: datetime

    class Config:
        from_attributes = True


class LettreGenerateRequest(BaseModel):
    offre_id: int
    force_regenerate: bool = False
