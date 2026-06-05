from app.services.scrapers.france_travail import FranceTravailScraper
from app.services.scrapers.indeed import IndeedScraper
from app.services.scrapers.linkedin import LinkedInScraper
from app.services.scrapers.wttj import WTTJScraper
from app.services.scrapers.apec import ApecScraper
from app.services.scrapers.hellowork import HelloWorkScraper
from app.services.scrapers.cadremploi import CadrEmploiScraper
from app.services.scrapers.jobteaser import JobTeaserScraper
from app.services.scrapers.monster import MonsterScraper
from app.services.scrapers.letudiant import LEtudiantScraper
from app.services.scrapers.regionsjob import RegionsJobScraper

ALL_SCRAPERS = {
    "france_travail": FranceTravailScraper,
    "indeed": IndeedScraper,
    "linkedin": LinkedInScraper,
    "welcome_to_the_jungle": WTTJScraper,
    "apec": ApecScraper,
    "hellowork": HelloWorkScraper,
    "cadremploi": CadrEmploiScraper,
    "jobteaser": JobTeaserScraper,
    "monster": MonsterScraper,
    "letudiant": LEtudiantScraper,
    "regionsjob": RegionsJobScraper,
}
