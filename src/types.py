"""
types.py — Shared data models for the entire application.

Purpose:
    Centralises all dataclasses and TypedDicts so every module imports
    from one place, preventing circular imports and duplication.

No runtime logic lives here — it is a pure type/schema definition file.
Import order in the pipeline:
    This file is always the FIRST to be imported by every other module.
    Load order: types.py → github_client.py → doc_loader.py
                        → reviewer.py → reporter.py → cli.py
"""

from __future__ import annotations  # enables forward references for all annotations

from dataclasses import dataclass, field
from typing import List, Optional, TypedDict


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class Config:
    """
    Application-wide configuration.
    Fields:
        github_token        : PAT for GitHub API auth.
        copilot_api_base_url: Base URL for Copilot chat completions API.
        copilot_model       : Model identifier for every Copilot API request.
        report_output_dir   : Where generated reports are written.
    """
    github_token: str
    copilot_api_base_url: str = "https://api.githubcopilot.com"
    copilot_model: str = "gpt-4o"
    report_output_dir: str = "./reports"


# ── GitHub / PR types ─────────────────────────────────────────────────────────

class PRFile(TypedDict):
    """
    Single file changed in a Pull Request.
    Fields:
        filename  : Relative path inside the repository.
        status    : 'added' | 'modified' | 'removed' | 'renamed'.
        additions : Lines added.
        deletions : Lines removed.
        patch     : Unified-diff string (None for binary files).
    """
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str]


@dataclass
class PullRequest:
    """
    Aggregated Pull Request data fetched from GitHub.
    Fields:
        owner  : GitHub org or user (e.g. 'octocat').
        repo   : Repository name (e.g. 'hello-world').
        number : PR number.
        title  : PR title string.
        body   : PR description (None if blank).
        files  : List of PRFile dicts for every changed file.
    """
    owner: str
    repo: str
    number: int
    title: str
    body: Optional[str]
    files: List[PRFile] = field(default_factory=list)


# ── Architecture document ─────────────────────────────────────────────────────

@dataclass
class ArchitectureDoc:
    """
    Parsed architecture document used as the review baseline.
    Fields:
        source  : Original path or URL.
        content : Full extracted plain text.
        doc_type: 'pdf' | 'url' | 'text'.
    """
    source: str
    content: str
    doc_type: str


# ── Review result ─────────────────────────────────────────────────────────────

class ReviewComment(TypedDict):
    """
    Single actionable comment from the Copilot review.
    Fields:
        file      : Relative path of the file.
        line      : Line number (None if not line-specific).
        severity  : 'error' | 'warning' | 'info'.
        message   : Human-readable explanation.
        suggestion: Optional recommended fix.
    """
    file: str
    line: Optional[int]
    severity: str
    message: str
    suggestion: Optional[str]


@dataclass
class ReviewResult:
    """
    Complete output of one review run.
    Fields:
        pr           : The PullRequest reviewed.
        comments     : All ReviewComments raised.
        summary      : High-level summary paragraph.
        passed       : False if any 'error' severity comment exists.
        compliance_docs: Compliance documents used in this review.
    """
    pr: PullRequest
    comments: List[ReviewComment] = field(default_factory=list)
    summary: str = ""
    passed: bool = True
    compliance_docs: List[ArchitectureDoc] = field(default_factory=list)
