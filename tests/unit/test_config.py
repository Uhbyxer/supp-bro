from __future__ import annotations

import unittest

from supp_bro.config import (
    GITHUB_ISSUES_CAPABILITY,
    MONGO_RETRIEVAL_CAPABILITY,
    OPENAI_EMBEDDINGS_CAPABILITY,
    PINECONE_RETRIEVAL_CAPABILITY,
    STACKOVERFLOW_SEARCH_CAPABILITY,
    LocalSettings,
    build_local_settings,
)


class LocalSettingsTest(unittest.TestCase):
    def test_empty_environment_builds_with_unavailable_capabilities(self) -> None:
        settings = build_local_settings({})

        self.assertFalse(settings.is_capability_available(GITHUB_ISSUES_CAPABILITY))
        self.assertFalse(settings.is_capability_available(STACKOVERFLOW_SEARCH_CAPABILITY))
        self.assertFalse(settings.is_capability_available(OPENAI_EMBEDDINGS_CAPABILITY))

    def test_provider_tokens_make_matching_capabilities_available(self) -> None:
        cases = [
            (GITHUB_ISSUES_CAPABILITY, "GITHUB_TOKEN", "github_token"),
            (STACKOVERFLOW_SEARCH_CAPABILITY, "STACKOVERFLOW_TOKEN", "stackoverflow_token"),
            (OPENAI_EMBEDDINGS_CAPABILITY, "OPENAI_API_KEY", "openai_api_key"),
            (PINECONE_RETRIEVAL_CAPABILITY, "PINECONE_API_KEY", "pinecone_api_key"),
            (MONGO_RETRIEVAL_CAPABILITY, "MONGODB_URI", "mongodb_uri"),
        ]

        for capability, env_var, token_field in cases:
            with self.subTest(capability=capability):
                settings = build_local_settings({env_var: "local_test_token"})

                self.assertEqual(getattr(settings.provider_tokens, token_field), "local_test_token")
                self.assertTrue(settings.is_capability_available(capability))
                unrelated_capabilities = [
                    other_capability
                    for other_capability, _, _ in cases
                    if other_capability != capability
                ]
                self.assertFalse(settings.is_capability_available(unrelated_capabilities[0]))

    def test_false_like_capability_enablement_disables_token_backed_capability(self) -> None:
        for false_like_value in ["0", "false", "no", "off", "disabled"]:
            with self.subTest(false_like_value=false_like_value):
                settings = build_local_settings(
                    {
                        "GITHUB_TOKEN": "ghp_local_test_token",
                        "SUPP_BRO_ENABLE_GITHUB_ISSUES": false_like_value,
                    }
                )

                status = settings.capability_status(GITHUB_ISSUES_CAPABILITY)
                self.assertFalse(status.available)
                self.assertFalse(status.enabled)
                self.assertTrue(status.token_configured)

    def test_unknown_provider_keys_are_ignored(self) -> None:
        settings = build_local_settings({"UNRELATED_PROVIDER_TOKEN": "ignored"})

        self.assertFalse(settings.is_capability_available(GITHUB_ISSUES_CAPABILITY))
        self.assertFalse(settings.is_capability_available(STACKOVERFLOW_SEARCH_CAPABILITY))

    def test_capability_enabled_mapping_is_snapshotted(self) -> None:
        enabled = {GITHUB_ISSUES_CAPABILITY: True}
        settings = LocalSettings(capability_enabled=enabled)

        enabled[GITHUB_ISSUES_CAPABILITY] = False

        self.assertTrue(settings.capability_status(GITHUB_ISSUES_CAPABILITY).enabled)

    def test_repr_and_availability_summary_do_not_expose_token_values(self) -> None:
        token = "ghp_local_test_token"
        settings = build_local_settings({"GITHUB_TOKEN": token})

        rendered_settings = repr(settings)
        rendered_summary = repr(settings.availability_summary())

        self.assertNotIn(token, rendered_settings)
        self.assertNotIn(token, rendered_summary)
        self.assertIn("token_configured=True", rendered_summary)


if __name__ == "__main__":
    unittest.main()
