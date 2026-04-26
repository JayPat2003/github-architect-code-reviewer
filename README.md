# 🏗️ GitHub Architect Code Reviewer

> Agentic AI code review for Pull Requests, aligned to your architecture standards, with deterministic safeguards for CI.

---

## 📋 Table of Contents

1. [What This Tool Solves](#what-this-tool-solves)
2. [What It Does](#what-it-does)
3. [Agentic Safeguards (Latest)](#agentic-safeguards-latest)
4. [How It Works](#how-it-works)
5. [Project Structure](#project-structure)
6. [Setup](#setup)
7. [Usage](#usage)
8. [Output Report Format](#output-report-format)
9. [Testing](#testing)
10. [CI/CD Integration](#cicd-integration)

---

## What This Tool Solves

Architecture docs are usually long, and PR reviewers are time-constrained. That creates risk:

- Important rules can be missed.
- Manual reviews can be inconsistent.
- Violations are found late in the cycle.

This project automates architecture-aware PR checks so each PR is reviewed with the same process and quality bar.

---

## What It Does

For each PR, the tool:

1. Fetches changed files and patches from GitHub.
2. Loads architecture guidance from `PDF`, `URL`, or text file.
3. Runs an agentic tool-calling review loop with `gpt-4o`.
4. Produces a structured JSON report.
5. Optionally posts review comments back to the PR.

---

## Agentic Safeguards (Latest)

The latest version includes hardening to make the reviewer more reliable and truly CI-safe:

- **Mandatory file coverage**: review fails if the agent does not inspect every changed file with `fetch_file_content`.
- **Verdict consistency enforcement**: if any `error` violation is recorded, final verdict is automatically forced to `passed=false`.
- **Chunked architecture retrieval**: architecture doc is chunked and retrieved via relevance scoring, avoiding reliance on only the first few thousand characters.
- **Richer file-context tool output**: `fetch_file_content` now returns patch plus metadata (`status`, `additions`, `deletions`, `patch_line_count`, `has_patch`).
- **Safer local/test execution**: reviewer supports injected client/token and no longer mutates global `OPENAI_*` environment values.

---

## How It Works

```text
PR Opened
   ↓
CLI command (src/cli.py)
   ↓
Fetch PR data (src/github_client.py)
   ↓
Load architecture document (src/doc_loader.py)
   ↓
Agentic review loop (src/reviewer.py)
   - fetch_file_content
   - search_architecture_doc
   - flag_violation
   - finish_review
   ↓
Deterministic post-checks
   - all files reviewed?
   - any error => force fail
   ↓
Save JSON report (src/reporter.py)
   ↓
Optional: post PR review comments (src/github_commenter.py)
```

### Core Modules

- `src/cli.py` — command entrypoint and orchestration.
- `src/github_client.py` — GitHub API PR + files fetch.
- `src/doc_loader.py` — architecture doc ingestion (`url` / `pdf` / `text`).
- `src/reviewer.py` — agentic tool loop + safety enforcement.
- `src/tools.py` — tool schemas exposed to the model.
- `src/reporter.py` — writes JSON reports.
- `src/github_commenter.py` — posts PR review comments.
- `src/types.py` — shared dataclasses.

---

## Project Structure

```text
copilot-code-reviewer/
├── src/
│   ├── cli.py
│   ├── github_client.py
│   ├── doc_loader.py
│   ├── reviewer.py
│   ├── tools.py
│   ├── reporter.py
│   ├── github_commenter.py
│   └── types.py
├── tests/
│   └── test_agent.py
├── reports/
├── .github/workflows/architecture-review.yml
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- GitHub token with repo access

### Install

```bash
git clone https://github.com/your-org/copilot-code-reviewer.git
cd copilot-code-reviewer
pip install -r requirements.txt
```

### Environment

Create `.env`:

```bash
GITHUB_TOKEN=ghp_your_token_here
```

---

## Usage

### Basic run

```bash
python -m src.cli review \
  --owner your-org \
  --repo your-repo \
  --pr 42 \
  --doc path/to/architecture.pdf
```

### With URL doc

```bash
python -m src.cli review \
  --owner your-org \
  --repo your-repo \
  --pr 42 \
  --doc https://your-docs-url/architecture
```

### With custom output directory

```bash
python -m src.cli review \
  --owner your-org \
  --repo your-repo \
  --pr 42 \
  --doc architecture.txt \
  --output ./review-history
```

### Post comments back to PR

```bash
python -m src.cli review \
  --owner your-org \
  --repo your-repo \
  --pr 42 \
  --doc architecture.txt \
  --post-comments
```

---

## Output Report Format

Each run writes `reports/review__YYYYMMDD_HHMMSS.json` with this shape:

| Field | Description |
|---|---|
| `reviewed_at` | Timestamp of report generation |
| `passed` | Final verdict (`true` / `false`) |
| `summary` | Review summary text |
| `comments` | Violations found |
| `files_reviewed` | Changed file metadata list |

### Example

```json
{
  "reviewed_at": "20260426_184200",
  "passed": false,
  "summary": "2 architecture violations found. Verdict adjusted: errors were recorded.",
  "comments": [
    {
      "file": "src/config.py",
      "line": 14,
      "severity": "error",
      "message": "Hardcoded secret detected.",
      "suggestion": "Use environment variables."
    }
  ],
  "files_reviewed": [
    { "filename": "src/config.py", "status": "modified", "additions": 3, "deletions": 1 }
  ]
}
```

---

## Testing

Run all tests:

```bash
pytest -q
```

Run agent-focused tests:

```bash
python -m pytest tests/test_agent.py -v
```

Current baseline after latest improvements:

- `20 passed`
- No lints on updated agent modules

---

## CI/CD Integration

Workflow: `.github/workflows/architecture-review.yml`

It currently performs:

1. Install dependencies
2. Validate agent tests
3. Run agentic review on PR
4. Optionally post comments
5. Upload generated report artifact

This allows architecture compliance to become an enforceable PR gate (`exit 0/1`) in GitHub Actions.

---