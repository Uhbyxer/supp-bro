from __future__ import annotations

import unittest


class PackageImportsTest(unittest.TestCase):
    def test_package_imports(self) -> None:
        import supp_bro
        import supp_bro.domain

        self.assertIs(supp_bro.domain.WorkflowState, supp_bro.domain.WorkflowState)

    def test_top_level_all_exports_domain(self) -> None:
        namespace: dict[str, object] = {}
        exec("from supp_bro import *", namespace)

        self.assertIn("domain", namespace)
        self.assertTrue(hasattr(namespace["domain"], "WorkflowState"))
