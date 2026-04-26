"""
reporter.py — Persists the ReviewResult to a timestamped JSON file.
"""

import json
import os
from dataclasses import asdict
from datetime import datetime

from src.types import ReviewResult


def save_report(result: ReviewResult, output_dir: str) -> str:
    """
    Serialise a ReviewResult to a JSON file.

    Args:
        result:     The completed ReviewResult from run_review().
        output_dir: Directory where the file will be written.

    Returns:
        Absolute path to the written report file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"review__{timestamp}.json"
    path = os.path.join(output_dir, filename)

    payload = {
        "reviewed_at": timestamp,
        "passed": result.passed,
        "summary": result.summary,
        "comments": [
            {
                "file": c.file,
                "line": c.line,
                "severity": c.severity,
                "message": c.message,
                "suggestion": c.suggestion,
            }
            for c in result.comments
        ],
        "files_reviewed": result.files_reviewed,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return os.path.abspath(path)