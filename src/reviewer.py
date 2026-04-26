"""
reviewer.py — Agentic review loop using tool-calling.

The agent iterates up to MAX_ITERATIONS turns. On each turn it may:
  1. fetch_file_content      → examine a file diff in detail
  2. search_architecture_doc → look up relevant rules
  3. flag_violation          → record a specific issue
  4. finish_review           → end the loop with a verdict
"""

import json
import os
from typing import Optional
from openai import OpenAI

from src.types import PRData, ReviewResult, ReviewComment, PRFile
from src.tools import TOOLS

MAX_ITERATIONS = 15
DOC_CHUNK_SIZE = 1200
DOC_CHUNK_OVERLAP = 200


def _chunk_document(text: str, chunk_size: int = DOC_CHUNK_SIZE, overlap: int = DOC_CHUNK_OVERLAP) -> list[str]:
    """Split architecture text into overlapping chunks for retrieval."""
    if not text:
        return []
    if chunk_size <= 0:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += step
    return chunks


def _retrieve_relevant_chunks(query: str, chunks: list[str], max_chunks: int = 5) -> list[dict]:
    """Return top matching chunks using simple keyword overlap scoring."""
    tokens = [t for t in query.lower().split() if t]
    if not chunks:
        return []

    scored: list[tuple[int, int, str]] = []
    for idx, chunk in enumerate(chunks):
        lower = chunk.lower()
        score = sum(lower.count(token) for token in tokens) if tokens else 0
        if not tokens:
            score = 1
        if score > 0:
            scored.append((score, idx, chunk))

    scored.sort(key=lambda item: (-item[0], item[1]))
    top = scored[: max(1, max_chunks)]
    return [
        {"chunk_index": idx, "score": score, "content": chunk}
        for score, idx, chunk in top
    ]


def run_review(pr: PRData, arch_doc, client: Optional[OpenAI] = None, github_token: Optional[str] = None) -> ReviewResult:
    """
    Run an agentic architecture review of a pull request.

    Args:
        pr:       PRData including per-file diffs and head_sha.
        arch_doc: ArchitectureDoc or plain string of the architecture document.

    Returns:
        ReviewResult with pass/fail verdict, summary, and per-violation comments.
    """
    if client is None:
        resolved_token = github_token or os.getenv("GITHUB_TOKEN") or "DUMMY_LOCAL_TOKEN"
        client = OpenAI(
            api_key=resolved_token,
            base_url="https://models.inference.ai.azure.com",
        )

    doc_text = arch_doc.content if hasattr(arch_doc, "content") else str(arch_doc)
    file_index: dict[str, PRFile] = {f.filename: f for f in pr.files}
    doc_chunks = _chunk_document(doc_text)
    reviewed_files: set[str] = set()
    violations: list[ReviewComment] = []
    finish_args: dict | None = None

    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior software architect performing a rigorous PR review.\n"
                "Use the provided tools methodically:\n"
                "  1. Inspect EVERY changed file using fetch_file_content.\n"
                "  2. Cross-reference rules using search_architecture_doc.\n"
                "  3. Record every violation with flag_violation.\n"
                "  4. Call finish_review once — only after ALL files are checked.\n"
                "passed must be false if any 'error' severity violation exists."
            )
        },
        {
            "role": "user",
            "content": (
                f"Review PR #{pr.number}: \"{pr.title}\"\n\n"
                f"Changed files ({len(pr.files)}):\n"
                + "\n".join(
                    f"  • {f.filename} [{f.status}] +{f.additions}/-{f.deletions}"
                    for f in pr.files
                )
                + f"\n\nArchitecture Document:\n{doc_text[:5000]}\n\n"
                "Start by fetching each file's content, then cross-check against the document."
            )
        }
    ]

    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            break

        tool_results = []
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = _dispatch(
                name,
                args,
                file_index,
                doc_text,
                doc_chunks,
                violations,
                reviewed_files,
            )
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })
            if name == "finish_review":
                finish_args = args

        messages.extend(tool_results)

        if finish_args:
            break

    # Fallback if agent never called finish_review
    if not finish_args:
        has_errors = any(v.severity == "error" for v in violations)
        finish_args = {
            "passed": not has_errors,
            "summary": (
                "Review reached iteration limit. "
                f"{'Errors found — marking as failed.' if has_errors else 'No errors recorded.'}"
            )
        }

    unreviewed_files = [f.filename for f in pr.files if f.filename not in reviewed_files]
    if unreviewed_files:
        violations.append(ReviewComment(
            file="__review_process__",
            severity="error",
            message=(
                "Agent finished without inspecting all changed files: "
                + ", ".join(unreviewed_files)
            ),
            suggestion="Call fetch_file_content for every changed file before finish_review.",
            line=None,
        ))
        finish_args["summary"] = (
            f'{finish_args["summary"]} Review process gap: not all files were inspected.'
        )

    has_errors = any(v.severity == "error" for v in violations)
    if has_errors and finish_args.get("passed", True):
        finish_args["passed"] = False
        finish_args["summary"] = (
            f'{finish_args["summary"]} Verdict adjusted: errors were recorded.'
        )

    return ReviewResult(
        passed=finish_args["passed"],
        summary=finish_args["summary"],
        comments=violations,
        files_reviewed=[
            {"filename": f.filename, "status": f.status,
             "additions": f.additions, "deletions": f.deletions}
            for f in pr.files
        ]
    )


def _dispatch(
    name: str,
    args: dict,
    file_index: dict[str, PRFile],
    arch_doc: str,
    doc_chunks: list[str],
    violations: list[ReviewComment],
    reviewed_files: set[str],
) -> dict:
    if name == "fetch_file_content":
        filename = args.get("filename")
        if not filename:
            return {"error": "Missing required argument: filename"}
        pr_file = file_index.get(filename)
        reviewed_files.add(filename)
        if not pr_file:
            return {"error": f"'{filename}' not found in PR"}
        patch = pr_file.patch or ""
        return {
            "content": patch,
            "file": {
                "filename": pr_file.filename,
                "status": pr_file.status,
                "additions": pr_file.additions,
                "deletions": pr_file.deletions,
                "patch_line_count": len(patch.splitlines()) if patch else 0,
                "has_patch": bool(patch),
            },
        }

    if name == "search_architecture_doc":
        query = args.get("query", "").strip()
        if not query:
            return {"error": "Missing required argument: query"}
        max_chunks = int(args.get("max_chunks", 5))
        chunk_hits = _retrieve_relevant_chunks(query, doc_chunks, max_chunks=max_chunks)
        if chunk_hits:
            return {
                "results": chunk_hits,
                "strategy": "chunk_retrieval",
            }
        hits = [line for line in arch_doc.splitlines() if query.lower() in line.lower()]
        return {
            "results": hits[:25] if hits else ["No matching rules found for this query."],
            "strategy": "line_fallback",
        }

    if name == "flag_violation":
        violations.append(ReviewComment(
            file=args["file"],
            severity=args["severity"],
            message=args["message"],
            suggestion=args["suggestion"],
            line=args.get("line"),
        ))
        return {"status": "violation recorded", "total_so_far": len(violations)}

    if name == "finish_review":
        return {"status": "review complete"}

    return {"error": f"Unknown tool: {name}"}