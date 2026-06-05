from abc import ABC, abstractmethod
from typing import List
from app.schemas.offre import OffreCreate


class BaseScraper(ABC):
    source_name: str = "unknown"

    @abstractmethod
    async def scrape(
        self,
        secteur: str,
        region: str | None,
        ville: str | None,
        type_contrat: str | None,
        mots_cles: str | None,
    ) -> List[OffreCreate]:
        pass
