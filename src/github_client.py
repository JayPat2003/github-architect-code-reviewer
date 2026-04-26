"""
github_client.py — Fetches Pull Request data from the GitHub REST API.
"""

import requests
from src.types import PRData, PRFile


def fetch_pull_request(owner: str, repo: str, pr_number: int, token: str) -> PRData:
    """
    Fetch PR metadata and per-file diffs from the GitHub API.

    Returns:
        PRData dataclass including head_sha and list of PRFile.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    pr_resp = requests.get(base, headers=headers, timeout=30)
    pr_resp.raise_for_status()
    pr_data = pr_resp.json()

    files_resp = requests.get(f"{base}/files", headers=headers, timeout=30)
    files_resp.raise_for_status()

    files = [
        PRFile(
            filename=f["filename"],
            status=f["status"],
            additions=f["additions"],
            deletions=f["deletions"],
            patch=f.get("patch", ""),
        )
        for f in files_resp.json()
    ]

    return PRData(
        owner=owner,
        repo=repo,
        number=pr_number,
        title=pr_data["title"],
        body=pr_data.get("body"),
        head_sha=pr_data["head"]["sha"],
        files=files,
    )