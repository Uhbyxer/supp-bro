"""Local settings boundary for optional provider-backed capabilities."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

CapabilityName = str

GITHUB_ISSUES_CAPABILITY = "github_issues"
STACKOVERFLOW_SEARCH_CAPABILITY = "stackoverflow_search"
OPENAI_EMBEDDINGS_CAPABILITY = "openai_embeddings"
PINECONE_RETRIEVAL_CAPABILITY = "pinecone_retrieval"
MONGO_RETRIEVAL_CAPABILITY = "mongo_retrieval"

FALSE_LIKE_VALUES = {"0", "false", "no", "off", "disabled"}

CAPABILITY_TOKEN_ENV_VARS: Mapping[CapabilityName, str] = MappingProxyType(
    {
        GITHUB_ISSUES_CAPABILITY: "GITHUB_TOKEN",
        STACKOVERFLOW_SEARCH_CAPABILITY: "STACKOVERFLOW_TOKEN",
        OPENAI_EMBEDDINGS_CAPABILITY: "OPENAI_API_KEY",
        PINECONE_RETRIEVAL_CAPABILITY: "PINECONE_API_KEY",
        MONGO_RETRIEVAL_CAPABILITY: "MONGODB_URI",
    }
)

CAPABILITY_ENABLE_ENV_VARS: Mapping[CapabilityName, str] = MappingProxyType(
    {
        GITHUB_ISSUES_CAPABILITY: "SUPP_BRO_ENABLE_GITHUB_ISSUES",
        STACKOVERFLOW_SEARCH_CAPABILITY: "SUPP_BRO_ENABLE_STACKOVERFLOW_SEARCH",
        OPENAI_EMBEDDINGS_CAPABILITY: "SUPP_BRO_ENABLE_OPENAI_EMBEDDINGS",
        PINECONE_RETRIEVAL_CAPABILITY: "SUPP_BRO_ENABLE_PINECONE_RETRIEVAL",
        MONGO_RETRIEVAL_CAPABILITY: "SUPP_BRO_ENABLE_MONGO_RETRIEVAL",
    }
)


@dataclass(frozen=True)
class ProviderTokens:
    """Explicit adapter-only access to local provider credentials."""

    github_token: str | None = field(default=None, repr=False)
    stackoverflow_token: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    pinecone_api_key: str | None = field(default=None, repr=False)
    mongodb_uri: str | None = field(default=None, repr=False)

    def token_for(self, capability: CapabilityName) -> str | None:
        token_fields = {
            GITHUB_ISSUES_CAPABILITY: self.github_token,
            STACKOVERFLOW_SEARCH_CAPABILITY: self.stackoverflow_token,
            OPENAI_EMBEDDINGS_CAPABILITY: self.openai_api_key,
            PINECONE_RETRIEVAL_CAPABILITY: self.pinecone_api_key,
            MONGO_RETRIEVAL_CAPABILITY: self.mongodb_uri,
        }
        return token_fields.get(capability)


@dataclass(frozen=True)
class CapabilityAvailability:
    capability: CapabilityName
    available: bool
    enabled: bool
    token_configured: bool


@dataclass(frozen=True)
class LocalSettings:
    provider_tokens: ProviderTokens = field(default_factory=ProviderTokens, repr=False)
    capability_enabled: Mapping[CapabilityName, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_enabled", MappingProxyType(dict(self.capability_enabled)))

    def is_capability_available(self, capability: CapabilityName) -> bool:
        return self.capability_status(capability).available

    def capability_status(self, capability: CapabilityName) -> CapabilityAvailability:
        enabled = self.capability_enabled.get(capability, True)
        token_configured = bool(self.provider_tokens.token_for(capability))
        return CapabilityAvailability(
            capability=capability,
            available=enabled and token_configured,
            enabled=enabled,
            token_configured=token_configured,
        )

    def availability_summary(self) -> dict[CapabilityName, CapabilityAvailability]:
        return {capability: self.capability_status(capability) for capability in CAPABILITY_TOKEN_ENV_VARS}


def build_local_settings(env: Mapping[str, str] | None = None) -> LocalSettings:
    source = os.environ if env is None else env
    tokens = ProviderTokens(
        github_token=_clean_token(source.get("GITHUB_TOKEN")),
        stackoverflow_token=_clean_token(source.get("STACKOVERFLOW_TOKEN")),
        openai_api_key=_clean_token(source.get("OPENAI_API_KEY")),
        pinecone_api_key=_clean_token(source.get("PINECONE_API_KEY")),
        mongodb_uri=_clean_token(source.get("MONGODB_URI")),
    )
    enabled = {
        capability: _is_enabled(source.get(env_var))
        for capability, env_var in CAPABILITY_ENABLE_ENV_VARS.items()
    }
    return LocalSettings(provider_tokens=tokens, capability_enabled=enabled)


def _clean_token(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _is_enabled(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() not in FALSE_LIKE_VALUES
