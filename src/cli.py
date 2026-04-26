"""
cli.py — Command-line entry point for the Copilot Code Reviewer.
"""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


@click.group()
@click.version_option("2.0.0")
def main() -> None:
    """AI-powered agentic code review against architecture principles."""


@main.command()
@click.option("--owner",         required=True,  help="GitHub repository owner")
@click.option("--repo",          required=True,  help="GitHub repository name")
@click.option("--pr",            "pr_number", required=True, type=int, help="Pull request number")
@click.option("--doc",           "doc_path",  required=True, help="Path or URL to the architecture document")
@click.option("--output",        "output_dir",
              default=os.getenv("REPORT_OUTPUT_DIR", "./reports"),
              show_default=True, help="Directory for the generated report")
@click.option("--post-comments", "post_comments", is_flag=True, default=False,
              help="Post inline review comments back to the PR on GitHub")
def review(owner: str, repo: str, pr_number: int, doc_path: str, output_dir: str, post_comments: bool) -> None:
    """Review a pull request against an architecture document (agentic mode)."""

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[bold red]Error:[/] GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    console.print(f"[bold cyan]Reviewing PR #{pr_number}[/] in [green]{owner}/{repo}[/]")
    console.print(f"Architecture doc: [yellow]{doc_path}[/]")

    from src.github_client import fetch_pull_request
    from src.doc_loader import load_document
    from src.reviewer import run_review
    from src.reporter import save_report

    with console.status("Fetching pull request…"):
        pr = fetch_pull_request(owner, repo, pr_number, github_token)

    with console.status("Loading architecture document…"):
        arch_doc = load_document(doc_path)

    with console.status("[bold yellow]Agentic review in progress (tool-calling loop)…"):
        result = run_review(pr, arch_doc)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    report_path = save_report(result, output_dir)

    if post_comments:
        from src.github_commenter import post_review_comments
        with console.status("Posting inline comments to PR…"):
            review_url = post_review_comments(owner, repo, pr, result, github_token)
        console.print(f"Review posted: [cyan]{review_url}[/]")

    if result.comments:
        console.print(f"\n[bold]Violations found ({len(result.comments)}):[/]")
        for c in result.comments:
            colour = {"error": "red", "warning": "yellow", "info": "blue"}.get(c.severity, "white")
            loc = f"{c.file}:{c.line}" if c.line else c.file
            console.print(f"  [{colour}][{c.severity.upper()}][/] {loc} — {c.message}")

    status = "[bold green]PASSED" if result.passed else "[bold red]FAILED"
    console.print(f"\nReview {status}[/]")
    console.print(f"Report saved to [cyan]{report_path}[/]")
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()