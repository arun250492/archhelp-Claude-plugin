"""Tests for input validation (security.py)."""

from __future__ import annotations

import pytest
from server.security import ValidationError, validate_repo_identifier, sanitise_tool_name


# ─── Valid inputs ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("owner/repo",                             ("owner", "repo")),
    ("my-org/my-repo",                         ("my-org", "my-repo")),
    ("https://github.com/owner/repo",          ("owner", "repo")),
    ("https://github.com/owner/repo.git",      ("owner", "repo")),
    ("https://github.com/owner/repo/tree/main",("owner", "repo")),
    ("github.com/owner/repo",                  ("owner", "repo")),
    ("My.Org/my_repo-2",                       ("My.Org", "my_repo-2")),
    ("a/b",                                    ("a", "b")),
    ("A1/B2",                                  ("A1", "B2")),
])
def test_valid_identifiers(value, expected):
    assert validate_repo_identifier(value) == expected


# ─── Invalid inputs ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "",
    "   ",
    "just-a-name",
    "owner/repo/extra",
    "owner//repo",
    "-owner/repo",
    "owner/-repo",
    "owner/",
    "/repo",
    "../etc/passwd",
    "owner/" + "a" * 101,
    "o" * 40 + "/repo",
    "https://notgithub.com/owner/repo",
    "a" * 301,
])
def test_invalid_identifiers(value):
    with pytest.raises(ValidationError):
        validate_repo_identifier(value)


def test_path_traversal_rejected():
    with pytest.raises(ValidationError):
        validate_repo_identifier("../evil/repo")


def test_dot_owner_rejected():
    with pytest.raises(ValidationError):
        validate_repo_identifier("./repo")


# ─── sanitise_tool_name ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("/api/users",     "api_users"),
    ("GET /api/{id}",  "GET__api__id"),
    ("",               "node"),
    ("valid_name",     "valid_name"),
    ("a" * 70,         "a" * 60),
    ("---",            "node"),
])
def test_sanitise_tool_name(raw, expected):
    result = sanitise_tool_name(raw)
    assert result == expected
    assert len(result) <= 60
    import re
    assert re.match(r"^[a-zA-Z0-9_]+$", result)
