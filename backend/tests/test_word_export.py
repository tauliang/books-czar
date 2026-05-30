from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from backend.schemas import SourceOut, SynthesisRunOut
from backend.word_export import build_synthesis_docx, word_filename


def test_build_synthesis_docx_contains_brief_sections_and_sources():
    run = SynthesisRunOut(
        id="brief-1",
        title="AI Operating Model",
        objective="Clarify the AI operating model",
        audience="c_suite",
        lens="operating_model",
        book_ids=["book-1"],
        status="complete",
        markdown=(
            "## Executive Takeaway\n"
            "Govern AI with measurable adoption goals [S1].\n\n"
            "## Recommended 30/60/90 Day Actions\n"
            "- 30 days: Confirm ownership [S1].\n\n"
            "## Metrics to Watch\n"
            "- Adoption progress [S1]."
        ),
        sources=[
            SourceOut(
                book_id="book-1",
                title="Executive AI",
                location="chunk 1",
                excerpt="AI programs need clear ownership and measured adoption.",
                score=0.87,
            )
        ],
        error=None,
        created_at="2026-05-30T12:00:00Z",
        updated_at="2026-05-30T12:00:00Z",
    )

    docx = build_synthesis_docx(run)

    assert docx.startswith(b"PK")
    with ZipFile(BytesIO(docx)) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        assert "word/styles.xml" in names
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Books Czar Board Brief" in document_xml
    assert "AI Operating Model" in document_xml
    assert "Executive Takeaway" in document_xml
    assert "Recommended 30/60/90 Day Actions" in document_xml
    assert "Metrics to Watch" in document_xml
    assert "Source Evidence" in document_xml
    assert "[S1] Executive AI" in document_xml


def test_word_filename_sanitizes_title():
    assert word_filename("AI Strategy / Board Brief") == "books-czar-ai-strategy-board-brief.docx"
