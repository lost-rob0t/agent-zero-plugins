from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POLICY_PATH = Path(__file__).resolve().parents[1] / "helpers" / "policy.py"


def load_policy():
    name = "github_cli_policy_edges"
    spec = importlib.util.spec_from_file_location(name, POLICY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {POLICY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load_policy()


class PolicyEdgeTests(unittest.TestCase):
    def test_compact_equals_delete_method_is_denied_for_repo(self):
        result = policy.evaluate(["api", "-X=DELETE", "repos/owner/repo"])
        self.assertFalse(result.allowed)
        self.assertIn("delet", result.reason.lower())

    def test_compact_delete_method_is_denied_for_repo(self):
        result = policy.evaluate(["api", "-XDELETE", "repos/owner/repo"])
        self.assertFalse(result.allowed)

    def test_compact_patch_method_is_a_gated_mutation(self):
        result = policy.evaluate(["api", "-X=PATCH", "repos/owner/repo"])
        self.assertTrue(result.allowed)
        self.assertTrue(result.mutation)


if __name__ == "__main__":
    unittest.main()
