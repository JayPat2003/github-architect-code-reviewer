"""
Validates the agentic reviewer end-to-end.

Run:
    python -m pytest tests/test_agent.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.types import PRData, PRFile, ReviewComment, ReviewResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

ARCH_DOC_TEXT = """
Architecture Standards v2.0
Rule 1: No hardcoded credentials, API keys, or secrets in source code.
Rule 2: All external HTTP calls must include retry logic and error handling.
Rule 3: Services must use dependency injection; avoid global mutable state.
Rule 4: Every public function must have a docstring.
"""

DIRTY_PR = PRData(
    owner="myorg", repo="payment-service",
    number=99, title="Add Stripe payment service",
    body="Integrates Stripe for checkout",
    head_sha="abc123def456",
    files=[
        PRFile("src/payment.py", "added",    10, 0, '+STRIPE_KEY = "sk_live_hardcoded"\n+def charge(): pass'),
        PRFile("src/config.py",  "modified",  2, 1, '+DB_PASSWORD = "prod_password_123"\n-DB_PASSWORD = ""'),
    ]
)

CLEAN_PR = PRData(
    owner="myorg", repo="my-service",
    number=100, title="Fix README typo",
    body="", head_sha="deadbeef0000",
    files=[PRFile("README.md", "modified", 1, 1, "+# Fixed heading\n-# Old heading")]
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tc(call_id, name, args):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def _msg(*tool_calls):
    m = MagicMock()
    m.tool_calls = list(tool_calls) if tool_calls else None
    m.content = None
    return m


def _mock_client(turns):
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=t)]) for t in turns
    ]
    return client


# ── Tool dispatcher unit tests ────────────────────────────────────────────────

class TestToolDispatch:

    def test_fetch_existing_file(self):
        from src.reviewer import _dispatch
        reviewed = set()
        file_index = {"src/payment.py": PRFile("src/payment.py", "added", 1, 0, "+code")}
        result = _dispatch("fetch_file_content", {"filename": "src/payment.py"},
                           file_index, "", [], [], reviewed)
        assert "code" in result["content"]
        assert result["file"]["status"] == "added"
        assert "src/payment.py" in reviewed

    def test_fetch_missing_file(self):
        from src.reviewer import _dispatch
        result = _dispatch("fetch_file_content", {"filename": "ghost.py"}, {}, "", [], [], set())
        assert "error" in result

    def test_search_doc_finds_match(self):
        from src.reviewer import _dispatch
        result = _dispatch("search_architecture_doc", {"query": "credentials"}, {}, ARCH_DOC_TEXT, [ARCH_DOC_TEXT], [], set())
        assert result["strategy"] in {"chunk_retrieval", "line_fallback"}
        serialized = json.dumps(result["results"]).lower()
        assert "credentials" in serialized

    def test_search_doc_no_match(self):
        from src.reviewer import _dispatch
        result = _dispatch("search_architecture_doc", {"query": "quantum_flux"}, {}, ARCH_DOC_TEXT, [ARCH_DOC_TEXT], [], set())
        assert "No matching rules found for this query." in json.dumps(result["results"])

    def test_flag_violation_appends(self):
        from src.reviewer import _dispatch
        violations = []
        _dispatch("flag_violation", {
            "file": "src/payment.py", "line": 1,
            "severity": "error", "message": "Hardcoded key",
            "suggestion": "Use os.getenv()"
        }, {}, "", [], violations, set())
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_flag_violation_no_line(self):
        from src.reviewer import _dispatch
        violations = []
        _dispatch("flag_violation", {
            "file": "src/config.py",
            "severity": "warning", "message": "No docstring",
            "suggestion": "Add docstring"
        }, {}, "", [], violations, set())
        assert violations[0].line is None

    def test_finish_review(self):
        from src.reviewer import _dispatch
        result = _dispatch("finish_review", {"passed": False, "summary": "Bad"}, {}, "", [], [], set())
        assert result["status"] == "review complete"

    def test_unknown_tool(self):
        from src.reviewer import _dispatch
        result = _dispatch("alien_tool", {}, {}, "", [], [], set())
        assert "error" in result


# ── Agentic loop integration tests ────────────────────────────────────────────

class TestAgenticLoop:

    def test_detects_secrets_and_fails(self):
        from src.reviewer import run_review

        turns = [
            _msg(
                _tc("c1", "fetch_file_content", {"filename": "src/payment.py"}),
                _tc("c2", "fetch_file_content", {"filename": "src/config.py"}),
            ),
            _msg(
                _tc("c3", "flag_violation", {
                    "file": "src/payment.py", "line": 1, "severity": "error",
                    "message": "Hardcoded Stripe key", "suggestion": "Use os.getenv('STRIPE_KEY')"
                }),
                _tc("c4", "flag_violation", {
                    "file": "src/config.py", "line": 1, "severity": "error",
                    "message": "Hardcoded DB password", "suggestion": "Use os.getenv('DB_PASSWORD')"
                }),
            ),
            _msg(_tc("c5", "finish_review", {
                "passed": False, "summary": "Two hardcoded secrets violate Rule 1."
            })),
        ]

        with patch("src.reviewer.OpenAI", return_value=_mock_client(turns)):
            result = run_review(DIRTY_PR, ARCH_DOC_TEXT)

        assert result.passed is False
        assert len(result.comments) == 2
        assert all(c.severity == "error" for c in result.comments)

    def test_clean_pr_passes(self):
        from src.reviewer import run_review

        turns = [
            _msg(_tc("c1", "fetch_file_content", {"filename": "README.md"})),
            _msg(_tc("c2", "finish_review", {"passed": True, "summary": "No violations."})),
        ]

        with patch("src.reviewer.OpenAI", return_value=_mock_client(turns)):
            result = run_review(CLEAN_PR, ARCH_DOC_TEXT)

        assert result.passed is True
        assert len(result.comments) == 0

    def test_fallback_when_finish_never_called(self):
        from src.reviewer import run_review

        turns = [
            _msg(_tc("c0", "fetch_file_content", {"filename": "src/payment.py"})),
            _msg(_tc("c1", "flag_violation", {
                "file": "src/payment.py", "line": 1, "severity": "error",
                "message": "Hardcoded key", "suggestion": "Use env var"
            })),
            _msg(),  # no tool_calls → loop breaks
        ]

        with patch("src.reviewer.OpenAI", return_value=_mock_client(turns)):
            result = run_review(DIRTY_PR, ARCH_DOC_TEXT)

        assert result.passed is False
        assert len(result.comments) >= 1

    def test_files_reviewed_populated(self):
        from src.reviewer import run_review

        turns = [_msg(_tc("c1", "finish_review", {"passed": True, "summary": "OK"}))]
        mock = MagicMock()
        mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=turns[0])]
        )

        with patch("src.reviewer.OpenAI", return_value=mock):
            result = run_review(DIRTY_PR, ARCH_DOC_TEXT)

        filenames = [f["filename"] for f in result.files_reviewed]
        assert "src/payment.py" in filenames
        assert "src/config.py" in filenames

    def test_warning_only_still_passes(self):
        from src.reviewer import run_review

        turns = [
            _msg(_tc("c0", "fetch_file_content", {"filename": "README.md"})),
            _msg(_tc("c1", "flag_violation", {
                "file": "src/payment.py", "severity": "warning",
                "message": "Missing docstring", "suggestion": "Add one"
            })),
            _msg(_tc("c2", "finish_review", {"passed": True, "summary": "Only minor issues."})),
        ]

        with patch("src.reviewer.OpenAI", return_value=_mock_client(turns)):
            result = run_review(CLEAN_PR, ARCH_DOC_TEXT)

        assert result.passed is True
        assert result.comments[0].severity == "warning"


# ── GitHub commenter tests ────────────────────────────────────────────────────

class TestGitHubCommenter:

    def _result(self, passed=False):
        return ReviewResult(
            passed=passed,
            summary="Test summary.",
            comments=[
                ReviewComment("src/payment.py", "error",   "Hardcoded key",    "Use env var",    line=1),
                ReviewComment("src/config.py",   "error",   "Hardcoded passwd", "Use env var",    line=2),
                ReviewComment("src/payment.py",  "warning", "No docstring",     "Add docstring",  line=None),
            ],
            files_reviewed=[]
        )

    def _mock_post(self, mock_post_cls, html_url="https://github.com/r/p/99#review-1"):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"html_url": html_url}
        mock_resp.raise_for_status = MagicMock()
        mock_post_cls.return_value = mock_resp

    def test_request_changes_on_failure(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp)
            post_review_comments("org", "repo", DIRTY_PR, self._result(passed=False), "tok")
        assert mp.call_args.kwargs["json"]["event"] == "REQUEST_CHANGES"

    def test_approve_on_pass(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp)
            post_review_comments("org", "repo", DIRTY_PR, self._result(passed=True), "tok")
        assert mp.call_args.kwargs["json"]["event"] == "APPROVE"

    def test_commit_sha_in_payload(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp)
            post_review_comments("org", "repo", DIRTY_PR, self._result(), "tok")
        assert mp.call_args.kwargs["json"]["commit_id"] == "abc123def456"

    def test_only_lined_comments_posted_inline(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp)
            post_review_comments("org", "repo", DIRTY_PR, self._result(), "tok")
        comments = mp.call_args.kwargs["json"]["comments"]
        assert len(comments) == 2  # 2 have lines, 1 does not
        assert all("line" in c for c in comments)

    def test_lineless_comment_folded_into_body(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp)
            post_review_comments("org", "repo", DIRTY_PR, self._result(), "tok")
        body = mp.call_args.kwargs["json"]["body"]
        assert "No docstring" in body

    def test_http_error_propagates(self):
        from src.github_commenter import post_review_comments
        import requests as req
        with patch("src.github_commenter.requests.post") as mp:
            mp.return_value = MagicMock(
                raise_for_status=MagicMock(side_effect=req.HTTPError("403"))
            )
            with pytest.raises(req.HTTPError):
                post_review_comments("org", "repo", DIRTY_PR, self._result(), "bad_token")

    def test_returns_html_url(self):
        from src.github_commenter import post_review_comments
        with patch("src.github_commenter.requests.post") as mp:
            self._mock_post(mp, html_url="https://github.com/org/repo/pull/99#review-42")
            url = post_review_comments("org", "repo", DIRTY_PR, self._result(), "tok")
        assert url == "https://github.com/org/repo/pull/99#review-42"