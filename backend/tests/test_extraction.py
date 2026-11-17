import fitz
import docx
import pytest
from app.services.document_processor import ExtractionError, extract_document


def test_pdf_extraction(tmp_path):
    p = tmp_path / "a.pdf"
    d = fitz.open()
    d.new_page().insert_text((72, 72), "Hello PDF world")
    d.save(p)
    pages = extract_document(p)
    assert pages[0].page_number == 1 and "Hello PDF world" in pages[0].text


def test_docx_extraction_with_sections(tmp_path):
    p = tmp_path / "a.docx"
    d = docx.Document()
    d.add_heading("Intro", level=1)
    d.add_paragraph("Some body text.")
    d.save(p)
    pages = extract_document(p)
    assert pages[0].section == "Intro" and "body text" in pages[0].text


def test_txt_extraction(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("Plain text.", encoding="utf-8")
    assert extract_document(p)[0].text == "Plain text."


def test_empty_and_corrupted_files(tmp_path):
    e = tmp_path / "e.txt"
    e.write_text("   ")
    with pytest.raises(ExtractionError):
        extract_document(e)
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf at all")
    with pytest.raises(ExtractionError):
        extract_document(bad)


def test_pdf_headings_become_markers_and_paragraphs_stay_whole(tmp_path):
    p = tmp_path / "h.pdf"
    d = fitz.open()
    page = d.new_page()
    page.insert_text((72, 72), "Retrieval Basics", fontsize=18)
    page.insert_textbox(fitz.Rect(72, 100, 520, 300),
                        "RAG retrieves relevant chunks before answering. It then generates a grounded answer.\n\n"
                        "A second paragraph follows here.", fontsize=11)
    d.save(p)
    text = extract_document(p)[0].text
    assert "## Retrieval Basics" in text
    assert "retrieves relevant chunks before answering. It then generates" in text  # wrapped lines re-joined
