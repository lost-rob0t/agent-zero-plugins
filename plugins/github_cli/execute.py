from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


STATE_DIR = Path(os.environ.get("A0_GITHUB_CLI_STATE_DIR", "/a0/usr/state/github_cli"))
CONFIG_DIR = STATE_DIR / "gh"
ENV_FILE = STATE_DIR / "env"


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _chmod(STATE_DIR, 0o700)
    _chmod(CONFIG_DIR, 0o700)

    ENV_FILE.write_text(f"GH_CONFIG_DIR={CONFIG_DIR}\n", encoding="utf-8")
    _chmod(ENV_FILE, 0o600)

    _migrate_existing_config()

    if not shutil.which("gh"):
        code = _install_gh()
        if code != 0:
            return code

    print(f"gh: {shutil.which('gh')}")
    print(f"persistent GH_CONFIG_DIR: {CONFIG_DIR}")

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        code = _persist_token(token)
        if code != 0:
            return code
        print("GitHub authentication from environment was persisted into GH_CONFIG_DIR.")
    else:
        print("No GH_TOKEN/GITHUB_TOKEN found; existing persisted gh authentication was left unchanged.")

    status = _run(["gh", "auth", "status"], check=False)
    if status.returncode != 0:
        print("gh is installed but not authenticated yet.")
        print(
            "Authenticate interactively with: "
            f"GH_CONFIG_DIR={CONFIG_DIR} gh auth login"
        )
        return 0

    print("gh authentication status: OK")
    return 0


def _install_gh() -> int:
    installers = [
        ("apt-get", [["apt-get", "update"], ["apt-get", "install", "-y", "gh"]]),
        ("dnf", [["dnf", "install", "-y", "gh"]]),
        ("apk", [["apk", "add", "github-cli"]]),
        ("pacman", [["pacman", "-Sy", "--noconfirm", "github-cli"]]),
    ]

    for executable, commands in installers:
        if not shutil.which(executable):
            continue
        print(f"Installing gh with {executable}...")
        for command in commands:
            result = _run(command, check=False)
            if result.returncode != 0:
                print(f"ERROR: {' '.join(command)} failed with exit {result.returncode}")
                return result.returncode
        return 0 if shutil.which("gh") else 1

    print("ERROR: gh is missing and no supported package manager was found.")
    return 1


def _persist_token(token: str) -> int:
    env = os.environ.copy()
    env["GH_CONFIG_DIR"] = str(CONFIG_DIR)
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["GH_PROMPT_DISABLED"] = "1"

    process = subprocess.run(
        ["gh", "auth", "login", "--hostname", "github.com", "--with-token"],
        input=token,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if process.returncode != 0:
        print("ERROR: gh auth login failed while persisting the environment token.")
    return process.returncode


def _migrate_existing_config() -> None:
    old = Path.home() / ".config" / "gh"
    if not old.is_dir() or old.resolve() == CONFIG_DIR.resolve():
        return

    destination_hosts = CONFIG_DIR / "hosts.yml"
    source_hosts = old / "hosts.yml"
    if source_hosts.is_file() and not destination_hosts.exists():
        shutil.copy2(source_hosts, destination_hosts)
        _chmod(destination_hosts, 0o600)
        print(f"Migrated existing gh auth config from {source_hosts}")


def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GH_CONFIG_DIR"] = str(CONFIG_DIR)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    return subprocess.run(command, text=True, env=env, check=check)


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
