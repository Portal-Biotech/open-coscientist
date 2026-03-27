"""
Shared pytest fixtures for Open Coscientist tests.

The ``make_pdf`` helper constructs a minimal but fully valid PDF
(Type1/Helvetica text, correct xref table) using only the Python
standard library.  This keeps the test suite self-contained — pypdf
is already an optional dependency, but no *write* library is needed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

import pytest


# ---------------------------------------------------------------------------
# Internal PDF builder
# ---------------------------------------------------------------------------


def _build_pdf(lines: List[str]) -> bytes:
    """
    Construct a minimal valid PDF containing *lines* as extractable text.

    The resulting file uses:
    - A single page (A4, 595×842 pt)
    - Helvetica (built-in Type1 font, no embedding required)
    - A content stream with BT…ET text operators
    - A correct cross-reference table so that ``pypdf.PdfReader`` can
      extract the text with ``page.extract_text()``.
    """
    # --- content stream ---------------------------------------------------
    escaped = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in lines]
    stream_parts = ["BT", "/F1 12 Tf", "72 750 Td"]
    for i, ln in enumerate(escaped):
        if i == 0:
            stream_parts.append(f"({ln}) Tj")
        else:
            stream_parts.append(f"0 -18 Td ({ln}) Tj")
    stream_parts.append("ET")
    stream_bytes = "\n".join(stream_parts).encode("latin-1")
    stream_len = len(stream_bytes)

    # --- object bodies (without leading offset) ---------------------------
    o1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    o3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]\n"
        b"   /Resources << /Font << /F1 << /Type /Font /Subtype /Type1"
        b" /BaseFont /Helvetica >> >> >>\n"
        b"   /Contents 4 0 R >>\nendobj\n"
    )
    o4 = (
        b"4 0 obj\n<< /Length "
        + str(stream_len).encode()
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )

    # --- assemble with xref -----------------------------------------------
    header = b"%PDF-1.4\n"
    bodies = [o1, o2, o3, o4]
    offsets: List[int] = []
    pos = len(header)
    for body in bodies:
        offsets.append(pos)
        pos += len(body)

    xref_pos = pos
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF\n"
    )

    return header + b"".join(bodies) + xref + trailer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_pdf(tmp_path):
    """
    Factory fixture that writes a PDF to *tmp_path* and returns its Path.

    Usage::

        def test_something(make_pdf):
            pdf = make_pdf(
                filename="paper.pdf",
                lines=["My Paper Title", "Abstract: This paper discusses..."],
            )
            assert pdf.exists()
    """

    def _factory(
        filename: str = "test_paper.pdf",
        lines: List[str] | None = None,
    ) -> Path:
        if lines is None:
            lines = [
                "Novel KRAS Inhibition Mechanisms",
                "Abstract: This paper explores allosteric inhibition of KRAS G12C.",
                "Introduction: KRAS mutations are found in ~30% of human cancers.",
                "Methods: We used cryo-EM and molecular dynamics simulations.",
                "Results: We identified three novel binding pockets.",
                "Conclusion: These findings open new therapeutic avenues.",
            ]
        dest = tmp_path / filename
        dest.write_bytes(_build_pdf(lines))
        return dest

    return _factory


@pytest.fixture
def make_empty_pdf(tmp_path):
    """
    Fixture that writes a valid PDF whose page has an empty content stream
    (simulates a scanned/image-only PDF that yields no extractable text).
    """
    o1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    # Page with an empty content stream — pypdf will extract "" from it
    o3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]"
        b" /Contents 4 0 R >>\nendobj\n"
    )
    o4 = b"4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n"

    header = b"%PDF-1.4\n"
    bodies = [o1, o2, o3, o4]
    offsets: List[int] = []
    pos = len(header)
    for body in bodies:
        offsets.append(pos)
        pos += len(body)

    xref_pos = pos
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF\n"
    )

    dest = tmp_path / "empty_paper.pdf"
    dest.write_bytes(header + b"".join(bodies) + xref + trailer)
    return dest
