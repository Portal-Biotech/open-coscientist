# Open Coscientist

**AI-powered research hypothesis generation using LangGraph**

Open Coscientist is an open **adaptation based on Google Research's [AI Co-Scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/)** research paper. This project provides an implementation that generates, reviews, ranks, and evolves research hypotheses using the multi-agent architecture described. It orchestrates 8-10 specialized AI agents through a LangGraph workflow and aims to produce novel hypotheses grounded in scientific literature.

## Demo

<p align="center">
  <a href="https://youtu.be/LyOvigZ59yE?si=JiIJnXajgLhTb1yj">
    <img src="https://github.com/jataware/open-coscientist/blob/main/assets/Open_Coscientist_Demo.gif?raw=true" alt="Open Coscientist Demo">
  </a>
</p>

<p align="center">
  <em>
    In this demo we use Open Coscientist to generate hypotheses for novel approaches to early detection of Alzheimer's disease.
    Click to watch the full demo on YouTube.
  </em>
</p>

### Standalone operation

The engine works with any LLM and can run without external data sources.

For high-quality hypothesis generation, the system provides an MCP server integration to perform literature-aware reasoning over published research. See [MCP Integration](https://github.com/jataware/open-coscientist/blob/main/docs/mcp-integration.md) for setup and configuration details, and to run the basic reference MCP server.

---

## Quick Start

### Installation

```bash
pip install open-coscientist
```

To use **PDF paper injection** (grounding hypotheses in your own papers):

```bash
pip install "open-coscientist[pdf]"
```

Set your API key (any LiteLLM-supported provider):
```bash
export ANTHROPIC_API_KEY="your-key-here"
# or: export OPENAI_API_KEY="your-key-here"
# or: export GEMINI_API_KEY="your-key-here"
```

For development, see [CONTRIBUTING.md](https://github.com/jataware/open-coscientist/blob/main/CONTRIBUTING.md).

> **Note**: for the any literature review to run, you must provide an MCP server with literature review tools/capabilities. You can use the provided reference implementation [MCP Server](https://github.com/jataware/open-coscientist/tree/main/mcp_server). Otherwise, no published research will be used — unless you supply your own PDFs (see [PDF Paper Mode](#pdf-paper-mode)).

**Model Support**: Uses [LiteLLM](https://docs.litellm.ai/docs/providers) for 100+ LLM providers (OpenAI, Anthropic, Google, Azure, AWS Bedrock, Cohere, etc.). May need to tweak some constants.py token usage and other params, such as initial hypotheses count, in order to work with less powerful models.

### Basic Python usage

```python
import asyncio
from open_coscientist import HypothesisGenerator

async def main():
    generator = HypothesisGenerator(
        model_name="anthropic/claude-sonnet-4-5",  # default
        max_iterations=1,
        initial_hypotheses_count=5,
        evolution_max_count=3
    )

    async for node_name, state in generator.generate_hypotheses(
        research_goal="Your research question",
        stream=True
    ):
        print(f"Completed: {node_name}")
        if node_name == "generate":
            print(f"Generated {len(state['hypotheses'])} hypotheses")

if __name__ == "__main__":
    asyncio.run(main())
```

See [`examples/run.py`](https://github.com/jataware/open-coscientist/blob/main/examples/run.py) for a full example with a built-in Console Reporter.

---

## CLI Reference

Two commands are installed with the package:

| Command | Purpose |
|---------|---------|
| `coscientist-run` | Run the full hypothesis generation pipeline |
| `coscientist-report` | Generate or regenerate an HTML report from saved results |

### `coscientist-run`

```
coscientist-run [options]
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--research-goal GOAL` | `-g` | *(prompted)* | Research question. Omit to be prompted interactively. |
| `--pdf FILE [FILE ...]` | | | One or more local PDF files to use as literature context. Bypasses MCP/PubMed by default. |
| `--supplement` | | `False` | When used with `--pdf`, also run MCP/PubMed and merge results with your papers. |
| `--model NAME` | | `anthropic/claude-sonnet-4-5` | Any [LiteLLM](https://docs.litellm.ai/docs/providers) model string. |
| `--iterations N` | `-i` | `1` | Number of review + evolve iterations. |
| `--hypotheses N` | `-n` | `5` | Number of initial hypotheses to generate. |
| `--evolution N` | `-e` | `3` | Max hypotheses to evolve per iteration. |
| `--report-dir DIR` | | `coscientist_reports` | Directory to save HTML report and JSON results. Pass `none` to disable. |

**Examples:**

```bash
# Standard run — MCP/PubMed literature review (requires MCP server)
coscientist-run --research-goal "Novel KRAS inhibition mechanisms"

# PDF-only mode — anchor hypotheses on your own papers
coscientist-run --pdf paper1.pdf paper2.pdf \
                --research-goal "Novel KRAS inhibition mechanisms"

# PDF + PubMed supplement — your papers plus a PubMed search
coscientist-run --pdf paper1.pdf paper2.pdf --supplement \
                --research-goal "Novel KRAS inhibition mechanisms"

# Interactive prompt for research goal
coscientist-run --pdf paper1.pdf paper2.pdf

# Custom model, more iterations, no report saved
coscientist-run -g "..." --model anthropic/claude-opus-4-5 \
                -i 3 -n 10 -e 5 --report-dir none
```

### `coscientist-report`

Generates (or regenerates) an HTML report without re-running the pipeline.

```bash
# From a saved results JSON (produced automatically after each run)
coscientist-report coscientist_reports/<run_id>_results.json

# From the raw LLM cache directory
coscientist-report .coscientist_cache/

# Specify a custom output directory
coscientist-report .coscientist_cache/ --output-dir my_reports/
```

The command auto-detects the input type — a `.json` file uses the saved results directly; a directory reads and reconstructs from the LLM response cache files.

---

## PDF Paper Mode

You can anchor hypothesis generation in your own papers instead of (or alongside) MCP/PubMed. This is useful when:

- You have a curated set of papers directly relevant to your research goal.
- You are working offline or without an MCP server.
- You want tighter control over the literature context.

### Install the PDF extra

```bash
pip install "open-coscientist[pdf]"
# or with uv:
uv pip install -e ".[pdf]"
```

### CLI

```bash
# Use only your papers
coscientist-run --pdf paper1.pdf paper2.pdf \
                --research-goal "Your research goal"

# Your papers + PubMed search
coscientist-run --pdf paper1.pdf paper2.pdf --supplement \
                --research-goal "Your research goal"
```

### Python API

```python
from open_coscientist import HypothesisGenerator

generator = HypothesisGenerator(model_name="anthropic/claude-sonnet-4-5")

result = await generator.generate_hypotheses(
    research_goal="Novel KRAS inhibition mechanisms",
    opts={
        "user_inputs": {
            "pdf_paths": [
                "papers/kras_targeting_2023.pdf",
                "papers/ras_gdp_switching.pdf",
            ],
            "supplement_with_mcp": False,  # True to also search PubMed
        }
    },
)
```

### How it works

PDF text is extracted with [`pypdf`](https://pypdf.readthedocs.io/) and the same multi-phase analysis pipeline used for MCP-sourced papers runs on your PDFs:

1. **Phase 3 — per-paper LLM analysis**: each paper is analysed for gaps and research opportunities relative to your research goal.
2. **Phase 4 — synthesis**: findings are synthesised into `articles_with_reasoning`, the same structured context fed to every hypothesis generation prompt.
3. **Citation resolution**: citations in generated hypotheses (e.g. `[C1]`, `[C2]`) resolve to your local papers in the final output and HTML report.

When `supplement_with_mcp=True`, MCP/PubMed results are fetched first and your PDFs are merged in before the analysis phase, so all papers are treated equally.

### `PdfLoader` API

You can also use `PdfLoader` directly if you need the `Article` objects for custom workflows:

```python
from open_coscientist import PdfLoader

articles = PdfLoader().load([
    "papers/kras_targeting_2023.pdf",
    "papers/ras_review.pdf",
])

for article in articles:
    print(article.title)
    print(f"  {len(article.content):,} chars extracted")
```

Each `Article` has: `title`, `abstract`, `content` (full text), `url` (file URI), `source="local_pdf"`, `used_in_analysis=True`.

---

## HTML Reports

After every run, an HTML report and a JSON results file are automatically saved to `coscientist_reports/` (configurable). The report is a standalone file with no external dependencies — open it in any browser.

### Report contents

- **Header**: research goal, run ID, timestamp
- **Metrics bar**: execution time, hypothesis count, reviews, tournaments, evolutions
- **Hypotheses** ranked by Elo rating, each with:
  - Score, Elo, tournament record, generation method badge
  - Full hypothesis text
  - Collapsible: Explanation, Literature Grounding (linked citations), Experiment Design, Reviews (score table + summary)
- **Citations section**: all resolved `[C*]` references with titles, authors, years, and links

### Auto-save behaviour

`ConsoleReporter` saves the report automatically at the end of every run. Control it via the `save_report` parameter:

```python
from open_coscientist.console import ConsoleReporter

# Default: save to coscientist_reports/
reporter = ConsoleReporter()

# Custom directory
reporter = ConsoleReporter(save_report="my_reports/")

# Disable auto-save
reporter = ConsoleReporter(save_report=False)
```

Two files are written per run:
- `{run_id}_report.html` — the human-readable report
- `{run_id}_results.json` — raw results for later re-processing

### Regenerating a report

```bash
# From saved JSON (fastest)
coscientist-report coscientist_reports/<run_id>_results.json

# From LLM cache (reconstructs hypotheses from raw cache files)
coscientist-report .coscientist_cache/
```

### Python API

```python
from open_coscientist import HtmlReporter, CacheReportBuilder

# From a final state dict (e.g. returned by generate_hypotheses)
paths = HtmlReporter().save(state, output_dir="my_reports/", research_goal="...")
print(paths["html"])   # path to the HTML file
print(paths["json"])   # path to the JSON file

# From the LLM cache directory
paths = CacheReportBuilder().save_report(".coscientist_cache/", output_dir="my_reports/")
```

---

## Features

- **Multi-agent workflow**: Supervisor, Generator, Reviewer, Ranker, Tournament Judge, Meta-Reviewer, Evolution, Proximity Deduplication
- **Rich hypothesis output**: Each hypothesis includes `text`, `explanation` (layman summary), `literature_grounding` with structured `[C*]` citations, and `experiment` (suggested validation design)
- **Literature review integration**: Optional MCP server provides access to real published research; structured citations resolve to full source metadata
- **PDF paper mode**: Ground hypotheses in your own local PDF papers instead of (or alongside) MCP/PubMed — no MCP server required
- **HTML report generation**: Auto-saved after every run; regeneratable from saved JSON or raw LLM cache; standalone file, no external dependencies
- **CLI**: `coscientist-run` for the full pipeline, `coscientist-report` for report generation and regeneration
- **Domain-agnostic customization**: YAML-based configuration to bring your own MCP servers, literature sources, and domain-specific prompt guidance — no code changes needed (see [Domain Customization](https://github.com/jataware/open-coscientist/blob/main/docs/domain-customization.md))
- **Real-time streaming**: Stream results as they're generated
- **Intelligent caching**: Faster development iteration with two-level LLM response + node output caching
- **Elo-based tournament**: Pairwise hypothesis comparison with Elo ratings
- **Iterative refinement**: Evolves top hypotheses while preserving diversity
- **Post-generation enrichments**: Attach domain-specific data (e.g., related CVEs, knowledge graph statements) to each hypothesis via configurable tool calls

The workflow automatically detects MCP availability and adjusts accordingly.
Functional reference MCP server included in `mcp_server/` directory.

---

## Documentation

- **[Architecture](https://github.com/jataware/open-coscientist/blob/main/docs/architecture.md)** - Workflow diagram, node descriptions, state management
- **[MCP Integration](https://github.com/jataware/open-coscientist/blob/main/docs/mcp-integration.md)** - Literature review setup and configuration
- **[Generation Modes](https://github.com/jataware/open-coscientist/blob/main/docs/generation-modes.md)** - Three generate node modes explained, and parameters to enable them
- **[Configuration](https://github.com/jataware/open-coscientist/blob/main/docs/configuration.md)** - All parameters, caching, performance tuning
- **[Domain Customization](https://github.com/jataware/open-coscientist/blob/main/docs/domain-customization.md)** - Adapting to new domains (cybersecurity, bioinformatics, etc.) via YAML config
- **[Literature Review Tools Configuration](https://github.com/jataware/open-coscientist/blob/main/docs/literature_review_tools_configuration.md)** - YAML schema reference for custom MCP servers and multi-source literature review
- **[Logging](https://github.com/jataware/open-coscientist/blob/main/docs/logging.md)** - File logging, rotating logs, log levels
- **[Development](https://github.com/jataware/open-coscientist/blob/main/docs/development.md)** - Contributing, node structure, testing

### Node Descriptions

| Node | Purpose | Key Operations |
|------|---------|----------------|
| **Supervisor** | Research planning | Analyzes research goal, identifies key areas, creates workflow strategy |
| **Literature Review** *(Recommended)* | Academic literature search | Queries databases (PubMed, Google Scholar), retrieves and analyzes real published papers (requires MCP server or user-supplied PDFs; without either, uses only LLM's latent knowledge) |
| **Generate** | Hypothesis creation | Generates N initial hypotheses using LLM with high temperature for diversity |
| **Reflection** *(Recommended)* | Literature comparison | Analyzes hypotheses against literature review findings, identifies novel contributions and validates against real research (requires literature review) |
| **Review** | Adaptive evaluation | Reviews hypotheses across 6 criteria using adaptive strategy (comparative batch for ≤5, parallel for >5) |
| **Rank** | Holistic ranking | LLM ranks all hypotheses considering composite scores and review feedback |
| **Tournament** | Pairwise comparison | Runs Elo tournament with random pairwise matchups, updates ratings |
| **Meta-Review** | Insight synthesis | Analyzes all reviews to identify common strengths, weaknesses, and strategic directions |
| **Evolve** | Hypothesis refinement | Refines top-k hypotheses with context awareness to preserve diversity |
| **Proximity** | Deduplication | Clusters similar hypotheses and removes high-similarity duplicates |

---

## Literature Review and Domain Customization

The bundled MCP server provides a PubMed reference implementation. The system is domain-agnostic: a YAML configuration file controls which MCP servers, literature sources, and prompt guidance are used — no code changes needed. Example configurations are included for biomedical (INDRA + PubMed), cybersecurity (arXiv + Google Scholar + NVD), and multi-source academic research.

See [MCP Integration](https://github.com/jataware/open-coscientist/blob/main/docs/mcp-integration.md) to set up literature review, and [Domain Customization](https://github.com/jataware/open-coscientist/blob/main/docs/domain-customization.md) to adapt to your research area.

---

## Attribution

Open Coscientist is a source-available implementation inspired by Google Research's AI Co-Scientist. While Google's original system is closed-source, this project adapts their multi-agent hypothesis generation architecture from their published research paper.

**Reference:**
- **Blog**: [Accelerating scientific breakthroughs with an AI Co-Scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/)
- **Paper**: [Towards an AI co-scientist](https://arxiv.org/abs/2502.18864)

This version provides a LangGraph-based implementation. It includes some optimizations for parallel execution, streaming support, and caching.

## Citation

If you use this work, please cite both this implementation and the original Google Research paper:

```bibtex
@article{coscientist2025,
  title={Towards an AI co-scientist},
  author={Google Research Team},
  journal={arXiv preprint arXiv:2502.18864},
  year={2025},
  url={https://arxiv.org/abs/2502.18864}
}
```
