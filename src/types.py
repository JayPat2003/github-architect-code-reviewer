"""
types.py — Shared data models for the entire application.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Config:
    github_token: str
    copilot_api_base_url: str = "https://models.inference.ai.azure.com"
    copilot_model: str = "gpt-4o"
    report_output_dir: str = "./reports"


@dataclass
class PRFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str = ""


@dataclass
class PRData:
    owner: str
    repo: str
    number: int
    title: str
    body: Optional[str]
    head_sha: str
    files: List[PRFile] = field(default_factory=list)


@dataclass
class ArchitectureDoc:
    source: str
    content: str
    doc_type: str


@dataclass
class ReviewComment:
    file: str
    severity: str          # "error" | "warning" | "info"
    message: str
    suggestion: str
    line: Optional[int] = None


@dataclass
class ReviewResult:
    passed: bool
    summary: str
    comments: List[ReviewComment] = field(default_factory=list)
    files_reviewed: List[dict] = field(default_factory=list)