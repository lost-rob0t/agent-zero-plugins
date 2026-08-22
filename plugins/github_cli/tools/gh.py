from __future__ import annotations

import asyncio
import os
import re
import shutil
import uuid
from typing import Any

from helpers.print_style import PrintStyle
from helpers.tool import Response, Tool
from usr.plugins.github_cli.helpers.gates import config_dir, consume_gate, create_gate, state_dir
from usr.plugins.github_cli.helpers.policy import evaluate, validate_argv


MAX_OUTPUT_CHARS = 30000
TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s]+"),
]


class Gh(Tool):
    async def before_execution(self, **kwargs: Any):
        self.log = self.get_log_object()
        safe = _safe_log_args(self.args)
        PrintStyle(
            font_color="#1B4F72",
            padding=True,
            background_color="white",
            bold=True,
        ).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        PrintStyle(font_color="#85C1E9").print(
            f"Action: {safe['action']} | Operation: {safe['operation']} | "
            f"argc: {safe['argc']} | gate: {safe['gate']}"
        )

    def get_log_object(self):
        pre_id = str(uuid.uuid4())
        heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}'"
        return self.agent.context.log.log(
            type="tool",
            heading=heading,
            content="",
            kvps=_safe_log_args(self.args),
            _tool_name=self.name,
            id=pre_id,
        )

    async def execute(
        self,
        action: str = "status",
        argv: list[str] | None = None,
        gate: str = "",
        timeout_seconds: int = 120,
        **kwargs: Any,
    ) -> Response:
        action = str(action or self.method or "status").strip().lower()

        if action in {"status", "doctor"}:
            return await self._status()

        if action not in {"prepare", "run"}:
            return Response(
                message="Unknown action. Supported actions: status, prepare, run.",
                break_loop=False,
            )

        try:
            clean_argv = validate_argv(argv or [])
        except ValueError as exc:
            return Response(message=f"GitHub CLI policy rejected argv: {exc}", break_loop=False)

        policy = evaluate(clean_argv)
        if not policy.allowed:
            return Response(message=f"GitHub CLI policy denied command: {policy.reason}", break_loop=False)

        if action == "prepare":
            if not policy.mutation:
                return Response(
                    message=(
                        f"RAGE analyze: {_operation(clean_argv)} is read-only. "
                        "No execution gate is required; call gh action=run with the same argv."
                    ),
                    break_loop=False,
                )

            record = create_gate(self.agent.context.id, clean_argv)
            return Response(
                message=(
                    f"RAGE analyze: {_operation(clean_argv)} changes GitHub state. "
                    f"Gate admitted for this exact command: {record['gate_id']} "
                    f"(expires_at={record['expires_at']}). "
                    "Execute with gh action=run, identical argv, and this gate id."
                ),
                break_loop=False,
            )

        if policy.mutation:
            if not gate:
                return Response(
                    message=(
                        f"RAGE gate required for {_operation(clean_argv)}. "
                        "Call gh action=prepare first, then run the exact same argv with its one-time gate id."
                    ),
                    break_loop=False,
                )
            try:
                consume_gate(self.agent.context.id, gate, clean_argv)
            except ValueError as exc:
                return Response(message=f"RAGE gate rejected execution: {exc}", break_loop=False)

        timeout = _bounded_timeout(timeout_seconds)
        result = await _run_gh(clean_argv, timeout)
        phase = "execute/evaluate" if policy.mutation else "evaluate"
        message = (
            f"RAGE {phase}: {_operation(clean_argv)} exit={result['returncode']}.\n"
            f"stdout:\n{result['stdout'] or '(empty)'}\n"
            f"stderr:\n{result['stderr'] or '(empty)'}\n"
            "Recurse from this observed result; do not assume success from intent alone."
        )
        return Response(message=message, break_loop=False)

    async def _status(self) -> Response:
        gh_path = shutil.which("gh")
        cfg = config_dir()
        state = state_dir()
        if not gh_path:
            return Response(
                message=(
                    "GitHub CLI plugin is installed, but gh is not present. "
                    "Run the plugin execute.py setup from Agent Zero's Plugins UI. "
                    f"Persistent state directory: {state}"
                ),
                break_loop=False,
            )

        version = await _run_gh(["--version"], 20)
        auth = await _run_gh(["auth", "status"], 30)
        message = (
            f"gh={gh_path}\n"
            f"GH_CONFIG_DIR={cfg}\n"
            f"state_dir={state}\n"
            f"version_exit={version['returncode']}\n{version['stdout'] or version['stderr']}\n"
            f"auth_exit={auth['returncode']}\n{auth['stdout'] or auth['stderr']}"
        )
        return Response(message=_redact(message), break_loop=False)


async def _run_gh(argv: list[str], timeout_seconds: int) -> dict[str, Any]:
    gh_path = shutil.which("gh")
    if not gh_path:
        return {
            "returncode": 127,
            "stdout": "",
            "stderr": "gh executable not found; run plugin setup first.",
        }

    cfg = config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cfg, 0o700)
    except OSError:
        pass

    env = os.environ.copy()
    env["GH_CONFIG_DIR"] = str(cfg)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["GH_PAGER"] = "cat"
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)

    process = await asyncio.create_subprocess_exec(
        gh_path,
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
        returncode = int(process.returncode or 0)
    except asyncio.TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        returncode = 124
        stderr_bytes += f"\ncommand timed out after {timeout_seconds}s".encode()

    stdout = _redact(stdout_bytes.decode("utf-8", errors="replace"))[-MAX_OUTPUT_CHARS:]
    stderr = _redact(stderr_bytes.decode("utf-8", errors="replace"))[-MAX_OUTPUT_CHARS:]
    return {"returncode": returncode, "stdout": stdout.strip(), "stderr": stderr.strip()}


def _safe_log_args(args: dict[str, Any]) -> dict[str, Any]:
    argv = args.get("argv")
    argv_list = argv if isinstance(argv, list) else []
    return {
        "action": str(args.get("action") or "status"),
        "operation": _operation(argv_list) if argv_list else "gh status",
        "argc": len(argv_list),
        "gate": "present" if args.get("gate") else "none",
        "timeout_seconds": args.get("timeout_seconds", 120),
    }


def _operation(argv: list[str]) -> str:
    if not argv:
        return "gh"
    root = argv[0]
    if root in {"api", "browse", "status"}:
        return f"gh {root}"
    if len(argv) > 1 and not argv[1].startswith("-"):
        return f"gh {root} {argv[1]}"
    return f"gh {root}"


def _bounded_timeout(value: int) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = 120
    return max(1, min(timeout, 600))


def _redact(text: str) -> str:
    result = text
    for pattern in TOKEN_PATTERNS:
        if pattern.groups:
            result = pattern.sub(r"\1[REDACTED]", result)
        else:
            result = pattern.sub("[REDACTED]", result)
    return result
