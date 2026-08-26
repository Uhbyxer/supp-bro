from __future__ import annotations

import unittest
from typing import Any

from supp_bro.config import LocalSettings, ProviderTokens
from supp_bro.domain.contracts import ToolRequest
from supp_bro.tools.github_issues import fetch_github_issue_context


def github_request() -> ToolRequest:
    return ToolRequest(
        tool_name="get_github_issue_context",
        tool_type="read",
        payload={"repo": "debezium/dbz", "issue_number": 3},
    )


class GithubIssuesAdapterTest(unittest.TestCase):
    def test_success_normalizes_issue_context(self) -> None:
        calls: list[tuple[str, dict[str, str] | None, int]] = []

        def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
            calls.append((url, headers, timeout))
            if url.endswith("/comments?per_page=30"):
                return [
                    {"user": {"login": "commenter-a"}},
                    {"user": {"login": "commenter-b"}},
                ]
            return {
                "title": "Unable to acquire buffer lock",
                "state": "open",
                "labels": [{"name": "bug"}],
                "assignees": [{"login": "maintainer"}],
                "user": {"login": "reporter"},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
                "closed_at": None,
                "comments": 2,
                "html_url": "https://github.com/debezium/dbz/issues/3",
            }

        observation = fetch_github_issue_context(
            github_request(),
            settings=LocalSettings(provider_tokens=ProviderTokens(github_token="ghp_secret")),
            http_get_json=http_get_json,
        )

        self.assertTrue(observation.success)
        self.assertEqual(observation.status, "success")
        self.assertEqual(observation.source, "github")
        self.assertEqual(observation.data["repo"], "debezium/dbz")
        self.assertEqual(observation.data["issue_number"], 3)
        self.assertEqual(observation.data["title"], "Unable to acquire buffer lock")
        self.assertEqual(observation.data["labels"], ["bug"])
        self.assertEqual(observation.data["assignees"], ["maintainer"])
        self.assertEqual(observation.data["participants"], ["commenter-a", "commenter-b", "maintainer", "reporter"])
        self.assertEqual(observation.data["recent_comment_authors"], ["commenter-a", "commenter-b"])
        self.assertNotIn("ghp_secret", repr(observation))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], {"Authorization": "Bearer ghp_secret"})

    def test_unavailable_does_not_call_http(self) -> None:
        called = False

        def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
            nonlocal called
            called = True
            return {}

        observation = fetch_github_issue_context(
            github_request(),
            settings=LocalSettings(),
            http_get_json=http_get_json,
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "unavailable")
        self.assertFalse(called)

    def test_timeout_and_provider_failure_are_typed_and_redacted(self) -> None:
        for exc, expected_status in [(TimeoutError("ghp_secret timed out"), "timeout"), (RuntimeError("ghp_secret failed"), "failed")]:
            with self.subTest(expected_status=expected_status):
                def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
                    raise exc

                observation = fetch_github_issue_context(
                    github_request(),
                    settings=LocalSettings(provider_tokens=ProviderTokens(github_token="ghp_secret")),
                    http_get_json=http_get_json,
                )

                self.assertFalse(observation.success)
                self.assertEqual(observation.status, expected_status)
                self.assertNotIn("ghp_secret", observation.error or "")

    def test_malformed_payload_is_failed_observation(self) -> None:
        observation = fetch_github_issue_context(
            github_request(),
            settings=LocalSettings(provider_tokens=ProviderTokens(github_token="ghp_secret")),
            http_get_json=lambda url, headers=None, timeout=20: [],
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "failed")


if __name__ == "__main__":
    unittest.main()
