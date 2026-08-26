from __future__ import annotations

import unittest

from supp_bro.domain.routes import HW5_TO_WORKFLOW_ROUTE, PRODUCT_ROUTES, map_hw5_route


class DomainRoutesTest(unittest.TestCase):
    def test_product_route_values_match_hw6_names(self) -> None:
        self.assertEqual(
            PRODUCT_ROUTES,
            (
                "docs_answer",
                "issue_investigation",
                "community_lookup",
                "clarification",
            ),
        )

    def test_hw5_routes_map_to_product_routes(self) -> None:
        self.assertEqual(
            HW5_TO_WORKFLOW_ROUTE,
            {
                "docs_question": "docs_answer",
                "known_issue_question": "issue_investigation",
                "report_new_issue": "clarification",
                "community_troubleshooting": "community_lookup",
                "clarification": "clarification",
            },
        )

    def test_route_mapping_normalizes_case_and_whitespace(self) -> None:
        self.assertEqual(map_hw5_route(" Known_Issue_Question "), "issue_investigation")

    def test_unknown_hw5_route_maps_to_clarification(self) -> None:
        self.assertEqual(map_hw5_route("not_a_known_route"), "clarification")
        self.assertEqual(map_hw5_route(None), "clarification")
