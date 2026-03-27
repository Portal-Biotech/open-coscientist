"""
Command-line interface for Open Coscientist.

Installed as ``coscientist-run`` after ``pip install open-coscientist``.

Usage examples::

    # Standard run (MCP/PubMed literature review)
    coscientist-run --research-goal "Novel KRAS inhibition mechanisms"

    # PDF-only mode — anchor hypotheses on your own papers
    coscientist-run --pdf paper1.pdf paper2.pdf \\
                    --research-goal "Novel KRAS inhibition mechanisms"

    # PDF + MCP supplement — your papers + PubMed search
    coscientist-run --pdf paper1.pdf paper2.pdf --supplement \\
                    --research-goal "Novel KRAS inhibition mechanisms"

    # Full options
    coscientist-run --pdf paper1.pdf \\
                    --research-goal "..." \\
                    --model anthropic/claude-sonnet-4-5 \\
                    --iterations 2 \\
                    --hypotheses 7 \\
                    --evolution 4 \\
                    --report-dir my_reports
"""

from __future__ import annotations

import argparse
import sys

from .constants import (
    DEFAULT_EVOLUTION_MAX_COUNT,
    DEFAULT_INITIAL_HYPOTHESES_COUNT,
    DEFAULT_MAX_ITERATIONS,
)

DEFAULT_MODEL = "anthropic/claude-sonnet-4-5"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coscientist-run",
        description=(
            "Open Coscientist — multi-agent research hypothesis generation.\n\n"
            "Run without --pdf to use MCP/PubMed for literature review.\n"
            "Run with --pdf to ground hypotheses in your own papers."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Core inputs
    parser.add_argument(
        "-g", "--research-goal",
        metavar="GOAL",
        default=None,
        help="Research question to generate hypotheses for. "
             "If omitted you will be prompted interactively.",
    )
    parser.add_argument(
        "--pdf",
        dest="pdf_paths",
        metavar="FILE",
        nargs="+",
        default=None,
        help="One or more local PDF files to use as the literature context. "
             "Bypasses MCP/PubMed by default; combine with --supplement to "
             "also search PubMed.",
    )
    parser.add_argument(
        "--supplement",
        action="store_true",
        default=False,
        help="When used with --pdf, also run an MCP/PubMed search and merge "
             "those results with your supplied papers.",
    )

    # Model / pipeline tuning
    parser.add_argument(
        "--model",
        metavar="NAME",
        default=DEFAULT_MODEL,
        help=f"LiteLLM model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "-i", "--iterations",
        metavar="N",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Number of review+evolve iterations (default: {DEFAULT_MAX_ITERATIONS}).",
    )
    parser.add_argument(
        "-n", "--hypotheses",
        metavar="N",
        type=int,
        default=DEFAULT_INITIAL_HYPOTHESES_COUNT,
        help=f"Number of initial hypotheses to generate "
             f"(default: {DEFAULT_INITIAL_HYPOTHESES_COUNT}).",
    )
    parser.add_argument(
        "-e", "--evolution",
        metavar="N",
        type=int,
        default=DEFAULT_EVOLUTION_MAX_COUNT,
        help=f"Max hypotheses to evolve per iteration "
             f"(default: {DEFAULT_EVOLUTION_MAX_COUNT}).",
    )

    # Output
    parser.add_argument(
        "--report-dir",
        metavar="DIR",
        default="coscientist_reports",
        help="Directory to save the HTML report and JSON results "
             "(default: coscientist_reports). Pass 'none' to disable.",
    )

    return parser


async def _run(args: argparse.Namespace) -> None:
    from rich.console import Console
    from rich.panel import Panel

    from .console import ConsoleReporter, default_progress_callback, run_console
    from .generator import HypothesisGenerator

    console = Console()

    # Interactive research-goal prompt if not supplied
    research_goal = args.research_goal
    if not research_goal:
        console.print()
        console.print(
            Panel(
                "[bold]Enter your research goal[/bold]\n\n"
                "[dim]Example:[/dim] Develop novel approaches for early detection "
                "of Alzheimer's disease using non-invasive biomarkers",
                title="[cyan]Research Goal[/cyan]",
                border_style="cyan",
            )
        )
        research_goal = console.input("\n[bold cyan]Research goal:[/bold cyan] ").strip()
        if not research_goal:
            console.print("[bold red]Error:[/bold red] Research goal cannot be empty.")
            sys.exit(1)

    # Build opts
    opts: dict = {}
    if args.pdf_paths:
        opts["user_inputs"] = {
            "pdf_paths": args.pdf_paths,
            "supplement_with_mcp": args.supplement,
        }
    else:
        # Standard MCP mode — enable literature review and tool calling
        opts["enable_literature_review_node"] = True
        opts["enable_tool_calling_generation"] = True

    # Report dir
    save_report: bool | str = (
        False if args.report_dir.lower() == "none" else args.report_dir
    )

    generator = HypothesisGenerator(
        model_name=args.model,
        max_iterations=args.iterations,
        initial_hypotheses_count=args.hypotheses,
        evolution_max_count=args.evolution,
    )

    reporter = ConsoleReporter(save_report=save_report)

    await reporter.run(
        event_stream=generator.generate_hypotheses(
            research_goal=research_goal,
            progress_callback=default_progress_callback,
            opts=opts,
            stream=True,
        ),
        research_goal=research_goal,
    )


def main() -> None:
    """Entry point for the ``coscientist-run`` CLI command."""
    from .console import run_console

    parser = _build_parser()
    args = parser.parse_args()

    async def _main() -> None:
        await _run(args)

    run_console(_main())
