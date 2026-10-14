import io
import pytest


def _make_pdf_bytes(text: str) -> bytes:
    """Build a minimal valid PDF with a single page containing *text*."""
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


def _make_docx_bytes(text: str) -> bytes:
    """Build a minimal valid DOCX with a single paragraph containing *text*."""
    import docx as python_docx
    doc = python_docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── unsupported / plain-text fallback ─────────────────────────────────────────

def test_extract_text_unsupported_extension():
    from app.services.cv_parser import extract_cv_text
    result = extract_cv_text("test.txt", b"Hello World")
    assert "Hello World" in result


def test_extract_text_utf8_fallback():
    from app.services.cv_parser import extract_cv_text
    content = "Jean Dupont, Développeur Python".encode("utf-8")
    result = extract_cv_text("cv.txt", content)
    assert "Jean Dupont" in result


# ── PDF ───────────────────────────────────────────────────────────────────────

def test_extract_text_from_pdf():
    from app.services.cv_parser import extract_cv_text
    content = _make_pdf_bytes("Marie Curie Data Scientist Paris")
    result = extract_cv_text("cv.pdf", content)
    assert "Marie Curie" in result


def test_extract_text_from_pdf_case_insensitive_extension():
    from app.services.cv_parser import extract_cv_text
    content = _make_pdf_bytes("Jean Valjean Ingenieur")
    result = extract_cv_text("CV.PDF", content)
    assert "Jean Valjean" in result


# ── DOCX ──────────────────────────────────────────────────────────────────────

def test_extract_text_from_docx():
    from app.services.cv_parser import extract_cv_text
    content = _make_docx_bytes("Pierre Martin Ingénieur Logiciel")
    result = extract_cv_text("cv.docx", content)
    assert "Pierre Martin" in result


def test_extract_text_from_doc_extension():
    """.doc extension is routed to the DOCX parser."""
    from app.services.cv_parser import extract_cv_text
    content = _make_docx_bytes("Isabelle Blanc Chef de Projet")
    result = extract_cv_text("cv.doc", content)
    assert "Isabelle Blanc" in result


# ── NUL bytes (PostgreSQL refuse \x00 dans un TEXT) ───────────────────────────

def test_extract_text_strips_nul_bytes_from_pdf(monkeypatch):
    from app.services import cv_parser

    class _Page:
        def extract_text(self):
            return "EXP\x00ÉRIENCES\x00 Bordeaux"

    class _Reader:
        def __init__(self, _stream):
            self.pages = [_Page()]

    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", _Reader)
    assert cv_parser.extract_cv_text("cv.pdf", b"%PDF") == "EXPÉRIENCES Bordeaux"


def test_extract_text_strips_nul_bytes_from_plain_text():
    from app.services.cv_parser import extract_cv_text
    assert extract_cv_text("cv.txt", b"Jean\x00 Dupont") == "Jean Dupont"
