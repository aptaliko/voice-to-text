import io

from docx import Document

from app.docx_export import build_docx


def test_paragraphs_and_title():
    data = build_docx("Πρώτη παράγραφος.\n\nΔεύτερη\nγραμμή.", title="ΣΥΜΒΟΛΑΙΟ")
    doc = Document(io.BytesIO(data))
    texts = [p.text for p in doc.paragraphs]
    assert texts == ["ΣΥΜΒΟΛΑΙΟ", "Πρώτη παράγραφος.", "Δεύτερη\nγραμμή."]
