"""
HTML report generation for Open Coscientist results.

Converts the final state from hypothesis generation into a standalone HTML report
(no external dependencies — all CSS is inlined).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Inline CSS
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f7fa;
    color: #1a202c;
    line-height: 1.6;
}
.container { max-width: 960px; margin: 0 auto; padding: 2rem 1rem; }

/* ---- Header ---- */
header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    color: white;
    padding: 2rem 0;
    margin-bottom: 2rem;
}
header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; }
.subtitle { font-size: 0.9rem; opacity: 0.75; margin-top: 0.25rem; }
.research-goal {
    background: rgba(255,255,255,0.12);
    border-left: 4px solid rgba(255,255,255,0.5);
    padding: 0.85rem 1.25rem;
    margin-top: 1rem;
    border-radius: 0 6px 6px 0;
    font-size: 1rem;
    font-style: italic;
}

/* ---- Metrics ---- */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
}
.metric-card {
    background: white;
    border-radius: 8px;
    padding: 1.25rem 1rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    border-top: 3px solid #2d6a9f;
}
.metric-card .value { font-size: 1.9rem; font-weight: 700; color: #2d6a9f; }
.metric-card .label {
    font-size: 0.75rem; color: #718096;
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-top: 0.2rem;
}

/* ---- Section title ---- */
.section-title {
    font-size: 1.4rem; font-weight: 700; color: #1e3a5f;
    margin-bottom: 1.25rem; padding-bottom: 0.5rem;
    border-bottom: 2px solid #e2e8f0;
}

/* ---- Hypothesis card ---- */
.hypothesis-card {
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 2rem;
    overflow: hidden;
}
.hypothesis-header {
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    padding: 0.9rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
}
.rank-badge { font-size: 1.4rem; min-width: 2rem; }
.hypothesis-title { font-size: 1rem; font-weight: 600; color: #1e3a5f; flex: 1; }
.stat-badge {
    background: #e8f0fe; color: #1a56db;
    font-size: 0.78rem; padding: 0.2rem 0.55rem;
    border-radius: 20px; font-weight: 600; white-space: nowrap;
}
.method-badge {
    font-size: 0.72rem; padding: 0.2rem 0.5rem;
    border-radius: 4px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em;
}
.method-debate { background: #fdf4ff; color: #7c3aed; border: 1px solid #e9d5ff; }
.method-literature { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.method-tools { background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }

.hypothesis-body { padding: 1.25rem 1.5rem; }
.hypothesis-text {
    font-size: 0.98rem; line-height: 1.8; color: #2d3748;
    margin-bottom: 1rem; padding-bottom: 1rem;
    border-bottom: 1px dashed #e2e8f0;
}

/* ---- Collapsible details ---- */
details {
    margin-bottom: 0.6rem;
    border: 1px solid #e2e8f0;
    border-radius: 6px; overflow: hidden;
}
details[open] { border-color: #93c5fd; }
summary {
    padding: 0.65rem 1rem; cursor: pointer;
    font-weight: 600; font-size: 0.88rem; color: #2d6a9f;
    background: #f8fafc; list-style: none;
    display: flex; align-items: center; gap: 0.5rem;
    user-select: none;
}
summary::-webkit-details-marker { display: none; }
summary::before { content: '▶'; font-size: 0.65rem; transition: transform 0.15s; display: inline-block; }
details[open] summary::before { transform: rotate(90deg); }
.details-content { padding: 0.9rem 1rem; font-size: 0.93rem; line-height: 1.75; color: #374151; }

/* ---- Review scores ---- */
.scores-table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; font-size: 0.88rem; }
.scores-table th {
    text-align: left; padding: 0.35rem 0.6rem;
    color: #6b7280; border-bottom: 1px solid #e5e7eb; font-weight: 600;
}
.scores-table td { padding: 0.35rem 0.6rem; }
.score-bar-wrap { display: flex; align-items: center; gap: 0.5rem; }
.score-bar { height: 6px; border-radius: 3px; background: #e5e7eb; flex: 1; overflow: hidden; min-width: 80px; }
.score-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #2d6a9f, #22d3ee); }
.review-sep { border: none; border-top: 1px dashed #e5e7eb; margin: 1rem 0; }

/* ---- Citation links ---- */
.cite-ref {
    color: #2d6a9f; text-decoration: none;
    font-size: 0.82em; vertical-align: super;
    font-weight: 600;
}
.cite-ref:hover { text-decoration: underline; }

/* ---- Citations section ---- */
.citations-section { margin-top: 3rem; }
.citations-list { list-style: none; }
.citations-list li {
    padding: 0.7rem 1rem;
    background: white; border-radius: 6px;
    margin-bottom: 0.4rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    font-size: 0.88rem; display: flex; gap: 0.75rem;
}
.cite-id { font-weight: 700; color: #2d6a9f; min-width: 3.5rem; padding-top: 0.05rem; }
.cite-body { flex: 1; }
.cite-title { font-weight: 600; color: #1e3a5f; }
.cite-meta { color: #6b7280; font-size: 0.82rem; margin-top: 0.15rem; }
.cite-link { color: #2d6a9f; font-size: 0.82rem; margin-left: 0.5rem; }

/* ---- Footer ---- */
footer {
    margin-top: 3rem; padding: 1.5rem 0;
    border-top: 1px solid #e2e8f0;
    text-align: center; color: #9ca3af; font-size: 0.82rem;
}

@media (max-width: 640px) {
    .metrics-grid { grid-template-columns: repeat(2, 1fr); }
    .hypothesis-header { flex-direction: column; align-items: flex-start; }
}
@media print {
    body { background: white; }
    .hypothesis-card { box-shadow: none; border: 1px solid #e2e8f0; }
    details { open: true; }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _html_escape(text: str) -> str:
    """Escape HTML special chars and render newlines as <br>."""
    text = str(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", "<br>")
    return text


def _rank_badge(rank: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, f"#{rank}")


def _method_badge_html(method: Optional[str], hyp: Dict[str, Any]) -> str:
    if not method:
        return ""
    if method == "debate":
        lit = hyp.get("literature_grounding", "")
        is_debate_only = not lit or lit.startswith("No literature review available")
        label = "Debate only" if is_debate_only else "Debate + Lit"
        return f'<span class="method-badge method-debate">{label}</span>'
    if method == "literature_tools":
        return '<span class="method-badge method-tools">Lit MCP Tools</span>'
    return ""


def _resolve_citations(text: str) -> str:
    """Replace [C1], [P1], [KG1] etc. with anchor links."""

    def replace(m: re.Match) -> str:
        inner = m.group(1)  # e.g. "C1"
        anchor_id = f"cite-{inner.lower()}"
        return f'<a class="cite-ref" href="#{anchor_id}">[{inner}]</a>'

    return re.sub(r"\[([A-Z]+\d+)\]", replace, text)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_scores_table(scores: Dict[str, Any]) -> str:
    rows = ""
    for criterion, score in scores.items():
        pct = min(float(score) * 10, 100)
        rows += f"""
          <tr>
            <td>{_html_escape(str(criterion).replace("_", " ").title())}</td>
            <td>
              <div class="score-bar-wrap">
                <div class="score-bar">
                  <div class="score-bar-fill" style="width:{pct:.0f}%"></div>
                </div>
                <span>{score}</span>
              </div>
            </td>
          </tr>"""
    return f"""
        <table class="scores-table">
          <tr><th>Criterion</th><th>Score (/10)</th></tr>
          {rows}
        </table>"""


def _render_reviews(reviews: List[Dict[str, Any]]) -> str:
    parts = []
    for i, review in enumerate(reviews):
        if i > 0:
            parts.append('<hr class="review-sep">')
        if review.get("scores"):
            parts.append(_render_scores_table(review["scores"]))
        if review.get("review_summary"):
            parts.append(f"<p>{_html_escape(review['review_summary'])}</p>")
    return "\n".join(parts)


def _render_hypothesis(rank: int, hyp: Dict[str, Any]) -> str:
    score = hyp.get("score", 0)
    elo = hyp.get("elo_rating", 1200)
    win_count = hyp.get("win_count", 0)
    loss_count = hyp.get("loss_count", 0)
    total_matches = hyp.get("total_matches", 0)
    reviews = hyp.get("reviews", [])

    tournament_html = ""
    if total_matches > 0:
        tournament_html = f'<span class="stat-badge">{win_count}W–{loss_count}L</span>'

    method_html = _method_badge_html(hyp.get("generation_method"), hyp)

    header = f"""
    <div class="hypothesis-header">
      <span class="rank-badge">{_rank_badge(rank)}</span>
      <span class="hypothesis-title">Hypothesis {rank}</span>
      <span class="stat-badge">Score {score:.1f}</span>
      <span class="stat-badge">Elo {elo}</span>
      {tournament_html}
      {method_html}
    </div>"""

    body_parts: List[str] = [
        f'<div class="hypothesis-text">{_html_escape(hyp["text"])}</div>'
    ]

    if hyp.get("explanation"):
        body_parts.append(
            f"""<details>
      <summary>Explanation</summary>
      <div class="details-content">{_html_escape(hyp["explanation"])}</div>
    </details>"""
        )

    if hyp.get("literature_grounding"):
        resolved = _resolve_citations(_html_escape(hyp["literature_grounding"]))
        body_parts.append(
            f"""<details open>
      <summary>Literature Grounding</summary>
      <div class="details-content">{resolved}</div>
    </details>"""
        )

    if hyp.get("experiment"):
        body_parts.append(
            f"""<details>
      <summary>Experiment Design</summary>
      <div class="details-content">{_html_escape(hyp["experiment"])}</div>
    </details>"""
        )

    if hyp.get("novelty_validation"):
        body_parts.append(
            f"""<details>
      <summary>Novelty Validation</summary>
      <div class="details-content">{_html_escape(hyp["novelty_validation"])}</div>
    </details>"""
        )

    if reviews:
        body_parts.append(
            f"""<details>
      <summary>Peer Reviews ({len(reviews)})</summary>
      <div class="details-content">{_render_reviews(reviews)}</div>
    </details>"""
        )

    body = "\n    ".join(body_parts)

    return f"""
  <div class="hypothesis-card">
    {header}
    <div class="hypothesis-body">
      {body}
    </div>
  </div>"""


def _render_citations_section(hypotheses: List[Dict[str, Any]]) -> str:
    all_citations: Dict[str, Any] = {}
    for hyp in hypotheses:
        for key, val in (hyp.get("citation_map") or {}).items():
            if key not in all_citations:
                all_citations[key] = val

    if not all_citations:
        return ""

    items: List[str] = []
    for key in sorted(all_citations.keys()):
        cite = all_citations[key]
        anchor_id = f"cite-{key.lower()}"
        title = cite.get("title") or "Untitled"
        authors: List[str] = cite.get("authors") or []
        year = cite.get("year", "")
        venue = cite.get("venue", "")
        url = cite.get("url", "")

        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        meta_parts = [p for p in [author_str, str(year) if year else "", venue] if p]
        meta_str = " · ".join(meta_parts)
        link_html = (
            f'<a class="cite-link" href="{url}" target="_blank" rel="noopener">→ Link</a>'
            if url
            else ""
        )

        items.append(
            f"""<li id="{anchor_id}">
        <span class="cite-id">[{key}]</span>
        <span class="cite-body">
          <div class="cite-title">{_html_escape(title)}</div>
          <div class="cite-meta">{_html_escape(meta_str)}{link_html}</div>
        </span>
      </li>"""
        )

    return f"""
  <section class="citations-section">
    <h2 class="section-title">Citations</h2>
    <ul class="citations-list">
      {"".join(items)}
    </ul>
  </section>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class HtmlReporter:
    """
    Generate standalone HTML reports from Open Coscientist results.

    Example::

        reporter = HtmlReporter()
        paths = reporter.save(state, research_goal="My research question")
        print(f"Report saved to {paths['html']}")
    """

    def generate(
        self,
        state: Dict[str, Any],
        research_goal: Optional[str] = None,
    ) -> str:
        """
        Generate an HTML string from the final state dict.

        Args:
            state: The dict returned by ``HypothesisGenerator.generate_hypotheses()``
                   (or the ``last_state`` from a ``ConsoleReporter.run()`` call).
            research_goal: The original research question (displayed in the header).

        Returns:
            A complete, standalone HTML document as a string.
        """
        hypotheses = sorted(
            state.get("hypotheses", []),
            key=lambda h: h.get("elo_rating", 1200),
            reverse=True,
        )
        metrics = state.get("metrics") or {}
        run_id = state.get("run_id", "")
        execution_time = state.get("execution_time") or metrics.get("total_time")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # --- metrics grid ---
        metric_items: List[tuple] = [
            ("Hypotheses", len(hypotheses)),
            ("Reviews", metrics.get("reviews_count", "—")),
            ("Tournaments", metrics.get("tournaments_count", "—")),
            ("Evolutions", metrics.get("evolutions_count", "—")),
            ("LLM Calls", metrics.get("llm_calls", "—")),
        ]
        if execution_time is not None:
            metric_items.append(("Runtime", f"{execution_time:.0f}s"))

        metric_cards = ""
        for label, value in metric_items:
            metric_cards += f"""
      <div class="metric-card">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
      </div>"""

        # --- hypotheses ---
        hyp_html = "".join(_render_hypothesis(rank, hyp) for rank, hyp in enumerate(hypotheses, 1))

        # --- citations ---
        citations_html = _render_citations_section(hypotheses)

        # --- header extras ---
        goal_html = (
            f'<div class="research-goal">{_html_escape(research_goal)}</div>'
            if research_goal
            else ""
        )
        run_id_html = (
            f'<span style="opacity:0.6;font-size:0.82rem;margin-left:1rem;">Run: {run_id}</span>'
            if run_id
            else ""
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Open Coscientist Report</title>
  <style>{_CSS}</style>
</head>
<body>
  <header>
    <div class="container">
      <h1>Open Coscientist Report</h1>
      <div class="subtitle">{timestamp}{run_id_html}</div>
      {goal_html}
    </div>
  </header>
  <div class="container">
    <div class="metrics-grid">{metric_cards}
    </div>
    <h2 class="section-title">Research Hypotheses</h2>
    {hyp_html}
    {citations_html}
  </div>
  <footer>
    Generated by <strong>Open Coscientist</strong> &mdash; {timestamp}
  </footer>
</body>
</html>"""

    def save(
        self,
        state: Dict[str, Any],
        output_dir: str = "coscientist_reports",
        research_goal: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Save an HTML report and a JSON results file to *output_dir*.

        Args:
            state: The final state dict from ``generate_hypotheses()``.
            output_dir: Directory to write files into (created if absent).
            research_goal: The original research question.

        Returns:
            Dict with keys ``"html"`` and ``"json"`` pointing to the saved paths.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        run_id = state.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = run_id.replace("-", "")[:32]  # filesystem-friendly

        # Save JSON for future CLI regeneration
        json_path = os.path.join(output_dir, f"{stem}_results.json")
        payload = dict(state)
        if research_goal:
            payload["research_goal"] = research_goal
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)

        # Save HTML report
        html_path = os.path.join(output_dir, f"{stem}_report.html")
        html = self.generate(state, research_goal=research_goal)
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)

        return {"html": html_path, "json": json_path}


class CacheReportBuilder:
    """
    Reconstruct an HTML report directly from the LLM response JSON files in
    ``.coscientist_cache/``, without needing to re-run the pipeline.

    The builder scans every ``.json`` file in the cache directory, identifies
    each file's agent type by keywords in ``prompt_preview``, then reassembles
    a best-effort state dict that ``HtmlReporter.generate()`` can render.

    Example::

        builder = CacheReportBuilder()
        paths = builder.save_report(".coscientist_cache/")
        print(f"Report saved to {paths['html']}")
    """

    # Keyword patterns used to classify each cache file.
    # Each entry is (agent_label, list_of_substrings_checked_against_prompt_preview).
    _AGENT_PATTERNS: List[tuple] = [
        ("supervisor", ["Supervisor Agent", "domain-specific guidance"]),
        ("generation", ["Generation Agent", "novel research hypotheses", "generate hypotheses"]),
        ("review", ["Hypothesis Review Agent", "comparative peer review"]),
        ("evolution", ["Hypothesis Evolution Agent", "refine and improve"]),
        ("ranking", ["Ranking Agent", "tournament"]),
        ("meta_review", ["Meta-Review Agent", "synthesize comprehensive meta-review"]),
        ("proximity", ["Proximity Agent", "Similarity Analysis"]),
    ]

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _load_json_files(cache_dir: str) -> List[Dict[str, Any]]:
        """Load every .json file in *cache_dir* (skipping subdirectories)."""
        records = []
        for fname in os.listdir(cache_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(cache_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    records.append(json.load(fh))
            except Exception:
                pass
        return records

    @staticmethod
    def _parse_response(raw_response: Any) -> Any:
        """
        Normalise a response value — some agents wrap their JSON payload in a
        ``"text"`` key as a JSON string; others return a direct object.
        """
        if isinstance(raw_response, dict) and "text" in raw_response:
            text_val = raw_response["text"]
            if isinstance(text_val, str):
                try:
                    return json.loads(text_val)
                except Exception:
                    pass
        return raw_response

    def _classify(self, record: Dict[str, Any]) -> str:
        """Return an agent label for *record* based on prompt_preview keywords."""
        preview: str = (record.get("request") or {}).get("prompt_preview", "")
        response = record.get("response", {})

        for label, keywords in self._AGENT_PATTERNS:
            if any(kw in preview for kw in keywords):
                return label

        # Fallback: ranking responses always have hypothesis_a in the direct response
        if isinstance(response, dict) and "hypothesis_a" in response:
            return "ranking"

        return "other"

    # ---------------------------------------------------------------------------
    # Per-agent extractors
    # ---------------------------------------------------------------------------

    @staticmethod
    def _extract_generation(response: Any, pool: Dict[str, Dict[str, Any]]) -> None:
        """Add hypotheses from a GENERATION_SCHEMA response to *pool*."""
        hyps = response.get("hypotheses") if isinstance(response, dict) else None
        if not hyps:
            return
        for item in hyps:
            text = (item.get("hypothesis") or "").strip()
            if not text:
                continue
            if text not in pool:
                pool[text] = {
                    "text": text,
                    "explanation": item.get("explanation"),
                    "literature_grounding": item.get("literature_grounding"),
                    "experiment": item.get("experiment"),
                    "novelty_validation": item.get("novelty_validation"),
                    "reviews": [],
                    "evolution_history": [],
                    "win_count": 0,
                    "loss_count": 0,
                    "elo_rating": 1200,
                    "score": 0.0,
                    "citation_map": {},
                    "generation_method": None,
                }

    @staticmethod
    def _extract_evolution(response: Any, pool: Dict[str, Dict[str, Any]]) -> None:
        """Add or update a hypothesis from an EVOLUTION_SCHEMA response."""
        if not isinstance(response, dict):
            return
        text = (response.get("hypothesis") or "").strip()
        if not text:
            return
        entry = pool.setdefault(
            text,
            {
                "text": text,
                "explanation": None,
                "literature_grounding": None,
                "experiment": None,
                "novelty_validation": None,
                "reviews": [],
                "evolution_history": [],
                "win_count": 0,
                "loss_count": 0,
                "elo_rating": 1200,
                "score": 0.0,
                "citation_map": {},
                "generation_method": None,
            },
        )
        # Always update content with evolved version
        entry["explanation"] = response.get("explanation") or entry["explanation"]
        entry["experiment"] = response.get("experiment") or entry["experiment"]
        summary = response.get("refinement_summary", "")
        if summary and summary not in entry["evolution_history"]:
            entry["evolution_history"].append(summary)

    @staticmethod
    def _extract_review(response: Any, pool: Dict[str, Dict[str, Any]]) -> None:
        """Attach a REVIEW_SCHEMA review to the matching hypothesis in *pool*."""
        if not isinstance(response, dict):
            return
        text = (response.get("hypothesis_text") or "").strip()
        if not text or text not in pool:
            return
        review = {
            "review_summary": response.get("review_summary", ""),
            "scores": response.get("scores", {}),
            "safety_ethical_concerns": response.get("safety_ethical_concerns", ""),
            "detailed_feedback": response.get("detailed_feedback", {}),
            "constructive_feedback": response.get("constructive_feedback", ""),
            "overall_score": response.get("overall_score", 0.0),
        }
        pool[text]["reviews"].append(review)

    @staticmethod
    def _extract_ranking(
        response: Any,
        pool: Dict[str, Dict[str, Any]],
        matches: List[tuple],
    ) -> None:
        """Record a RANKING_SCHEMA matchup; add unseen hypotheses to *pool*."""
        if not isinstance(response, dict):
            return
        hyp_a = (response.get("hypothesis_a") or "").strip()
        hyp_b = (response.get("hypothesis_b") or "").strip()
        winner_label = response.get("winner", "")
        if not hyp_a or not hyp_b or winner_label not in ("a", "b"):
            return

        winner_text = hyp_a if winner_label == "a" else hyp_b
        loser_text = hyp_b if winner_label == "a" else hyp_a

        # Ensure both hypotheses exist in pool
        for text in (hyp_a, hyp_b):
            pool.setdefault(
                text,
                {
                    "text": text,
                    "explanation": None,
                    "literature_grounding": None,
                    "experiment": None,
                    "novelty_validation": None,
                    "reviews": [],
                    "evolution_history": [],
                    "win_count": 0,
                    "loss_count": 0,
                    "elo_rating": 1200,
                    "score": 0.0,
                    "citation_map": {},
                    "generation_method": None,
                },
            )

        matches.append((winner_text, loser_text))

    @staticmethod
    def _apply_elo(pool: Dict[str, Dict[str, Any]], matches: List[tuple]) -> None:
        """Simulate Elo ratings from the recorded tournament matchups."""
        K = 32
        for winner_text, loser_text in matches:
            winner = pool.get(winner_text)
            loser = pool.get(loser_text)
            if not winner or not loser:
                continue

            elo_w = winner["elo_rating"]
            elo_l = loser["elo_rating"]
            expected_w = 1.0 / (1.0 + 10 ** ((elo_l - elo_w) / 400.0))

            winner["elo_rating"] = round(elo_w + K * (1 - expected_w))
            loser["elo_rating"] = round(elo_l + K * (0 - (1 - expected_w)))
            winner["win_count"] += 1
            loser["loss_count"] += 1

        # Derive scores from win rates
        for entry in pool.values():
            total = entry["win_count"] + entry["loss_count"]
            entry["score"] = round((entry["win_count"] / total * 100) if total else 0.0, 2)

    @staticmethod
    def _extract_meta_review(response: Any) -> Optional[Dict[str, Any]]:
        if isinstance(response, dict) and "meta_review_summary" in response:
            return response
        return None

    @staticmethod
    def _extract_research_goal(response: Any) -> Optional[str]:
        if not isinstance(response, dict):
            return None
        # SUPERVISOR_SCHEMA: response.research_goal_analysis.goal_summary
        rga = response.get("research_goal_analysis")
        if isinstance(rga, dict):
            return rga.get("goal_summary") or rga.get("research_goal")
        return response.get("research_goal")

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def build_state(self, cache_dir: str) -> Dict[str, Any]:
        """
        Parse all ``.json`` files in *cache_dir* and return a state dict
        compatible with ``HtmlReporter.generate()``.

        Args:
            cache_dir: Path to the ``.coscientist_cache/`` directory.

        Returns:
            State dict with ``hypotheses``, ``meta_review``, ``metrics``, and
            ``research_goal`` keys (``research_goal`` is a top-level convenience
            key consumed by ``HtmlReporter.save()``).
        """
        records = self._load_json_files(cache_dir)

        pool: Dict[str, Dict[str, Any]] = {}
        matches: List[tuple] = []
        meta_review: Optional[Dict[str, Any]] = None
        research_goal: Optional[str] = None
        reviews_count = 0
        tournaments_count = 0
        evolutions_count = 0

        for record in records:
            label = self._classify(record)
            if label == "other":
                continue

            response = self._parse_response(record.get("response", {}))

            if label == "generation":
                self._extract_generation(response, pool)

            elif label == "evolution":
                evolutions_count += 1
                self._extract_evolution(response, pool)

            elif label == "review":
                reviews_count += 1
                self._extract_review(response, pool)

            elif label == "ranking":
                tournaments_count += 1
                self._extract_ranking(response, pool, matches)

            elif label == "meta_review":
                if meta_review is None:
                    meta_review = self._extract_meta_review(response)

            elif label == "supervisor":
                if research_goal is None:
                    research_goal = self._extract_research_goal(response)

        self._apply_elo(pool, matches)

        # Build final hypothesis list sorted by Elo
        hypotheses = sorted(pool.values(), key=lambda h: h["elo_rating"], reverse=True)

        # Add computed fields expected by HtmlReporter
        for h in hypotheses:
            total = h["win_count"] + h["loss_count"]
            h["total_matches"] = total
            h["win_rate"] = (h["win_count"] / total * 100) if total else 0.0

        return {
            "hypotheses": hypotheses,
            "meta_review": meta_review or {},
            "research_goal": research_goal,
            "metrics": {
                "hypothesis_count": len(hypotheses),
                "reviews_count": reviews_count,
                "tournaments_count": tournaments_count,
                "evolutions_count": evolutions_count,
                "llm_calls": len(records),
            },
        }

    def save_report(
        self,
        cache_dir: str,
        output_dir: str = "coscientist_reports",
    ) -> Dict[str, str]:
        """
        Build a state from *cache_dir* and save an HTML report + JSON snapshot.

        Args:
            cache_dir: Path to the ``.coscientist_cache/`` directory.
            output_dir: Directory to write output files into (created if absent).

        Returns:
            Dict with keys ``"html"`` and ``"json"`` pointing to the saved paths.
        """
        state = self.build_state(cache_dir)
        research_goal: Optional[str] = state.pop("research_goal", None)
        return HtmlReporter().save(state, output_dir=output_dir, research_goal=research_goal)


def main() -> None:
    """
    CLI entry point: generate an HTML report from either a saved results JSON
    file or a raw ``.coscientist_cache/`` directory.

    Usage::

        # From a saved results JSON (fast — pure read):
        coscientist-report <results.json> [output_dir]

        # From a cache directory (reconstructs from raw LLM responses):
        coscientist-report <cache_dir/> [output_dir]

    If *output_dir* is omitted:
    - For a JSON file, the report is written next to the file.
    - For a cache dir, the report is written to ``coscientist_reports/``.
    """
    if len(sys.argv) < 2:
        print("Usage: coscientist-report <results.json | cache_dir/> [output_dir]")
        sys.exit(1)

    source = sys.argv[1]

    if os.path.isdir(source):
        # Reconstruct from raw LLM cache files
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "coscientist_reports"
        print(f"Scanning cache directory: {source}")
        paths = CacheReportBuilder().save_report(source, output_dir=output_dir)
        print(f"Report saved → {paths['html']}")

    elif os.path.isfile(source) and source.endswith(".json"):
        # Regenerate from a previously saved results JSON
        output_dir = sys.argv[2] if len(sys.argv) > 2 else (os.path.dirname(source) or ".")
        with open(source, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        research_goal: Optional[str] = state.pop("research_goal", None)
        paths = HtmlReporter().save(state, output_dir=output_dir, research_goal=research_goal)
        print(f"Report saved → {paths['html']}")

    else:
        print(f"Error: '{source}' is not a directory or a .json file.")
        sys.exit(1)
