from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_STATE_DIR = Path("/a0/usr/state/prolog_rlm")
MAX_QUERY_CHARS = 32_000
MAX_CONTEXT_CHARS = 65_536
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def state_dir() -> Path:
    return Path(os.environ.get("A0_PROLOG_RLM_STATE_DIR", str(DEFAULT_STATE_DIR)))


def repo_dir() -> Path:
    return Path(os.environ.get("A0_PROLOG_RLM_REPO", str(state_dir() / "repo")))


def entrypoint() -> Path:
    return repo_dir() / "bin" / "prolog-rlm.pl"


def resolve_runtime() -> tuple[str, Path, Path]:
    swipl = shutil.which("swipl")
    if not swipl:
        raise RuntimeError("swipl executable not found; run plugin setup after installing SWI-Prolog")

    repo = repo_dir()
    entry = entrypoint()
    if not entry.is_file():
        raise RuntimeError(
            f"prolog-rlm entrypoint not found at {entry}; run the plugin execute.py setup"
        )
    return swipl, repo, entry


def build_rlm_argv(
    *,
    query: str,
    context: str = "",
    model: str = "",
    endpoint: str = "",
    credential_env: str = "OPENAI_API_KEY",
    no_credential: bool = False,
    max_tokens: int = 256,
    max_cost_usd: float = 0.25,
    time_limit: float = 120.0,
    context_bytes: int = 8192,
) -> list[str]:
    query = _bounded_text("query", query, MAX_QUERY_CHARS, required=True)
    context = _bounded_text("context", context, MAX_CONTEXT_CHARS, required=False)
    model = _bounded_text("model", model, 512, required=False)
    endpoint = _bounded_text("endpoint", endpoint, 2048, required=False)
    credential_env = _bounded_text(
        "credential_env", credential_env, 256, required=bool(endpoint and not no_credential)
    )

    max_tokens = _bounded_int("max_tokens", max_tokens, 1, 8192)
    context_bytes = _bounded_int("context_bytes", context_bytes, 1, MAX_CONTEXT_CHARS)
    max_cost_usd = _bounded_float("max_cost_usd", max_cost_usd, 0.0, 100.0)
    time_limit = _bounded_float("time_limit", time_limit, 1.0, 600.0)

    argv = [
        "rlm",
        query,
        "--json",
        "--max-tokens",
        str(max_tokens),
        "--max-cost",
        str(max_cost_usd),
        "--time-limit",
        str(time_limit),
        "--context-bytes",
        str(context_bytes),
    ]

    if context:
        argv.extend(["--context", context])
    if model:
        argv.extend(["--model", model])

    if endpoint:
        _validate_endpoint(endpoint)
        argv.extend(["--endpoint", endpoint])
        if no_credential:
            argv.append("--no-credential")
        else:
            if not _ENV_NAME.fullmatch(credential_env):
                raise ValueError("credential_env must be an environment-variable name")
            argv.extend(["--credential-env", credential_env])
    elif no_credential:
        raise ValueError("no_credential is only valid with a custom endpoint")

    return argv


def command_for(argv: list[str]) -> tuple[list[str], Path]:
    swipl, repo, entry = resolve_runtime()
    return [swipl, "-q", "-s", str(entry), "--", *argv], repo


def bounded_timeout(value: int | float) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = 150
    return max(1, min(timeout, 660))


def _bounded_text(name: str, value: object, limit: int, *, required: bool) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    if required and not text:
        raise ValueError(f"{name} is required")
    if len(text) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    if "\x00" in text:
        raise ValueError(f"{name} contains a NUL byte")
    return text


def _bounded_int(name: str, value: object, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def _bounded_float(name: str, value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint must be an absolute http(s) URL")
