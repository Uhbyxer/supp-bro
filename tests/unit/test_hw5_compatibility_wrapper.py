from __future__ import annotations

import sys
import unittest
from pathlib import Path

from supp_bro.domain.contracts import ToolRequest
from supp_bro.domain.support_intent import classify_support_intent
from supp_bro.tools import build_tool_request, validate_tool_request

HW5_DIR = Path(__file__).resolve().parents[2] / "scripts" / "hw5"
if str(HW5_DIR) not in sys.path:
    sys.path.insert(0, str(HW5_DIR))

import external_tool_router  # noqa: E402


class Hw5CompatibilityWrapperTest(unittest.TestCase):
    def test_re_exports_package_tool_request_and_helpers(self) -> None:
        self.assertIs(external_tool_router.ToolRequest, ToolRequest)
        self.assertIs(external_tool_router.classify_support_intent, classify_support_intent)
        self.assertIs(external_tool_router.build_tool_request, build_tool_request)
        self.assertIs(external_tool_router.validate_tool_request, validate_tool_request)

    def test_old_import_path_keeps_request_behavior(self) -> None:
        request = external_tool_router.build_tool_request(
            route="docs_question",
            question="Can I get exactly once delivery?",
            repo="debezium/dbz",
            issue_number=None,
            allow_external_community_search=False,
        )

        self.assertEqual(request.tool_name, "none")
        self.assertEqual(request.tool_type, "read")
        self.assertEqual(request.payload, {})
        self.assertFalse(request.confirmed)


if __name__ == "__main__":
    unittest.main()
