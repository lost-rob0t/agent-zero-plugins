from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path


DEFAULT_STATE_DIR = Path("/a0/usr/state/github_cli")
GATE_TTL_SECONDS = 15 * 60


def state_dir() -> Path:
    return Path(os.environ.get("A0_GITHUB_CLI_STATE_DIR", str(DEFAULT_STATE_DIR)))


def config_dir() -> Path:
    override = os.environ.get("GH_CONFIG_DIR")
    if override:
        return Path(override)

    env_path = state_dir() / "env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "GH_CONFIG_DIR" and value.strip():
                return Path(value.strip())
    except OSError:
        pass
    return state_dir() / "gh"


def create_gate(context_id: str, argv: list[str]) -> dict[str, object]:
    now = int(time.time())
    gate_id = uuid.uuid4().hex
    record = {
        "version": 1,
        "gate_id": gate_id,
        "context_id": context_id,
        "argv_sha256": argv_digest(argv),
        "created_at": now,
        "expires_at": now + GATE_TTL_SECONDS,
        "consumed_at": None,
    }
    _write_gate(record)
    return record


def consume_gate(context_id: str, gate_id: str, argv: list[str]) -> dict[str, object]:
    path = _gate_path(gate_id)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("RAGE gate not found") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("RAGE gate is unreadable") from exc

    if record.get("context_id") != context_id:
        raise ValueError("RAGE gate belongs to another Agent Zero context")
    if record.get("consumed_at") is not None:
        raise ValueError("RAGE gate was already consumed")
    if int(record.get("expires_at") or 0) < int(time.time()):
        raise ValueError("RAGE gate expired")
    if record.get("argv_sha256") != argv_digest(argv):
        raise ValueError("RAGE gate does not match the requested gh command")

    record["consumed_at"] = int(time.time())
    _write_gate(record)
    return record


def argv_digest(argv: list[str]) -> str:
    payload = json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _gate_path(gate_id: str) -> Path:
    if not gate_id or any(character not in "0123456789abcdef" for character in gate_id.lower()):
        raise ValueError("Invalid RAGE gate id")
    return state_dir() / "gates" / f"{gate_id}.json"


def _write_gate(record: dict[str, object]) -> None:
    gate_id = str(record["gate_id"])
    path = _gate_path(gate_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
