import httpx
from typing import List
from datetime import datetime
from app.schemas.offre import OffreCreate
from app.services.scrapers.base import BaseScraper
from app.config import settings


class FranceTravailScraper(BaseScraper):
    source_name = "france_travail"
    TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            self.TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.francetravail_client_id,
                "client_secret": settings.francetravail_client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def scrape(self, secteur, region, ville, type_contrat, mots_cles) -> List[OffreCreate]:
        if not settings.francetravail_client_id:
            return []

        offres = []
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_token(client)
            params: dict = {"motsCles": mots_cles or secteur, "range": "0-49"}
            if ville:
                params["commune"] = ville
            if type_contrat:
                contract_map = {"CDI": "CDI", "CDD": "CDD", "alternance": "CFA"}
                params["typeContrat"] = contract_map.get(type_contrat, type_contrat)

            resp = await client.get(
                self.SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            for item in data.get("resultats", []):
                offres.append(
                    OffreCreate(
                        titre=item.get("intitule", ""),
                        entreprise=item.get("entreprise", {}).get("nom", "Inconnu"),
                        description=item.get("description", ""),
                        lien_source=item.get("origineOffre", {}).get("urlOrigine", ""),
                        source=self.source_name,
                        ville=item.get("lieuTravail", {}).get("libelle", ""),
                        type_contrat=item.get("typeContrat", ""),
                        date_publication=datetime.fromisoformat(
                            item["dateCreation"].replace("Z", "+00:00")
                        ) if item.get("dateCreation") else None,
                    )
                )
        return offres
