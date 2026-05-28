"""
Input validation and content sanitisation for the GitHub Code Analyzer.

External content fetched from GitHub must never be relayed verbatim as a
tool response, because a malicious repository could embed adversarial
instructions aimed at the model.  All analysis here produces synthesised
output (Mermaid diagrams, counts, names) rather than raw file text, which
is the primary defence.  This module adds a second layer of defence:
strict input validation so malformed repo identifiers are rejected before
any network request is made.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# GitHub's own validation rules for owner / repo names
_SLUG_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9._-]{0,37}[a-zA-Z0-9])?$")

# Maximum lengths
MAX_OWNER_LEN = 39   # GitHub limit
MAX_REPO_LEN  = 100  # GitHub limit


class ValidationError(ValueError):
    """Raised when a user-supplied value fails validation."""


def validate_repo_identifier(value: str) -> tuple[str, str]:
    """
    Parse and validate a GitHub repo identifier.

    Accepts:
    - ``owner/repo``
    - ``https://github.com/owner/repo``
    - ``https://github.com/owner/repo.git``
    - ``https://github.com/owner/repo/tree/branch``

    Returns ``(owner, repo)`` if valid, raises ``ValidationError`` otherwise.
    """
    if not isinstance(value, str):
        raise ValidationError("Repo identifier must be a string.")

    raw = value.strip().rstrip("/")

    if not raw:
        raise ValidationError("Repo identifier must not be empty.")

    if len(raw) > 300:
        raise ValidationError("Repo identifier is too long.")

    if "://" in raw or raw.startswith("github.com") or raw.startswith("www.github.com"):
        try:
            parsed = urlparse(raw if raw.startswith("http") else f"https://{raw}")
            host = parsed.hostname or ""
            if host not in ("github.com", "www.github.com"):
                raise ValidationError(
                    f"Only github.com repositories are supported. Got host: {host!r}"
                )
            parts = [p for p in parsed.path.strip("/").split("/") if p]
        except ValidationError:
            raise
        except Exception:
            raise ValidationError(f"Cannot parse GitHub URL: {raw!r}")

        if len(parts) < 2:
            raise ValidationError(
                f"GitHub URL must contain at least owner and repo: {raw!r}"
            )
        owner, repo = parts[0], parts[1].removesuffix(".git")
    elif "/" in raw:
        segments = raw.split("/")
        if len(segments) != 2:
            raise ValidationError(
                "Use the format 'owner/repo' or a full GitHub URL."
            )
        owner, repo = segments
    else:
        raise ValidationError(
            "Provide a GitHub URL (https://github.com/owner/repo) "
            "or a slug in the format 'owner/repo'."
        )

    _validate_slug_part(owner, "owner")
    _validate_slug_part(repo, "repo")

    return owner, repo


def _validate_slug_part(value: str, label: str) -> None:
    if not value:
        raise ValidationError(f"The {label} name must not be empty.")

    max_len = MAX_OWNER_LEN if label == "owner" else MAX_REPO_LEN
    if len(value) > max_len:
        raise ValidationError(
            f"The {label} name is too long (max {max_len} characters)."
        )

    if not _SLUG_RE.match(value):
        raise ValidationError(
            f"The {label} name {value!r} contains invalid characters. "
            "GitHub names may only contain letters, digits, hyphens, underscores, "
            "and dots, and must start and end with a letter or digit."
        )

    # Block names that could be used for path traversal
    if value in {".", ".."}:
        raise ValidationError(f"The {label} name {value!r} is reserved.")


def sanitise_tool_name(value: str) -> str:
    """Return a Mermaid-safe node identifier from an arbitrary string."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", value).strip("_")
    return safe[:60] if safe else "node"
