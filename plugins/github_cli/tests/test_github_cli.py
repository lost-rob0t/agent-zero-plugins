from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = PLUGIN_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load_module("github_cli_policy", "helpers/policy.py")
gates = load_module("github_cli_gates", "helpers/gates.py")


class PolicyTests(unittest.TestCase):
    def test_repo_create_is_allowed_mutation(self):
        result = policy.evaluate(["repo", "create", "owner/repo", "--private"])
        self.assertTrue(result.allowed)
        self.assertTrue(result.mutation)

    def test_repo_view_is_read_only(self):
        result = policy.evaluate(["repo", "view", "owner/repo"])
        self.assertTrue(result.allowed)
        self.assertFalse(result.mutation)

    def test_repo_delete_is_hard_denied(self):
        result = policy.evaluate(["repo", "delete", "owner/repo", "--yes"])
        self.assertFalse(result.allowed)
        self.assertIn("deletion", result.reason.lower())

    def test_rest_repo_delete_is_hard_denied(self):
        result = policy.evaluate(["api", "--method", "DELETE", "repos/owner/repo"])
        self.assertFalse(result.allowed)

    def test_rest_repo_delete_with_boolean_flag_is_hard_denied(self):
        result = policy.evaluate(
            ["api", "--method", "DELETE", "--paginate", "repos/owner/repo"]
        )
        self.assertFalse(result.allowed)

    def test_enterprise_rest_repo_delete_is_hard_denied(self):
        result = policy.evaluate(
            ["api", "-XDELETE", "https://github.example/api/v3/repos/owner/repo"]
        )
        self.assertFalse(result.allowed)

    def test_non_repo_rest_delete_remains_gated(self):
        result = policy.evaluate(["api", "--method", "DELETE", "repos/owner/repo/issues/1"])
        self.assertTrue(result.allowed)
        self.assertTrue(result.mutation)

    def test_graphql_delete_repository_is_hard_denied(self):
        result = policy.evaluate(
            [
                "api",
                "graphql",
                "-f",
                "query=mutation { deleteRepository(input: {repositoryId: \"x\"}) { clientMutationId } }",
            ]
        )
        self.assertFalse(result.allowed)

    def test_uninspectable_graphql_file_is_denied(self):
        result = policy.evaluate(["api", "graphql", "-f", "query=@mutation.graphql"])
        self.assertFalse(result.allowed)

    def test_api_get_is_read_only(self):
        result = policy.evaluate(["api", "repos/owner/repo"])
        self.assertTrue(result.allowed)
        self.assertFalse(result.mutation)

    def test_api_post_requires_gate(self):
        result = policy.evaluate(["api", "repos/owner/repo/issues", "-f", "title=test"])
        self.assertTrue(result.allowed)
        self.assertTrue(result.mutation)

    def test_alias_or_extension_root_is_denied(self):
        self.assertFalse(policy.evaluate(["alias", "list"]).allowed)
        self.assertFalse(policy.evaluate(["extension", "list"]).allowed)
        self.assertFalse(policy.evaluate(["my-shell-alias", "arg"]).allowed)

    def test_auth_token_exposure_is_denied(self):
        self.assertFalse(policy.evaluate(["auth", "token"]).allowed)
        self.assertFalse(policy.evaluate(["auth", "status", "--show-token"]).allowed)


class GateTests(unittest.TestCase):
    def test_gate_is_exact_context_bound_one_time_and_does_not_store_argv(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"A0_GITHUB_CLI_STATE_DIR": temporary}, clear=False):
                argv = ["repo", "create", "owner/secret-name", "--private"]
                record = gates.create_gate("ctx-a", argv)
                gate_id = str(record["gate_id"])

                gate_path = Path(temporary) / "gates" / f"{gate_id}.json"
                stored = json.loads(gate_path.read_text(encoding="utf-8"))
                self.assertNotIn("argv", stored)
                self.assertNotIn("secret-name", gate_path.read_text(encoding="utf-8"))

                with self.assertRaisesRegex(ValueError, "another Agent Zero context"):
                    gates.consume_gate("ctx-b", gate_id, argv)

                with self.assertRaisesRegex(ValueError, "does not match"):
                    gates.consume_gate("ctx-a", gate_id, ["repo", "create", "owner/other"])

                consumed = gates.consume_gate("ctx-a", gate_id, argv)
                self.assertIsNotNone(consumed["consumed_at"])

                with self.assertRaisesRegex(ValueError, "already consumed"):
                    gates.consume_gate("ctx-a", gate_id, argv)


if __name__ == "__main__":
    unittest.main()
