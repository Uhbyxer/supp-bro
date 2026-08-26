"""Canonical workflow route names and brownfield route mapping."""

from __future__ import annotations

from typing import Final, Literal, cast

Hw5Route = Literal[
    "docs_question",
    "known_issue_question",
    "report_new_issue",
    "community_troubleshooting",
    "clarification",
]
ProductRoute = Literal["docs_answer", "issue_investigation", "community_lookup", "clarification"]

DOCS_ANSWER: Final[ProductRoute] = "docs_answer"
ISSUE_INVESTIGATION: Final[ProductRoute] = "issue_investigation"
COMMUNITY_LOOKUP: Final[ProductRoute] = "community_lookup"
CLARIFICATION: Final[ProductRoute] = "clarification"

PRODUCT_ROUTES: Final[tuple[ProductRoute, ...]] = (
    DOCS_ANSWER,
    ISSUE_INVESTIGATION,
    COMMUNITY_LOOKUP,
    CLARIFICATION,
)

HW5_TO_WORKFLOW_ROUTE: Final[dict[Hw5Route, ProductRoute]] = {
    "docs_question": DOCS_ANSWER,
    "known_issue_question": ISSUE_INVESTIGATION,
    "report_new_issue": CLARIFICATION,
    "community_troubleshooting": COMMUNITY_LOOKUP,
    "clarification": CLARIFICATION,
}


def map_hw5_route(route: object) -> ProductRoute:
    """Map an HW5 classifier route to the canonical product workflow route."""
    if not isinstance(route, str):
        return CLARIFICATION
    normalized = route.strip().lower()
    if normalized not in HW5_TO_WORKFLOW_ROUTE:
        return CLARIFICATION
    return HW5_TO_WORKFLOW_ROUTE[cast(Hw5Route, normalized)]
