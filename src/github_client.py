"""
github_client.py — GitHub API integration layer.

Purpose:
    Fetches Pull Request metadata and the unified diff of every changed file
    using the PyGitHub library, then maps the raw response into the app's
    own PullRequest / PRFile types so the rest of the codebase never touches
    PyGitHub objects directly.

Dependencies:
    pip install PyGithub

How it fits in the pipeline:
    cli.py  ──calls──>  fetch_pull_request()  ──returns──>  PullRequest
"""

from github import Github
from src.types import PRFile, PullRequest


def fetch_pull_request(owner: str, repo: str, pr_number: int, token: str) -> PullRequest:
    """
    Fetch a Pull Request and all its changed files from GitHub.

    Steps:
        1. Authenticate with the provided Personal Access Token (PAT).
        2. Look up the repository by its 'owner/repo' full name.
        3. Retrieve the PR object by number.
        4. Iterate over every changed file and build a PRFile TypedDict for each.
        5. Wrap everything in a PullRequest dataclass and return it.

    Args:
        owner     : GitHub username or organisation (e.g. 'octocat').
        repo      : Repository name (e.g. 'hello-world').
        pr_number : Integer PR number shown in the GitHub UI.
        token     : GitHub PAT with at least 'repo' (private) or
                    'public_repo' (public) scope.

    Returns:
        A fully-populated PullRequest dataclass.

    Raises:
        github.GithubException: If the repo or PR is not found, or auth fails.

    Example:
        pr = fetch_pull_request("octocat", "hello-world", 42, "ghp_...")
    """
    # 1. Authenticate
    g = Github(token)

    # 2. Resolve the repository
    gh_repo = g.get_repo(f"{owner}/{repo}")

    # 3. Fetch the pull request
    gh_pr = gh_repo.get_pull(pr_number)

    # 4. Map each changed file to our internal PRFile TypedDict.
    #    f.patch is None for binary files — we handle that gracefully downstream.
    files: list[PRFile] = [
        PRFile(
            filename=f.filename,
            status=f.status,       # 'added' | 'modified' | 'removed' | 'renamed'
            additions=f.additions,
            deletions=f.deletions,
            patch=f.patch,         # unified diff string, or None
        )
        for f in gh_pr.get_files()
    ]

    # 5. Build and return the aggregated PullRequest object
    return PullRequest(
        owner=owner,
        repo=repo,
        number=pr_number,
        title=gh_pr.title,
        body=gh_pr.body,
        files=files,
    )
