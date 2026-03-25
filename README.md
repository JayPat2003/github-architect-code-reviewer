# 🏗️ GitHub Architect Code Reviewer

> An AI-powered tool that automatically reviews Pull Requests against your organisation's architecture principles — ensuring every code change aligns with your standards before it reaches production.

---

## 📋 Table of Contents

1. [The Problem](#the-problem)
2. [The Solution](#the-solution)
3. [How It Works — High Level](#how-it-works--high-level)
4. [Detailed Pipeline Walkthrough](#detailed-pipeline-walkthrough)
5. [Project Structure](#project-structure)
6. [Setup & Installation](#setup--installation)
7. [Running the Tool](#running-the-tool)
8. [Understanding the Report](#understanding-the-report)
9. [CI/CD Integration](#cicd-integration)

---

## The Problem

In large organisations, software teams are expected to follow strict architecture standards. These standards are typically written in documents that describe rules such as:

- "All external API calls must include error handling."
- "No credentials or secrets may be hardcoded in source code."
- "Services must communicate only through approved interfaces."
- "Every module must remain loosely coupled from others."

**The challenge** is that these documents are long, and developers — under deadline pressure — can unintentionally miss a rule. Today, the only way to catch these violations is through a manual architecture review, which:

- Requires a senior architect's time on every Pull Request.
- Slows down the delivery pipeline.
- Is inconsistent — different reviewers may focus on different rules.
- Often happens too late, after the code is already written.

---

## The Solution

This tool automates the architecture review step using **GitHub Copilot AI**.

When a developer opens a Pull Request, this tool:

1. **Reads** the code changes from GitHub automatically.
2. **Reads** one or more of your organisation's compliance documents (PDFs, web pages, or text/Markdown files).
3. **Sends everything** to GitHub Copilot AI and asks it to check for violations across all documents.
4. **Produces** a structured report listing every issue found, with severity levels and suggested fixes.

The result is an instant, consistent, and repeatable architecture review — every single time a Pull Request is raised.

---

## How It Works — High Level

```
  Developer opens a Pull Request on GitHub
              │
              ▼
  ┌─────────────────────────────┐
  │   Tool is triggered (CLI)   │
  └────────────┬────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  ┌─────────┐     ┌──────────────────────┐
  │  GitHub │     │  Architecture        │
  │   API   │     │  Document            │
  │         │     │  (PDF / URL / Text)  │
  │ PR Diff │     │                      │
  └────┬────┘     └──────────┬───────────┘
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │   GitHub Copilot AI  │
       │                      │
       │  "Does this code     │
       │   follow the rules   │
       │   in the document?"  │
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │   Review Report      │
       │   (JSON File)        │
       │                      │
       │  ✅ PASSED  or       │
       │  ❌ FAILED           │
       │                      │
       │  + List of comments  │
       │    with severity,    │
       │    file, and fix     │
       └──────────────────────┘
```

---

## Detailed Pipeline Walkthrough

The tool is made up of five modules that run in sequence. Below is a walkthrough of each stage.

---

### Stage 1 — Fetch the Pull Request (`github_client.py`)

```
  CLI receives:
  --owner  myorg
  --repo   my-service
  --pr     42
         │
         ▼
  Connects to GitHub API
  using your personal access token
         │
         ▼
  Downloads:
  ┌──────────────────────────────────────────┐
  │  PR Title      : "Add payment service"   │
  │  PR Description: "Implements Stripe..."  │
  │                                          │
  │  Changed Files:                          │
  │  ┌──────────────────────────────────┐    │
  │  │ src/payment.py   [modified]      │    │
  │  │   + 45 lines added               │    │
  │  │   - 12 lines removed             │    │
  │  │   diff: @@ -10,3 +10,5 @@...    │    │
  │  ├──────────────────────────────────┤    │
  │  │ src/config.py    [modified]      │    │
  │  │   + 3 lines added                │    │
  │  └──────────────────────────────────┘    │
  └──────────────────────────────────────────┘
```

A **diff** is a standard format showing exactly what lines of code were added (marked with `+`) and removed (marked with `-`) in a file.

---

### Stage 2 — Load the Architecture Document (`doc_loader.py`)

```
  --doc  path/to/architecture.pdf
              │
              ▼
  ┌──────────────────────────────────┐
  │  Detect document type:           │
  │                                  │
  │  Starts with https:// → Web page │
  │  Ends with .pdf       → PDF file │
  │  Anything else        → Text file│
  └──────────────┬───────────────────┘
                 │
                 ▼
  Extract all text content from the document
                 │
                 ▼
  "All services must implement retry logic.
   No hardcoded credentials are permitted.
   All modules must use dependency injection..."
```

The tool supports your architecture document in whatever format it already exists in — no need to reformat it.

---

### Stage 3 — AI Review (`reviewer.py`)

This is the core of the tool. Both the code diff and the architecture document are combined into a single request sent to **GitHub Copilot AI**.

```
  ┌────────────────────────────────────────────────────────────┐
  │                  Message sent to Copilot AI                │
  │                                                            │
  │  "You are a senior software architect.                     │
  │                                                            │
  │   Here is our Architecture Document:                       │
  │   [full document text]                                     │
  │                                                            │
  │   Here is the Pull Request diff:                           │
  │   [all changed files and their diffs]                      │
  │                                                            │
  │   Review the changes for compliance.                       │
  │   Return a structured JSON report."                        │
  └────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
                    GitHub Copilot AI (gpt-4o)
                               │
                               ▼
  ┌────────────────────────────────────────────────────────────┐
  │                  Structured JSON Response                  │
  │  {                                                         │
  │    "passed": false,                                        │
  │    "summary": "The PR introduces a payment module         │
  │                but hardcodes an API key in config.py,     │
  │                violating the secrets policy.",            │
  │    "comments": [                                           │
  │      {                                                     │
  │        "file": "src/config.py",                           │
  │        "line": 14,                                        │
  │        "severity": "error",                               │
  │        "message": "API key is hardcoded.",                │
  │        "suggestion": "Use environment variables instead." │
  │      }                                                     │
  │    ]                                                       │
  │  }                                                         │
  └────────────────────────────────────────────────────────────┘
```

---

### Stage 4 — Save the Report (`reporter.py`)

```
  ReviewResult object
          │
          ▼
  Serialise to a JSON file with a unique timestamped filename:

  reports/
  └── myorg__my-service__pr42__20240615_143022.json

  The file contains:
  ┌──────────────────────────────────────────┐
  │  meta        : owner, repo, pr, date     │
  │  passed      : true / false              │
  │  summary     : overall AI assessment     │
  │  comments    : list of issues found      │
  │  files_reviewed: list of changed files   │
  └──────────────────────────────────────────┘
```

Each run produces a new file, so a full history of all reviews is preserved.

---

### Stage 5 — Exit Code for CI (`cli.py`)

```
  result.passed == True
        │
        ├── Yes → Print "PASSED", exit with code 0
        │         (CI pipeline continues ✅)
        │
        └── No  → Print "FAILED", exit with code 1
                  (CI pipeline stops ❌)
```

This means the tool can be placed inside an automated pipeline (GitHub Actions, Jenkins, etc.) and will **block a merge** if the code violates architecture rules.

---

## Project Structure

```
copilot-code-reviewer/
│
├── src/
│   ├── cli.py            # Entry point — wires the pipeline together
│   ├── github_client.py  # Fetches PR data from GitHub API
│   ├── doc_loader.py     # Loads architecture document (PDF/URL/text)
│   ├── reviewer.py       # Sends data to Copilot AI and parses response
│   ├── reporter.py       # Saves the structured report to disk
│   └── types.py          # Shared data models used across all modules
│
├── reports/              # Generated review reports are saved here
├── .env                  # Your GitHub token (never commit this file)
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- A GitHub account with access to the repository you want to review
- A GitHub Personal Access Token (PAT)

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/copilot-code-reviewer.git
cd copilot-code-reviewer
```

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Create your `.env` file

Create a file named `.env` in the project root with the following content:

```
GITHUB_TOKEN=ghp_your_personal_access_token_here
```

To generate a token:
1. Go to **GitHub → Settings → Developer Settings → Personal Access Tokens**
2. Create a token with the `repo` scope (for private repositories) or `public_repo` (for public repositories)

> **Important:** Never share or commit this file. It contains your credentials.

---

## Running the Tool

### Basic command (single compliance document)

```bash
python -m src.cli review \
  --owner  your-org \
  --repo   your-repo \
  --pr     42 \
  --doc    path/to/architecture.pdf
```

### Multiple compliance documents

Repeat `--doc` for each additional document — any combination of PDFs, URLs, and text/Markdown files is supported:

```bash
python -m src.cli review \
  --owner  your-org \
  --repo   your-repo \
  --pr     42 \
  --doc    docs/architecture-standards.pdf \
  --doc    https://your-intranet.com/security-policy \
  --doc    docs/company-guidelines.md
```

The AI will check the PR diff against **all** supplied documents and report any violation found in any of them.

### With a URL as the compliance document

```bash
python -m src.cli review \
  --owner  your-org \
  --repo   your-repo \
  --pr     42 \
  --doc    https://your-intranet.com/architecture-standards
```

### Specifying a custom output directory

```bash
python -m src.cli review \
  --owner  your-org \
  --repo   your-repo \
  --pr     42 \
  --doc    architecture.txt \
  --output ./review-history
```

### Help

```bash
python -m src.cli review --help
```

---

## Understanding the Report

The generated JSON report contains the following sections:

| Field              | Description                                                         |
|--------------------|---------------------------------------------------------------------|
| `meta`             | PR details: owner, repo, number, title, review date, and the list of compliance documents used |
| `passed`           | `true` if no errors were found, `false` otherwise                   |
| `summary`          | A paragraph written by the AI summarising the review                |
| `comments`         | A list of specific issues found (see below)                         |
| `files_reviewed`   | Every file that was part of the Pull Request                        |

### Comment severity levels

| Severity  | Meaning                                                        |
|-----------|----------------------------------------------------------------|
| `error`   | A clear violation of an architecture rule. Must be fixed.      |
| `warning` | A potential concern that should be discussed.                  |
| `info`    | A suggestion or observation for improvement.                   |

### Example report

```json
{
  "meta": {
    "owner": "myorg",
    "repo": "payment-service",
    "pr_number": 42,
    "pr_title": "Add Stripe payment integration",
    "reviewed_at": "20240615_143022",
    "compliance_docs": [
      { "source": "docs/architecture-standards.pdf", "doc_type": "pdf" },
      { "source": "https://your-intranet.com/security-policy", "doc_type": "url" }
    ]
  },
  "passed": false,
  "summary": "The PR introduces a payment module but contains a hardcoded API key in config.py, which directly violates the organisation's secrets management policy.",
  "comments": [
    {
      "file": "src/config.py",
      "line": 14,
      "severity": "error",
      "message": "The Stripe API key is hardcoded as a string literal.",
      "suggestion": "Move this value to an environment variable and access it via os.getenv('STRIPE_API_KEY')."
    }
  ],
  "files_reviewed": [
    { "filename": "src/config.py",   "status": "modified", "additions": 3,  "deletions": 1 },
    { "filename": "src/payment.py",  "status": "added",    "additions": 45, "deletions": 0 }
  ]
}
```

---

## CI/CD Integration

The tool exits with code `0` (success) or `1` (failure), making it directly compatible with any CI/CD system.

### GitHub Actions example

```yaml
# .github/workflows/architecture-review.yml

name: Architecture Review

on:
  pull_request:
    branches: [main]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Architecture Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python -m src.cli review \
            --owner  ${{ github.repository_owner }} \
            --repo   ${{ github.event.repository.name }} \
            --pr     ${{ github.event.pull_request.number }} \
            --doc    docs/architecture-standards.pdf \
            --doc    docs/security-policy.md \
            --doc    https://your-intranet.com/company-guidelines
```

When this workflow is added to a repository, **every Pull Request will be automatically reviewed** against all configured compliance documents. If violations are found, the check will fail and the merge will be blocked until the issues are resolved.

---