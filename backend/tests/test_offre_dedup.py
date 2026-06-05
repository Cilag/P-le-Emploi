import pytest
import sys
import os



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
