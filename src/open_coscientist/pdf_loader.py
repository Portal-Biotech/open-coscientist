"""
PDF loader for user-supplied research papers.

Extracts text from local PDF files and converts them to Article objects
that can be injected into the hypothesis generation pipeline via
``opts["user_inputs"]["pdf_paths"]``.

Requires pypdf (optional dependency)::

    pip install "open-coscientist[pdf]"
    # or
    pip install pypdf

Example::

    from open_coscientist import HypothesisGenerator, PdfLoader

    generator = HypothesisGenerator(model_name="anthropic/claude-sonnet-4-5")
    result = await generator.generate_hypotheses(
        research_goal="Novel KRAS inhibition mechanisms",
        opts={
            "user_inputs": {
                "pdf_paths": ["papers/kras_2023.pdf", "papers/ras_review.pdf"],
                "supplement_with_mcp": False,  # True to also search PubMed
            }
        },
    )
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Article

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_pypdf() -> Any:
    """Import pypdf, raising a helpful error if not installed."""
    try:
        import pypdf  # noqa: F401

        return pypdf
    except ImportError as exc:
        raise ImportError(
            "pypdf is required to load PDF files.\n"
            "Install it with:\n"
            '    pip install "open-coscientist[pdf]"\n'
            "or:\n"
            "    pip install pypdf"
        ) from exc


def _extract_text_from_pdf(path: str) -> str:
    """Return the full extracted text from a PDF file."""
    pypdf = _require_pypdf()
    reader = pypdf.PdfReader(path)
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _guess_title(text: str, path: str) -> str:
    """Heuristically extract a title from the first page of extracted PDF text.

    Tries the first substantial non-header line; falls back to the filename stem.
    """
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 10 and not re.match(
            r"^(abstract|introduction|keywords?|1[\s\.])\b", line, re.IGNORECASE
        ):
            return line[:200]
    # Fallback: humanise the filename
    return Path(path).stem.replace("_", " ").replace("-", " ")


def _guess_abstract(text: str) -> str:
    """Heuristically extract an abstract from PDF text.

    Looks for a section between an 'Abstract' heading and the next major
    heading; falls back to the first ~500 characters of body text.
    """
    match = re.search(
        r"(?:^|\n)\s*[Aa]bstract\s*\n(.*?)"
        r"(?=\n\s*(?:[Ii]ntroduction|1[\.\s]|[Kk]eywords?))",
        text,
        re.DOTALL,
    )
    if match:
        candidate = match.group(1).strip()
        if len(candidate) > 50:
            return candidate[:3000]

    # Fallback: skip the likely-title first lines and take early body text
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return " ".join(lines[2:10])[:500] if len(lines) > 2 else text[:500]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PdfLoader:
    """
    Load local PDF files as :class:`~open_coscientist.models.Article` objects.

    The resulting articles can be passed into
    :meth:`~open_coscientist.HypothesisGenerator.generate_hypotheses` via
    ``opts["user_inputs"]["pdf_paths"]``, causing the hypothesis generation
    pipeline to use them as its literature context instead of (or in addition
    to) MCP/PubMed results.

    Requires the ``pypdf`` library::

        pip install "open-coscientist[pdf]"

    Example::

        loader = PdfLoader()
        articles = loader.load(["paper1.pdf", "paper2.pdf"])
    """

    def load(self, pdf_paths: List[str]) -> "List[Article]":
        """
        Extract text from each PDF and return a list of
        :class:`~open_coscientist.models.Article` objects.

        All paths are validated for existence **before** any extraction begins
        (fail-fast, all-or-nothing).  If any PDF cannot be read or yields no
        extractable text the method raises immediately so the pipeline stops
        rather than proceeding with incomplete literature context.

        Args:
            pdf_paths: Paths to PDF files (absolute or relative to CWD).

        Returns:
            List of Article objects with the same order as *pdf_paths*.  Each has:

            * ``title`` – heuristically extracted (falls back to filename stem)
            * ``abstract`` – heuristically extracted Abstract section
            * ``content`` – full extracted text (used for per-paper LLM analysis)
            * ``source`` – ``"local_pdf"``
            * ``used_in_analysis`` – ``True``

        Raises:
            FileNotFoundError: If **any** path does not exist (checked upfront,
                before extraction starts).
            ValueError: If a PDF yields no extractable text (e.g. scanned /
                image-only PDF).  The message names the offending file and
                suggests OCR pre-processing.
            RuntimeError: If pypdf raises an unexpected error while reading a
                file (e.g. corrupted PDF).
            ImportError: If ``pypdf`` is not installed.
        """
        from .models import Article

        if not pdf_paths:
            return []

        # ------------------------------------------------------------------
        # Phase 1 — validate all paths exist BEFORE touching any file
        # ------------------------------------------------------------------
        missing = [p for p in pdf_paths if not Path(p).exists()]
        if missing:
            missing_list = "\n  ".join(missing)
            raise FileNotFoundError(
                f"The following PDF file(s) could not be found:\n  {missing_list}\n"
                "Fix the path(s) and try again.  The pipeline has not started."
            )

        # ------------------------------------------------------------------
        # Phase 2 — extract text from every PDF; stop on the first failure
        # ------------------------------------------------------------------
        articles: List[Article] = []

        for path in pdf_paths:
            p = Path(path)
            logger.info("Loading PDF: %s", path)

            try:
                text = _extract_text_from_pdf(str(p))
            except Exception as exc:
                logger.error("Failed to read PDF %r: %s", path, exc)
                raise RuntimeError(
                    f"Could not read PDF file {path!r}.\n"
                    f"pypdf reported: {exc}\n"
                    "The file may be corrupted or password-protected.  "
                    "The pipeline has been stopped."
                ) from exc

            if not text.strip():
                raise ValueError(
                    f"No text could be extracted from {path!r}.\n"
                    "The PDF may be image-based (scanned).  "
                    "Convert it to a text-based PDF with an OCR tool "
                    "(e.g. `ocrmypdf input.pdf output.pdf`) and try again.\n"
                    "The pipeline has been stopped."
                )

            title = _guess_title(text, str(p))
            abstract = _guess_abstract(text)

            article = Article(
                title=title,
                url=p.resolve().as_uri(),
                authors=[],
                year=None,
                venue=None,
                citations=0,
                abstract=abstract,
                content=text,
                source_id=str(p),
                source="local_pdf",
                pdf_links=[str(p)],
                used_in_analysis=True,
            )
            articles.append(article)
            logger.info("Loaded %r: %s chars extracted", title[:60], f"{len(text):,}")

        logger.info("PdfLoader: loaded %d article(s) from PDFs", len(articles))
        return articles
