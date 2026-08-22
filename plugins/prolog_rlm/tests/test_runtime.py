from __future__ import annotations

import importlib.util
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


runtime = load_module("prolog_rlm_runtime", "helpers/runtime.py")


class RuntimeTests(unittest.TestCase):
    def test_build_default_rlm_argv_is_structured(self):
        argv = runtime.build_rlm_argv(query="solve this")
        self.assertEqual(argv[:2], ["rlm", "solve this"])
        self.assertIn("--json", argv)
        self.assertNotIn("-g", argv)
        self.assertNotIn("consult", argv)

    def test_context_and_openrouter_model_are_forwarded(self):
        argv = runtime.build_rlm_argv(
            query="answer", context="observed fact", model="openrouter/free"
        )
        self.assertIn("--context", argv)
        self.assertIn("observed fact", argv)
        self.assertIn("--model", argv)
        self.assertIn("openrouter/free", argv)

    def test_custom_endpoint_uses_env_name_not_secret(self):
        argv = runtime.build_rlm_argv(
            query="answer",
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            model="local-model",
            credential_env="LOCAL_MODEL_KEY",
        )
        self.assertIn("--credential-env", argv)
        self.assertIn("LOCAL_MODEL_KEY", argv)
        self.assertNotIn("secret-value", argv)

    def test_no_credential_requires_custom_endpoint(self):
        with self.assertRaisesRegex(ValueError, "custom endpoint"):
            runtime.build_rlm_argv(query="answer", no_credential=True)

    def test_invalid_credential_env_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "environment-variable"):
            runtime.build_rlm_argv(
                query="answer",
                endpoint="https://example.invalid/v1/chat/completions",
                credential_env="BAD-NAME",
            )

    def test_non_http_endpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "http"):
            runtime.build_rlm_argv(query="answer", endpoint="file:///tmp/socket")

    def test_query_and_context_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "query exceeds"):
            runtime.build_rlm_argv(query="x" * (runtime.MAX_QUERY_CHARS + 1))
        with self.assertRaisesRegex(ValueError, "context exceeds"):
            runtime.build_rlm_argv(
                query="answer", context="x" * (runtime.MAX_CONTEXT_CHARS + 1)
            )

    def test_command_for_uses_fixed_public_entrypoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            entry = repo / "bin" / "prolog-rlm.pl"
            entry.parent.mkdir(parents=True)
            entry.write_text(":- halt.\n", encoding="utf-8")
            with patch.dict(os.environ, {"A0_PROLOG_RLM_REPO": str(repo)}, clear=False):
                with patch.object(runtime.shutil, "which", return_value="/usr/bin/swipl"):
                    command, cwd = runtime.command_for(["rlm", "question", "--json"])
            self.assertEqual(cwd, repo)
            self.assertEqual(command[:4], ["/usr/bin/swipl", "-q", "-s", str(entry)])
            self.assertEqual(command[4:], ["--", "rlm", "question", "--json"])


if __name__ == "__main__":
    unittest.main()
