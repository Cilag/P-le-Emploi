"""Registre paresseux des scrapers.

Les scrapers basés sur Playwright (indeed, linkedin, hellowork, monster, letudiant)
importent ``playwright`` au niveau module ; ce paquet n'est installé que dans
l'image *worker*. Le backend ne doit donc jamais importer ces modules avant
d'en avoir réellement besoin (sinon 500 sur ``/offres/sources/list``).
"""
from collections.abc import Mapping
from importlib import import_module

_REGISTRY: dict[str, tuple[str, str]] = {
    "france_travail": ("france_travail", "FranceTravailScraper"),
    "indeed": ("indeed", "IndeedScraper"),
    "linkedin": ("linkedin", "LinkedInScraper"),
    "welcome_to_the_jungle": ("wttj", "WTTJScraper"),
    "apec": ("apec", "ApecScraper"),
    "hellowork": ("hellowork", "HelloWorkScraper"),
    "cadremploi": ("cadremploi", "CadrEmploiScraper"),
    "jobteaser": ("jobteaser", "JobTeaserScraper"),
    "monster": ("monster", "MonsterScraper"),
    "letudiant": ("letudiant", "LEtudiantScraper"),
    "regionsjob": ("regionsjob", "RegionsJobScraper"),
}


class _LazyScrapers(Mapping):
    """Se comporte comme un dict {source_name: classe} mais n'importe qu'à l'accès."""

    def __getitem__(self, key: str):
        module_name, class_name = _REGISTRY[key]
        module = import_module(f"app.services.scrapers.{module_name}")
        return getattr(module, class_name)

    def __iter__(self):
        return iter(_REGISTRY)

    def __len__(self) -> int:
        return len(_REGISTRY)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, ImportError, AttributeError):
            return default


ALL_SCRAPERS = _LazyScrapers()

__all__ = ["ALL_SCRAPERS"]
