from __future__ import annotations

import unittest
from typing import Any

from supp_bro.config import STACKOVERFLOW_SEARCH_CAPABILITY, LocalSettings, ProviderTokens
from supp_bro.domain.contracts import ToolRequest
from supp_bro.tools.stackoverflow import UNCONFIRMED_SEARCH_ERROR, search_stackoverflow_questions


def stackoverflow_request(confirmed: bool = True) -> ToolRequest:
    return ToolRequest(
        tool_name="search_stackoverflow_questions",
        tool_type="read",
        payload={"query": "Has anyone seen Debezium buffer lock on Stack Overflow?", "tag": "debezium", "max_results": 5},
        confirmed=confirmed,
    )


class StackOverflowAdapterTest(unittest.TestCase):
    def test_confirmed_success_normalizes_results_and_unescapes_titles(self) -> None:
        calls: list[str] = []

        def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
            calls.append(url)
            return {
                "items": [
                    {
                        "title": "Debezium buffer &amp; lock",
                        "score": 7,
                        "answer_count": 2,
                        "is_answered": True,
                        "last_activity_date": 123,
                        "link": "https://stackoverflow.com/q/1",
                    }
                ]
            }

        observation = search_stackoverflow_questions(
            stackoverflow_request(),
            settings=LocalSettings(provider_tokens=ProviderTokens(stackoverflow_token="so_secret")),
            http_get_json=http_get_json,
        )

        self.assertTrue(observation.success)
        self.assertEqual(observation.status, "success")
        self.assertEqual(observation.source, "stackoverflow")
        self.assertEqual(observation.data["query"], "Has anyone seen Debezium buffer lock on Stack Overflow?")
        self.assertEqual(observation.data["normalized_query"], "debezium buffer lock")
        self.assertEqual(observation.data["tag"], "debezium")
        self.assertEqual(observation.data["count"], 1)
        self.assertEqual(observation.data["results"][0]["title"], "Debezium buffer & lock")
        self.assertIn("key=so_secret", calls[0])
        self.assertNotIn("so_secret", observation.raw_reference or "")
        self.assertNotIn("so_secret", repr(observation))

    def test_unconfirmed_search_is_skipped_without_http(self) -> None:
        called = False

        def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
            nonlocal called
            called = True
            return {}

        observation = search_stackoverflow_questions(
            stackoverflow_request(confirmed=False),
            settings=LocalSettings(provider_tokens=ProviderTokens(stackoverflow_token="so_secret")),
            http_get_json=http_get_json,
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "skipped")
        self.assertEqual(observation.error, UNCONFIRMED_SEARCH_ERROR)
        self.assertFalse(called)

    def test_unavailable_does_not_call_http(self) -> None:
        for settings in [
            LocalSettings(),
            LocalSettings(
                provider_tokens=ProviderTokens(stackoverflow_token="so_secret"),
                capability_enabled={STACKOVERFLOW_SEARCH_CAPABILITY: False},
            ),
        ]:
            with self.subTest(settings=settings):
                called = False

                def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
                    nonlocal called
                    called = True
                    return {}

                observation = search_stackoverflow_questions(
                    stackoverflow_request(),
                    settings=settings,
                    http_get_json=http_get_json,
                )

                self.assertFalse(observation.success)
                self.assertEqual(observation.status, "unavailable")
                self.assertFalse(called)

    def test_timeout_and_provider_failure_are_typed_and_redacted(self) -> None:
        encoded_token = "so%2Fsecret"
        for exc, expected_status in [
            (TimeoutError("so/secret timed out"), "timeout"),
            (RuntimeError(f"{encoded_token} failed"), "failed"),
        ]:
            with self.subTest(expected_status=expected_status):
                def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
                    raise exc

                observation = search_stackoverflow_questions(
                    stackoverflow_request(),
                    settings=LocalSettings(provider_tokens=ProviderTokens(stackoverflow_token="so/secret")),
                    http_get_json=http_get_json,
                )

                self.assertFalse(observation.success)
                self.assertEqual(observation.status, expected_status)
                self.assertNotIn("so/secret", observation.error or "")
                self.assertNotIn(encoded_token, observation.error or "")

    def test_malformed_payload_is_failed_observation(self) -> None:
        observation = search_stackoverflow_questions(
            stackoverflow_request(),
            settings=LocalSettings(provider_tokens=ProviderTokens(stackoverflow_token="so_secret")),
            http_get_json=lambda url, headers=None, timeout=20: {"items": "not a list"},
        )

        self.assertFalse(observation.success)
        self.assertEqual(observation.status, "failed")

    def test_non_string_result_title_does_not_raise(self) -> None:
        observation = search_stackoverflow_questions(
            stackoverflow_request(),
            settings=LocalSettings(provider_tokens=ProviderTokens(stackoverflow_token="so_secret")),
            http_get_json=lambda url, headers=None, timeout=20: {
                "items": [{"title": 123, "link": "https://stackoverflow.com/q/1"}]
            },
        )

        self.assertTrue(observation.success)
        self.assertEqual(observation.data["results"][0]["title"], "")


if __name__ == "__main__":
    unittest.main()
