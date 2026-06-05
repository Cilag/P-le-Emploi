import pytest
import sys
import os




def test_extract_text_unsupported_extension():
    from app.services.cv_parser import extract_cv_text
    result = extract_cv_text("test.txt", b"Hello World")
    assert "Hello World" in result


def test_extract_text_utf8_fallback():
    from app.services.cv_parser import extract_cv_text
    content = "Jean Dupont, Développeur Python".encode("utf-8")
    result = extract_cv_text("cv.txt", content)
    assert "Jean Dupont" in result
