
"""
reporter.py — Review result persistence layer.

Purpose:
    Serialises a ReviewResult into a human-readable JSON file and writes it
    to the configured output directory. The filename encodes the repo, PR
    number, and a timestamp so multiple runs never overwrite each other.

How it fits in the pipeline:
    cli.py  ──calls──>  save_report(result, output_dir)  ──returns──>  report_path (str)

Output format:
    reports/
    └── {owner}__{repo}__pr{number}__{YYYYMMDD_HHMMSS}.json
"""

import json
from datetime import datetime
from pathlib import Path

from src.types import ReviewResult


def save_report(result: ReviewResult, output_dir: str) -> str:
    """
    Serialise ReviewResult to a timestamped JSON file.

    Steps:
        1. Build a filename from owner, repo, PR number, and current timestamp.
        2. Serialise the ReviewResult (and nested objects) to a dict.
        3. Write the JSON file with 2-space indentation for readability.
        4. Return the full path of the written file.

    Args:
        result    : The ReviewResult returned by reviewer.py.
        output_dir: Directory path where the report file will be written.
                    The directory must already exist (cli.py creates it).

    Returns:
        Absolute path string of the saved report file.

    Example output file:
        reports/octocat__hello-world__pr42__20240101_120000.json
    """
    pr = result.pr

    # 1. Build filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{pr.owner}__{pr.repo}__pr{pr.number}__{timestamp}.json"
    report_path = Path(output_dir) / filename

    # 2. Serialise to a plain dict
    payload = {
        "meta": {
            "owner":     pr.owner,
            "repo":      pr.repo,
            "pr_number": pr.number,
            "pr_title":  pr.title,
            "reviewed_at": timestamp,
        },
        "passed":   result.passed,
        "summary":  result.summary,
        "comments": [
            {
                "file":       c["file"],
                "line":       c["line"],
                "severity":   c["severity"],
                "message":    c["message"],
                "suggestion": c["suggestion"],
            }
            for c in result.comments
        ],
        "files_reviewed": [
            {
                "filename":  f["filename"],
                "status":    f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
            }
            for f in pr.files
        ],
    }

    # 3. Write JSON
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Return path as string for cli.py to display
    return str(report_path)