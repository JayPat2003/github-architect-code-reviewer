"""
cli.py — Command-line entry point for the Copilot Code Reviewer.

Purpose:
    Wires together every module in the pipeline behind a user-friendly CLI
    built with Click. Reads secrets from a .env file (or real environment
    variables), orchestrates the four pipeline stages, and exits with code 0
    (pass) or 1 (fail) so it can be embedded in CI workflows.

Dependencies:
    pip install click python-dotenv rich

How to run:
    # 1. Create a .env file with your token:
    #       GITHUB_TOKEN=ghp_...
    #
    # 2. Basic usage:
    #       python -m src.cli review \
    #           --owner  <github-owner> \
    #           --repo   <repo-name>   \
    #           --pr     <pr-number>   \
    #           --doc    path/to/architecture.pdf
    #
    # 3. Override the output directory:
    #       python -m src.cli review ... --output ./my-reports
    #
    # 4. Show help:
    #       python -m src.cli --help
    #       python -m src.cli review --help

Pipeline triggered by this file:
    fetch_pull_request()  →  load_document()  →  run_review()  →  save_report()
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

# Load .env into os.environ before anything else reads env vars
load_dotenv()
console = Console()


@click.group()
@click.version_option("1.0.0")
def main() -> None:
    """AI-powered code review against architecture principles using GitHub Copilot."""


@main.command()
@click.option("--owner",     required=True,                                      help="GitHub repository owner")
@click.option("--repo",      required=True,                                      help="GitHub repository name")
@click.option("--pr",        "pr_number", required=True, type=int,               help="Pull request number")
@click.option("--doc",       "doc_path",  required=True,                         help="Path or URL to the architecture document (PDF, URL, or text file)")
@click.option("--output",    "output_dir",
              default=os.getenv("REPORT_OUTPUT_DIR", "./reports"),
              show_default=True,                                                  help="Directory for the generated report")
def review(owner: str, repo: str, pr_number: int, doc_path: str, output_dir: str) -> None:
    """
    Review a pull request against an architecture document.

    Steps performed:
        1. Validate that GITHUB_TOKEN is present in the environment.
        2. Fetch the PR diff from GitHub via github_client.py.
        3. Load and parse the architecture document via doc_loader.py.
        4. Send the diff + document to the Copilot API via reviewer.py.
        5. Persist the structured report to disk via reporter.py.
        6. Exit 0 if no errors were found, exit 1 otherwise (CI-friendly).

    Args (Click options):
        owner      : GitHub org or user who owns the repository.
        repo       : Repository name.
        pr_number  : PR number to review (--pr flag).
        doc_path   : Local file path or HTTPS URL of the architecture doc.
        output_dir : Directory where the report file will be written.
    """
    # ── 1. Guard: token must exist before any network call ────────────────────
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[bold red]Error:[/] GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    console.print(f"[bold cyan]Reviewing PR #{pr_number}[/] in [green]{owner}/{repo}[/]")
    console.print(f"Architecture doc: [yellow]{doc_path}[/]")

    # Lazy imports keep CLI startup fast (heavy deps load only when 'review' runs)
    from src.github_client import fetch_pull_request
    from src.doc_loader    import load_document
    from src.reviewer      import run_review
    from src.reporter      import save_report

    # ── 2. Fetch PR ───────────────────────────────────────────────────────────
    with console.status("Fetching pull request…"):
        pr = fetch_pull_request(owner, repo, pr_number, github_token)

    # ── 3. Load architecture document ─────────────────────────────────────────
    with console.status("Loading architecture document…"):
        arch_doc = load_document(doc_path)

    # ── 4. Run Copilot review ─────────────────────────────────────────────────
    with console.status("Running Copilot review…"):
        result = run_review(pr, arch_doc)

    # ── 5. Save report ────────────────────────────────────────────────────────
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    report_path = save_report(result, output_dir)

    # ── 6. Print outcome and exit with appropriate code ───────────────────────
    status = "[bold green]PASSED" if result.passed else "[bold red]FAILED"
    console.print(f"\nReview {status}[/]")
    console.print(f"Report saved to [cyan]{report_path}[/]")
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    # Allows running directly:  python src/cli.py review ...
    main()
