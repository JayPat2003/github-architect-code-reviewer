"""
reviewer.py — GitHub Copilot API integration for code review.

Purpose:
    Builds a structured prompt from the PR diff and one or more compliance /
    architecture documents, sends it to the GitHub Copilot chat completions
    API via the openai SDK, parses the JSON response into ReviewComment
    objects, and returns a ReviewResult.

How it fits in the pipeline:
    cli.py  ──calls──>  run_review(pr, docs)  ──returns──>  ReviewResult
                                                                  │
                                                           reporter.py uses it

Environment variables required:
    GITHUB_TOKEN : Used as the Bearer token for Copilot API auth.
"""

import json
import os
from typing import List

from openai import OpenAI

from src.types import ArchitectureDoc, PullRequest, ReviewComment, ReviewResult


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(pr: PullRequest, docs: List[ArchitectureDoc]) -> str:
    """
    Construct the user message sent to the Copilot model.

    Includes:
        - PR title and description
        - All compliance / architecture document contents (clearly labelled)
        - Unified diffs of every changed file

    Args:
        pr  : Fetched PullRequest object.
        docs: One or more loaded ArchitectureDoc objects.

    Returns:
        A single formatted string ready to send as the user message.
    """
    diff_sections = []
    for f in pr.files:
        patch = f["patch"] or "(binary file — no diff available)"
        diff_sections.append(
            f"### File: {f['filename']}  [{f['status']}  +{f['additions']} -{f['deletions']}]\n"
            f"```diff\n{patch}\n```"
        )

    diffs = "\n\n".join(diff_sections)

    # Build a clearly labelled section for every compliance document
    doc_sections = []
    for i, doc in enumerate(docs, start=1):
        doc_sections.append(
            f"### Compliance Document {i}: {doc.source} [{doc.doc_type}]\n"
            f"{doc.content}"
        )
    docs_block = "\n\n".join(doc_sections)

    return f"""You are a senior software architect reviewing a Pull Request for compliance with the project's architecture principles and company policies.

## Compliance & Architecture Documents
{docs_block}

## Pull Request
**Title:** {pr.title}
**Description:** {pr.body or 'No description provided.'}

## Changed Files
{diffs}

## Your Task
Review every changed file against ALL of the compliance and architecture documents listed above.
Return a JSON object with this exact shape:
{{
  "summary": "<one paragraph overall assessment>",
  "passed": true | false,
  "comments": [
    {{
      "file": "<filename>",
      "line": <integer or null>,
      "severity": "error" | "warning" | "info",
      "message": "<what the issue is>",
      "suggestion": "<how to fix it, or null>"
    }}
  ]
}}
Set passed=false if ANY comment has severity="error".
Return ONLY the JSON object — no markdown fences, no extra text."""


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_response(raw: str, pr: PullRequest, docs: List[ArchitectureDoc]) -> ReviewResult:
    """
    Parse the raw JSON string returned by the Copilot model.

    Falls back to a single error comment if the response cannot be parsed,
    so the pipeline never crashes due to a malformed LLM response.

    Args:
        raw : Raw string content from the model's message.
        pr  : The original PullRequest (attached to the result).
        docs: The compliance documents used in this review.

    Returns:
        A fully-populated ReviewResult.
    """
    try:
        data = json.loads(raw)
        comments: List[ReviewComment] = [
            ReviewComment(
                file=c.get("file", "unknown"),
                line=c.get("line"),
                severity=c.get("severity", "info"),
                message=c.get("message", ""),
                suggestion=c.get("suggestion"),
            )
            for c in data.get("comments", [])
        ]
        return ReviewResult(
            pr=pr,
            comments=comments,
            summary=data.get("summary", ""),
            passed=data.get("passed", True),
            compliance_docs=docs,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        # Graceful fallback — surface the raw response as an error comment
        return ReviewResult(
            pr=pr,
            comments=[
                ReviewComment(
                    file="N/A",
                    line=None,
                    severity="error",
                    message=f"Failed to parse Copilot response: {exc}",
                    suggestion=f"Raw response was:\n{raw}",
                )
            ],
            summary="Review could not be parsed.",
            passed=False,
            compliance_docs=docs,
        )


# ── Public entry point ────────────────────────────────────────────────────────

def run_review(pr: PullRequest, docs: List[ArchitectureDoc]) -> ReviewResult:
    """
    Orchestrate the full Copilot review for one PR against one or more
    compliance / architecture documents.

    Uses GitHub Models API (models.inference.ai.azure.com) which accepts
    a GitHub PAT directly — no token exchange needed.

    Steps:
        1. Initialise the OpenAI client pointed at GitHub Models API.
        2. Build the prompt from the PR diff and all compliance documents.
        3. Send a chat completion request to gpt-4o.
        4. Parse and return the structured ReviewResult.

    Args:
        pr  : The PullRequest to review.
        docs: One or more ArchitectureDoc objects to check compliance against.
    """
    # Explicitly remove any OPENAI_BASE_URL or OPENAI_API_KEY that could
    # redirect the client to the internal Copilot endpoint
    os.environ.pop("OPENAI_BASE_URL", None)
    os.environ.pop("OPENAI_API_KEY", None)

    # 1. Initialise client — GitHub Models API accepts PAT directly
    client = OpenAI(
        api_key=os.environ["GITHUB_TOKEN"],
        base_url="https://models.inference.ai.azure.com",
    )

    # 2. Build prompt
    prompt = _build_prompt(pr, docs)

    # 3. Call the API
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert software architect. "
                    "You review code changes for compliance with architecture principles "
                    "and company policies. "
                    "Always respond with valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content or ""

    # 4. Parse and return
    return _parse_response(raw, pr, docs)
