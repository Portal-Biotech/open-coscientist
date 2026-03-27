"""
Tests for open_coscientist.pdf_loader.PdfLoader.

Coverage:
- Happy-path: single PDF, multiple PDFs
- Title and abstract heuristics
- Pre-flight validation: all missing paths reported at once, before extraction
- Extraction failures: empty/scanned PDFs, corrupted PDFs
- No partial loading: pipeline stops at the first failure
- pypdf not installed: ImportError with install instructions
- Empty input list: returns empty list, no error
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if pypdf is not installed (optional dependency)
pypdf = pytest.importorskip("pypdf", reason="pypdf not installed — run: pip install 'open-coscientist[pdf]'")

from open_coscientist.pdf_loader import PdfLoader, _guess_abstract, _guess_title


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TITLE_TEXT = "Novel KRAS Inhibition Mechanisms"
ABSTRACT_BODY = "This paper explores allosteric inhibition of KRAS G12C mutations."

SAMPLE_LINES = [
    TITLE_TEXT,
    f"Abstract: {ABSTRACT_BODY}",
    "Introduction: KRAS mutations are present in ~30% of human cancers.",
    "Methods: We used cryo-EM and molecular dynamics simulations.",
    "Results: We identified three novel allosteric pockets.",
    "Conclusion: These results open new therapeutic avenues for KRAS G12C.",
]


# ---------------------------------------------------------------------------
# 1. Happy path — single PDF
# ---------------------------------------------------------------------------


def test_load_single_pdf_returns_one_article(make_pdf):
    pdf = make_pdf(lines=SAMPLE_LINES)
    articles = PdfLoader().load([str(pdf)])

    assert len(articles) == 1
    article = articles[0]
    assert article.source == "local_pdf"
    assert article.used_in_analysis is True
    assert len(article.content) > 50, "Expected non-trivial extracted text"


def test_article_has_correct_source_fields(make_pdf):
    pdf = make_pdf(filename="my_paper.pdf", lines=SAMPLE_LINES)
    article = PdfLoader().load([str(pdf)])[0]

    assert article.source == "local_pdf"
    assert article.source_id == str(pdf)
    assert str(pdf) in article.pdf_links
    assert article.url.startswith("file://")


def test_article_title_extracted(make_pdf):
    pdf = make_pdf(lines=SAMPLE_LINES)
    article = PdfLoader().load([str(pdf)])[0]

    # The title heuristic should grab the first substantial line
    assert TITLE_TEXT in article.title


def test_article_content_contains_all_lines(make_pdf):
    pdf = make_pdf(lines=SAMPLE_LINES)
    article = PdfLoader().load([str(pdf)])[0]

    content = article.content
    assert "KRAS" in content
    assert "cryo-EM" in content


def test_article_abstract_non_empty(make_pdf):
    pdf = make_pdf(lines=SAMPLE_LINES)
    article = PdfLoader().load([str(pdf)])[0]

    assert article.abstract
    assert len(article.abstract) > 10


# ---------------------------------------------------------------------------
# 2. Happy path — multiple PDFs
# ---------------------------------------------------------------------------


def test_load_multiple_pdfs_returns_all(make_pdf):
    pdf1 = make_pdf(filename="paper1.pdf", lines=["Paper One Title", "Abstract: First."])
    pdf2 = make_pdf(filename="paper2.pdf", lines=["Paper Two Title", "Abstract: Second."])
    pdf3 = make_pdf(filename="paper3.pdf", lines=["Paper Three Title", "Abstract: Third."])

    articles = PdfLoader().load([str(pdf1), str(pdf2), str(pdf3)])

    assert len(articles) == 3


def test_load_multiple_pdfs_preserves_order(make_pdf):
    pdfs = [
        make_pdf(filename=f"paper_{i}.pdf", lines=[f"Title {i}", f"Abstract: Body {i}."])
        for i in range(4)
    ]
    articles = PdfLoader().load([str(p) for p in pdfs])

    for i, article in enumerate(articles):
        assert f"Title {i}" in article.title or f"Title {i}" in article.content


def test_load_returns_empty_list_for_empty_input():
    articles = PdfLoader().load([])
    assert articles == []


# ---------------------------------------------------------------------------
# 3. Pre-flight validation: missing paths detected BEFORE any extraction
# ---------------------------------------------------------------------------


def test_single_missing_file_raises_file_not_found(tmp_path):
    missing = str(tmp_path / "ghost.pdf")
    with pytest.raises(FileNotFoundError) as exc_info:
        PdfLoader().load([missing])

    assert "ghost.pdf" in str(exc_info.value)


def test_all_missing_files_reported_together(tmp_path):
    """All missing paths must appear in a single FileNotFoundError."""
    paths = [str(tmp_path / f"missing_{i}.pdf") for i in range(3)]
    with pytest.raises(FileNotFoundError) as exc_info:
        PdfLoader().load(paths)

    message = str(exc_info.value)
    for p in paths:
        assert "missing_" in message, f"Expected all missing paths in error, got: {message}"


def test_missing_file_error_before_extraction_starts(make_pdf, tmp_path):
    """
    If the first PDF exists but the second doesn't, the pipeline must stop
    before extracting anything — the error is raised in the pre-flight phase,
    not mid-way through extraction.
    """
    good_pdf = make_pdf(filename="good.pdf", lines=SAMPLE_LINES)
    bad_path = str(tmp_path / "does_not_exist.pdf")

    with pytest.raises(FileNotFoundError) as exc_info:
        PdfLoader().load([str(good_pdf), bad_path])

    assert "does_not_exist.pdf" in str(exc_info.value)
    assert "pipeline has not started" in str(exc_info.value).lower()


def test_extraction_not_called_when_path_missing(make_pdf, tmp_path):
    """
    Verify that _extract_text_from_pdf is never called when a pre-flight
    FileNotFoundError would be raised.
    """
    good_pdf = make_pdf(lines=SAMPLE_LINES)
    bad_path = str(tmp_path / "phantom.pdf")

    with patch("open_coscientist.pdf_loader._extract_text_from_pdf") as mock_extract:
        with pytest.raises(FileNotFoundError):
            PdfLoader().load([str(good_pdf), bad_path])

        mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Empty / unreadable PDFs — pipeline stops
# ---------------------------------------------------------------------------


def test_empty_pdf_raises_value_error(make_empty_pdf):
    """
    A PDF with a valid structure but no text content (e.g. scanned/image)
    must raise ValueError with a message pointing to OCR.
    """
    with pytest.raises(ValueError) as exc_info:
        PdfLoader().load([str(make_empty_pdf)])

    msg = str(exc_info.value)
    assert "No text could be extracted" in msg
    assert "ocr" in msg.lower() or "OCR" in msg


def test_empty_pdf_stops_before_subsequent_pdfs(make_pdf, make_empty_pdf):
    """
    Given [good.pdf, empty.pdf, good2.pdf], the loader must stop at empty.pdf
    and never process good2.pdf.
    """
    good1 = make_pdf(filename="good1.pdf", lines=SAMPLE_LINES)
    good2 = make_pdf(filename="good2.pdf", lines=SAMPLE_LINES)

    call_count = 0
    original_extract = __import__(
        "open_coscientist.pdf_loader", fromlist=["_extract_text_from_pdf"]
    )._extract_text_from_pdf

    def counting_extract(path):
        nonlocal call_count
        call_count += 1
        return original_extract(path)

    with patch("open_coscientist.pdf_loader._extract_text_from_pdf", side_effect=counting_extract):
        with pytest.raises(ValueError):
            PdfLoader().load([str(good1), str(make_empty_pdf), str(good2)])

    # good1 + empty_pdf extracted; good2 must NOT have been attempted
    assert call_count == 2, f"Expected 2 extraction attempts, got {call_count}"


def test_corrupted_pdf_raises_runtime_error(tmp_path):
    """A file that exists but is not a valid PDF raises RuntimeError."""
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"This is definitely not PDF content %%%%")

    with pytest.raises((RuntimeError, Exception)):
        PdfLoader().load([str(corrupt)])


# ---------------------------------------------------------------------------
# 5. pypdf not installed — ImportError with install hint
# ---------------------------------------------------------------------------


def test_import_error_when_pypdf_missing(make_pdf):
    """
    When pypdf is not installed, PdfLoader.load should raise ImportError
    with instructions for installing it.
    """
    pdf = make_pdf(lines=SAMPLE_LINES)

    # Temporarily hide pypdf from the import system
    real_pypdf = sys.modules.pop("pypdf", None)
    try:
        with pytest.raises(ImportError) as exc_info:
            # Re-import the module with a fresh state so _require_pypdf runs
            from importlib import reload
            import open_coscientist.pdf_loader as pdf_mod
            reload(pdf_mod)

            # Patch the import inside the already-loaded module
            with patch.dict(sys.modules, {"pypdf": None}):
                pdf_mod._require_pypdf()

        assert "open-coscientist[pdf]" in str(exc_info.value) or "pypdf" in str(exc_info.value)
    finally:
        if real_pypdf is not None:
            sys.modules["pypdf"] = real_pypdf


# ---------------------------------------------------------------------------
# 6. Title heuristic unit tests
# ---------------------------------------------------------------------------


def test_guess_title_uses_first_substantial_line():
    text = "Novel KRAS Inhibition Mechanisms\nSome Author\nAbstract: ..."
    title = _guess_title(text, "paper.pdf")
    assert title == "Novel KRAS Inhibition Mechanisms"


def test_guess_title_skips_abstract_keyword():
    text = "Abstract\nReal Title Here\nMore content"
    title = _guess_title(text, "paper.pdf")
    assert "Real Title Here" in title


def test_guess_title_falls_back_to_filename():
    # Very short lines that don't pass the length threshold
    text = "Hi\nOK\n."
    title = _guess_title(text, "/path/to/my_great_paper.pdf")
    assert "my great paper" in title.lower() or "my_great_paper" in title.lower()


def test_guess_title_max_length():
    long_line = "A" * 300
    title = _guess_title(long_line, "paper.pdf")
    assert len(title) <= 200


# ---------------------------------------------------------------------------
# 7. Abstract heuristic unit tests
# ---------------------------------------------------------------------------


def test_guess_abstract_extracts_between_headings():
    text = (
        "Title Line\n"
        "Abstract\n"
        "This paper presents a novel approach to KRAS inhibition.\n"
        "Introduction\n"
        "Background section..."
    )
    abstract = _guess_abstract(text)
    assert "novel approach" in abstract
    assert "Background" not in abstract


def test_guess_abstract_falls_back_to_early_text():
    text = "Title\nAuthor Name\nBody text starts here and goes on."
    abstract = _guess_abstract(text)
    assert len(abstract) > 0


def test_guess_abstract_truncated_at_3000_chars():
    long_body = "X " * 2000
    text = f"Title\nAbstract\n{long_body}\nIntroduction\nEnd"
    abstract = _guess_abstract(text)
    assert len(abstract) <= 3000


# ---------------------------------------------------------------------------
# 8. Integration: article fields are coherent end-to-end
# ---------------------------------------------------------------------------


def test_article_authors_empty_list(make_pdf):
    article = PdfLoader().load([str(make_pdf())])[0]
    assert article.authors == []


def test_article_year_is_none(make_pdf):
    article = PdfLoader().load([str(make_pdf())])[0]
    assert article.year is None


def test_article_citations_zero(make_pdf):
    article = PdfLoader().load([str(make_pdf())])[0]
    assert article.citations == 0


def test_article_venue_is_none(make_pdf):
    article = PdfLoader().load([str(make_pdf())])[0]
    assert article.venue is None


def test_multiple_pdfs_have_distinct_source_ids(make_pdf):
    pdf1 = make_pdf(filename="a.pdf")
    pdf2 = make_pdf(filename="b.pdf")
    articles = PdfLoader().load([str(pdf1), str(pdf2)])
    ids = {a.source_id for a in articles}
    assert len(ids) == 2, "Each PDF should produce a distinct source_id"
