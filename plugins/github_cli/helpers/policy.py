from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


ALLOWED_ROOTS = {
    "api",
    "attestation",
    "auth",
    "browse",
    "cache",
    "codespace",
    "gist",
    "issue",
    "label",
    "org",
    "pr",
    "project",
    "release",
    "repo",
    "ruleset",
    "run",
    "search",
    "secret",
    "ssh-key",
    "status",
    "variable",
    "workflow",
}

READ_ONLY = {
    "attestation": {"download", "trusted-root", "verify"},
    "auth": {"status"},
    "cache": {"list"},
    "codespace": {"list", "logs", "ports", "view"},
    "gist": {"clone", "list", "view"},
    "issue": {"list", "status", "view"},
    "label": {"list"},
    "org": {"list"},
    "pr": {"checks", "diff", "list", "status", "view"},
    "project": {"field-list", "item-list", "list", "view"},
    "release": {"download", "list", "view"},
    "repo": {"clone", "list", "view"},
    "ruleset": {"check", "list", "view"},
    "run": {"list", "view", "watch"},
    "secret": {"list"},
    "ssh-key": {"list"},
    "variable": {"get", "list"},
    "workflow": {"list", "view"},
}

READ_ONLY_ROOTS = {"browse", "search", "status"}


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    mutation: bool
    reason: str


def validate_argv(argv: list[str]) -> list[str]:
    if not isinstance(argv, list) or not argv:
        raise ValueError("argv must be a non-empty list")
    if len(argv) > 128:
        raise ValueError("argv contains too many arguments")

    clean: list[str] = []
    for item in argv:
        if not isinstance(item, str):
            raise ValueError("every argv item must be a string")
        if not item or "\x00" in item:
            raise ValueError("argv contains an empty or invalid argument")
        if len(item) > 16384:
            raise ValueError("argv argument is too large")
        clean.append(item)
    return clean


def evaluate(argv: list[str]) -> PolicyResult:
    argv = validate_argv(argv)
    root = argv[0]

    if root not in ALLOWED_ROOTS:
        return PolicyResult(
            allowed=False,
            mutation=False,
            reason="Only built-in gh command groups are allowed; aliases and extensions are not executable.",
        )

    secret_reason = _credential_exposure_reason(argv)
    if secret_reason:
        return PolicyResult(False, False, secret_reason)

    tunnel_reason = _execution_tunnel_reason(argv)
    if tunnel_reason:
        return PolicyResult(False, False, tunnel_reason)

    delete_reason = _repository_delete_reason(argv)
    if delete_reason:
        return PolicyResult(False, True, delete_reason)

    if root == "api":
        mutation = _api_is_mutation(argv)
        return PolicyResult(True, mutation, "GitHub API command accepted by policy.")

    if root in READ_ONLY_ROOTS:
        return PolicyResult(True, False, "Read-only gh command.")

    subcommand = _subcommand(argv)
    if subcommand and subcommand in READ_ONLY.get(root, set()):
        return PolicyResult(True, False, "Read-only gh command.")

    return PolicyResult(True, True, "State-changing gh command requires a RAGE gate.")


def _subcommand(argv: list[str]) -> str:
    for item in argv[1:]:
        if not item.startswith("-"):
            return item
    return ""


def _credential_exposure_reason(argv: list[str]) -> str:
    lowered = [item.lower() for item in argv]
    if argv[:2] == ["auth", "token"]:
        return "gh auth token is disabled because it exposes stored credentials."
    if argv and argv[0] == "auth" and "--show-token" in lowered:
        return "--show-token is disabled because it exposes stored credentials."
    return ""


def _execution_tunnel_reason(argv: list[str]) -> str:
    if argv[:2] == ["codespace", "ssh"]:
        return "gh codespace ssh is disabled because it provides arbitrary remote command execution."
    return ""


def _repository_delete_reason(argv: list[str]) -> str:
    if argv[:2] == ["repo", "delete"]:
        return "Repository deletion is permanently disabled by this plugin."

    if not argv or argv[0] != "api":
        return ""

    joined = " ".join(argv).lower()
    if "deleterepository" in joined:
        return "GraphQL deleteRepository is permanently disabled by this plugin."

    endpoint = _api_endpoint(argv)
    method = _api_method(argv)
    if method == "DELETE" and _is_repository_endpoint(endpoint):
        return "Deleting a repository through gh api is permanently disabled by this plugin."

    if _is_graphql_endpoint(endpoint) and _has_uninspectable_graphql_input(argv):
        return "GraphQL file/stdin input is disabled because repository-deletion policy cannot inspect it safely."

    return ""


def _api_method(argv: list[str]) -> str:
    method = "GET"
    for index, item in enumerate(argv[1:], start=1):
        if item in {"-X", "--method"} and index + 1 < len(argv):
            method = argv[index + 1].upper()
        elif item.startswith("--method="):
            method = item.split("=", 1)[1].upper()
        elif item.startswith("-X") and len(item) > 2:
            method = item[2:].upper()

    if method == "GET" and any(
        item in {"-f", "--raw-field", "-F", "--field", "--input"}
        or item.startswith(("--raw-field=", "--field=", "--input="))
        for item in argv[1:]
    ):
        method = "POST"
    return method


def _api_is_mutation(argv: list[str]) -> bool:
    return _api_method(argv) not in {"GET", "HEAD"}


def _api_endpoint(argv: list[str]) -> str:
    value_flags = {
        "-X",
        "--method",
        "-H",
        "--header",
        "-f",
        "--raw-field",
        "-F",
        "--field",
        "--input",
        "--hostname",
        "--cache",
        "--template",
        "--jq",
    }
    skip_next = False
    for item in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if item in value_flags:
            skip_next = True
            continue
        if item.startswith("-"):
            continue
        return item
    return ""


def _is_repository_endpoint(endpoint: str) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    path = parsed.path if parsed.scheme else endpoint.split("?", 1)[0]
    parts = [part for part in path.strip("/").split("/") if part]
    try:
        repos_index = next(index for index, part in enumerate(parts) if part.lower() == "repos")
    except StopIteration:
        return False
    return len(parts) == repos_index + 3


def _is_graphql_endpoint(endpoint: str) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    path = parsed.path if parsed.scheme else endpoint.split("?", 1)[0]
    return path.strip("/").lower().endswith("graphql")


def _has_uninspectable_graphql_input(argv: list[str]) -> bool:
    for index, item in enumerate(argv[1:], start=1):
        if item == "--input":
            return True
        if item.startswith("--input="):
            return True
        if item in {"-f", "--raw-field", "-F", "--field"} and index + 1 < len(argv):
            value = argv[index + 1]
            if "query=@" in value.lower():
                return True
        if item.startswith(("--raw-field=", "--field=")) and "query=@" in item.lower():
            return True
    return False
