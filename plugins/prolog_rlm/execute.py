from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


STATE_DIR = Path(os.environ.get("A0_PROLOG_RLM_STATE_DIR", "/a0/usr/state/prolog_rlm"))
REPO_DIR = Path(os.environ.get("A0_PROLOG_RLM_REPO", str(STATE_DIR / "repo")))
REPO_URL = os.environ.get("A0_PROLOG_RLM_REPO_URL", "https://github.com/lost-rob0t/prolog-rlm.git")
REF = os.environ.get("A0_PROLOG_RLM_REF", "main")


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    missing = [name for name in ("git", "swipl") if not shutil.which(name)]
    if missing:
        print(f"ERROR: missing required executables: {', '.join(missing)}")
        print("Install Git and SWI-Prolog, then rerun this setup.")
        return 1

    if (REPO_DIR / ".git").is_dir():
        print(f"Updating persisted prolog-rlm checkout at {REPO_DIR}")
        if _run(["git", "-C", str(REPO_DIR), "fetch", "--depth", "1", "origin", REF]).returncode:
            return 1
        if _run(["git", "-C", str(REPO_DIR), "reset", "--hard", "FETCH_HEAD"]).returncode:
            return 1
    elif REPO_DIR.exists():
        print(f"ERROR: {REPO_DIR} exists but is not a Git checkout")
        return 1
    else:
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        print(f"Cloning {REPO_URL} ({REF}) into {REPO_DIR}")
        if _run(
            ["git", "clone", "--depth", "1", "--branch", REF, REPO_URL, str(REPO_DIR)]
        ).returncode:
            return 1

    entry = REPO_DIR / "bin" / "prolog-rlm.pl"
    if not entry.is_file():
        print(f"ERROR: expected CLI entrypoint is missing: {entry}")
        return 1

    smoke = _run(["swipl", "-q", "-s", str(entry), "--", "help"], cwd=REPO_DIR)
    if smoke.returncode:
        print("ERROR: prolog-rlm CLI smoke check failed")
        return smoke.returncode

    revision = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()
    print(f"prolog-rlm ready: repo={REPO_DIR} revision={revision or 'unknown'}")
    print("Provider credentials remain environment-only; OPENROUTER_API_KEY is used by the default provider.")
    return 0


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, check=False)
    if result.returncode:
        print(f"ERROR: command failed with exit {result.returncode}: {command[0]}")
    return result


if __name__ == "__main__":
    sys.exit(main())
