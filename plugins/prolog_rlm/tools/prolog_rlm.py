from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from helpers.print_style import PrintStyle
from helpers.tool import Response, Tool
from usr.plugins.prolog_rlm.helpers.runtime import (
    bounded_timeout,
    build_rlm_argv,
    command_for,
    entrypoint,
    repo_dir,
    resolve_runtime,
)


MAX_OUTPUT_CHARS = 40_000


class PrologRlm(Tool):
    async def before_execution(self, **kwargs: Any):
        self.log = self.get_log_object()
        safe = _safe_log_args(self.args)
        PrintStyle(
            font_color="#4A235A",
            padding=True,
            background_color="white",
            bold=True,
        ).print(f"{self.agent.agent_name}: Using tool '{self.name}'")
        PrintStyle(font_color="#884EA0").print(
            f"Action: {safe['action']} | query_chars: {safe['query_chars']} | "
            f"context_chars: {safe['context_chars']} | model: {safe['model']}"
        )

    def get_log_object(self):
        pre_id = str(uuid.uuid4())
        heading = f"icon://psychology {self.agent.agent_name}: Using tool '{self.name}'"
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
        action: str = "reason",
        query: str = "",
        context: str = "",
        model: str = "",
        endpoint: str = "",
        credential_env: str = "OPENAI_API_KEY",
        no_credential: bool = False,
        max_tokens: int = 256,
        max_cost_usd: float = 0.25,
        time_limit: float = 120.0,
        context_bytes: int = 8192,
        timeout_seconds: int = 150,
        **kwargs: Any,
    ) -> Response:
        action = str(action or self.method or "reason").strip().lower()
        if action in {"status", "doctor"}:
            return await self._status()
        if action not in {"reason", "run"}:
            return Response(
                message="Unknown action. Supported actions: status, reason.",
                break_loop=False,
            )

        try:
            argv = build_rlm_argv(
                query=query,
                context=context,
                model=model,
                endpoint=endpoint,
                credential_env=credential_env,
                no_credential=bool(no_credential),
                max_tokens=max_tokens,
                max_cost_usd=max_cost_usd,
                time_limit=time_limit,
                context_bytes=context_bytes,
            )
            command, cwd = command_for(argv)
        except (RuntimeError, ValueError) as exc:
            return Response(message=f"prolog-rlm bridge rejected request: {exc}", break_loop=False)

        result = await _run(command, cwd, bounded_timeout(timeout_seconds))
        payload = _decode_payload(result["stdout"])
        if payload is not None:
            body = json.dumps(payload, indent=2, sort_keys=True)
        else:
            body = result["stdout"] or "(empty)"

        message = (
            f"prolog-rlm exit={result['returncode']}\n"
            f"result:\n{body}\n"
            f"stderr:\n{result['stderr'] or '(empty)'}\n"
            "Treat this as recursive reasoning evidence. Verify real-world state and external effects separately."
        )
        return Response(message=message[-MAX_OUTPUT_CHARS:], break_loop=False)

    async def _status(self) -> Response:
        try:
            swipl, repo, entry = resolve_runtime()
        except RuntimeError as exc:
            return Response(
                message=(
                    f"prolog-rlm bridge is not ready: {exc}\n"
                    f"expected_repo={repo_dir()}\nexpected_entrypoint={entrypoint()}"
                ),
                break_loop=False,
            )

        version = await _run([swipl, "--version"], repo, 20)
        smoke = await _run([swipl, "-q", "-s", str(entry), "--", "help"], repo, 30)
        return Response(
            message=(
                f"swipl={swipl}\nrepo={repo}\nentrypoint={entry}\n"
                f"version_exit={version['returncode']}\n{version['stdout'] or version['stderr']}\n"
                f"cli_help_exit={smoke['returncode']}\n"
                f"{(smoke['stdout'] or smoke['stderr'])[:4000]}"
            ),
            break_loop=False,
        )


async def _run(command: list[str], cwd, timeout_seconds: int) -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
        returncode = int(process.returncode or 0)
    except asyncio.TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        returncode = 124
        stderr_bytes += f"\nbridge timed out after {timeout_seconds}s".encode()

    stdout = stdout_bytes.decode("utf-8", errors="replace")[-MAX_OUTPUT_CHARS:].strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace")[-MAX_OUTPUT_CHARS:].strip()
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


def _decode_payload(stdout: str) -> Any | None:
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _safe_log_args(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    context = args.get("context")
    model = args.get("model")
    return {
        "action": str(args.get("action") or "reason"),
        "query_chars": len(query) if isinstance(query, str) else 0,
        "context_chars": len(context) if isinstance(context, str) else 0,
        "model": str(model)[:128] if model else "default",
        "custom_endpoint": bool(args.get("endpoint")),
        "credential_env": str(args.get("credential_env") or "OPENAI_API_KEY")[:128],
        "timeout_seconds": args.get("timeout_seconds", 150),
    }
