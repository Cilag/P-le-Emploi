from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class OffreBase(BaseModel):
    titre: str
    entreprise: str
    description: Optional[str] = None
    lien_source: str
    source: str
    ville: Optional[str] = None
    type_contrat: Optional[str] = None
    date_publication: Optional[datetime] = None


class OffreCreate(OffreBase):
    pass


class OffreRead(OffreBase):
    id: int
    statut: str
    date_import: datetime
    dedup_hash: str

    class Config:
        from_attributes = True


class OffreScanParams(BaseModel):
    secteur: str = "informatique"
    region: Optional[str] = None
    ville: Optional[str] = None
    type_contrat: Optional[str] = None
    mots_cles: Optional[str] = None
    sources: list[str] = []
