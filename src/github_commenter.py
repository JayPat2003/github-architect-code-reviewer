"""
github_commenter.py — Posts the agent's review back to the PR on GitHub.

Uses the Pull Request Reviews API so violations appear as inline annotations
on the "Files changed" tab.

API reference:
    POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
"""

import requests
from src.types import PRData, ReviewResult

_GITHUB_API = "https://api.github.com"
_SEVERITY_ICON = {"error": "🚨", "warning": "⚠️", "info": "ℹ️"}


def post_review_comments(
    owner: str,
    repo: str,
    pr: PRData,
    result: ReviewResult,
    token: str,
) -> str:
    """
    Submit a GitHub PR review with inline comments for every flagged violation.

    Args:
        owner:  Repository owner.
        repo:   Repository name.
        pr:     PRData including the head commit SHA.
        result: ReviewResult produced by run_review().
        token:  GitHub token with pull_requests:write scope.

    Returns:
        URL of the submitted review on GitHub.

    Raises:
        requests.HTTPError: If the GitHub API call fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    inline_comments = []
    for c in result.comments:
        if c.line is not None:
            icon = _SEVERITY_ICON.get(c.severity, "")
            body = (
                f"{icon} **[{c.severity.upper()}]** {c.message}\n\n"
                f"**Suggested fix:** {c.suggestion}"
            )
            inline_comments.append({"path": c.file, "line": c.line, "body": body})

    general_items = [
        f"- **{c.file}** — {c.message} *(suggestion: {c.suggestion})*"
        for c in result.comments if c.line is None
    ]
    general_section = (
        "\n\n**Additional observations:**\n" + "\n".join(general_items)
    ) if general_items else ""

    verdict = "✅ **PASSED**" if result.passed else "❌ **FAILED**"
    review_body = f"## 🤖 Architecture Review — {verdict}\n\n{result.summary}{general_section}"

    payload = {
        "commit_id": pr.head_sha,
        "body": review_body,
        "event": "APPROVE" if result.passed else "REQUEST_CHANGES",
        "comments": inline_comments,
    }

    resp = requests.post(
        f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr.number}/reviews",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("html_url", "")