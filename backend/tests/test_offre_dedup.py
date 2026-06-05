import pytest
from app.models.offre import Offre


def test_dedup_hash_same_inputs():
    h1 = Offre.compute_hash("Développeur Python", "Acme Corp", "Paris")
    h2 = Offre.compute_hash("Développeur Python", "Acme Corp", "Paris")
    assert h1 == h2


def test_dedup_hash_normalizes_case():
    h1 = Offre.compute_hash("DÉVELOPPEUR PYTHON", "ACME CORP", "PARIS")
    h2 = Offre.compute_hash("développeur python", "acme corp", "paris")
    assert h1 == h2


def test_dedup_hash_normalizes_whitespace():
    h1 = Offre.compute_hash("  Développeur Python  ", "  Acme Corp  ", "  Paris  ")
    h2 = Offre.compute_hash("Développeur Python", "Acme Corp", "Paris")
    assert h1 == h2


def test_dedup_hash_different_inputs():
    h1 = Offre.compute_hash("Développeur Python", "Acme Corp", "Paris")
    h2 = Offre.compute_hash("Développeur Python", "Acme Corp", "Lyon")
    assert h1 != h2


def test_dedup_hash_handles_none_ville():
    h1 = Offre.compute_hash("Data Engineer", "TechCorp", None)
    h2 = Offre.compute_hash("Data Engineer", "TechCorp", "")
    assert h1 == h2


def test_dedup_hash_is_sha256_hex():
    """Hash must be a 64-character lowercase hex string (SHA-256 output)."""
    h = Offre.compute_hash("Ingénieur DevOps", "Startup SAS", "Bordeaux")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_dedup_hash_special_characters():
    """Accents and punctuation are part of the normalized key (case-folded)."""
    h1 = Offre.compute_hash("Développeur C++", "L'Oréal", "Île-de-France")
    h2 = Offre.compute_hash("développeur c++", "l'oréal", "île-de-france")
    assert h1 == h2


def test_dedup_hash_different_entreprise():
    """Same title + city but different company → different hash."""
    h1 = Offre.compute_hash("DevOps Engineer", "CompanyA", "Paris")
    h2 = Offre.compute_hash("DevOps Engineer", "CompanyB", "Paris")
    assert h1 != h2


def test_dedup_hash_different_titre():
    """Same company + city but different title → different hash."""
    h1 = Offre.compute_hash("Développeur Python", "Acme", "Paris")
    h2 = Offre.compute_hash("Développeur Django", "Acme", "Paris")
    assert h1 != h2
