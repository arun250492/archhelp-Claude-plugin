"""
Integration tests for the full analysis pipeline with mocked GitHub API.

Uses `respx` to intercept httpx calls so no real network requests are made.
"""

from __future__ import annotations

import base64
import json
import pytest
import respx
import httpx

from server.main import _analyse, _overview_text, _full_analysis
from server.security import ValidationError


# ─── Fixtures ─────────────────────────────────────────────────────────────────

OWNER = "testorg"
REPO  = "testrepo"

_TREE = {
    "tree": [
        {"path": "frontend",              "type": "tree"},
        {"path": "backend",               "type": "tree"},
        {"path": "infra",                 "type": "tree"},
        {"path": ".github",               "type": "tree"},
        {"path": ".github/workflows",     "type": "tree"},
        {"path": "frontend/App.tsx",      "type": "blob", "size": 500},
        {"path": "backend/models.py",     "type": "blob", "size": 800},
        {"path": "backend/views.py",      "type": "blob", "size": 600},
        {"path": "infra/Dockerfile",      "type": "blob", "size": 300},
        {"path": ".github/workflows/ci.yml", "type": "blob", "size": 200},
        {"path": "manage.py",             "type": "blob", "size": 100},
        {"path": "requirements.txt",      "type": "blob", "size": 50},
    ]
}

_REPO_META = {
    "default_branch": "main",
    "name": REPO,
    "full_name": f"{OWNER}/{REPO}",
}

_MODELS_PY = """\
from django.db import models

class User(models.Model):
    username = models.CharField(max_length=150)

class Post(models.Model):
    author = models.ForeignKey('User', on_delete=models.CASCADE)
    title  = models.CharField(max_length=200)

class Comment(models.Model):
    post   = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey('User', on_delete=models.CASCADE)
"""

_VIEWS_PY = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
async def list_users(): ...

@router.post("/users")
async def create_user(): ...

@router.get("/users/{user_id}")
async def get_user(user_id: int): ...

@router.post("/auth/login")
async def login(): ...
"""

_APP_TSX = """\
import React from 'react'
import { api } from '../backend/api'

export function App() {
  return <div>Hello</div>
}
"""


def _encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _file_response(content: str) -> dict:
    return {"encoding": "base64", "content": _encode(content)}


# ─── Mock helper ──────────────────────────────────────────────────────────────

def _mock_github(mock: respx.MockRouter) -> None:
    base = "https://api.github.com"

    mock.get(f"{base}/repos/{OWNER}/{REPO}").mock(
        return_value=httpx.Response(200, json=_REPO_META)
    )
    mock.get(f"{base}/repos/{OWNER}/{REPO}/git/trees/main?recursive=1").mock(
        return_value=httpx.Response(200, json=_TREE)
    )

    file_map = {
        "backend/models.py":  _MODELS_PY,
        "backend/views.py":   _VIEWS_PY,
        "frontend/App.tsx":   _APP_TSX,
        "infra/Dockerfile":   "FROM python:3.12-slim\nRUN pip install -r requirements.txt\n",
        ".github/workflows/ci.yml": "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
        "manage.py":          "#!/usr/bin/env python\nimport django\n",
        "requirements.txt":   "django>=4.2\nfastapi>=0.100\nredis>=5.0\n",
    }
    for path, content in file_map.items():
        mock.get(f"{base}/repos/{OWNER}/{REPO}/contents/{path}").mock(
            return_value=httpx.Response(200, json=_file_response(content))
        )


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_analyse_returns_correct_owner_repo():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert result.owner == OWNER
    assert result.repo  == REPO


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_frontend():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert result.has_frontend is True


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_backend():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert result.has_backend is True


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_infra():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert result.has_infra is True


@pytest.mark.asyncio
@respx.mock
async def test_analyse_extracts_django_models():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    names = [m.name for m in result.models]
    assert "User"    in names
    assert "Post"    in names
    assert "Comment" in names


@pytest.mark.asyncio
@respx.mock
async def test_analyse_extracts_routes():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    paths = [r.path for r in result.routes]
    assert "/users" in paths
    assert "/auth/login" in paths


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_django_framework():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert "Django" in result.tech.get("framework", [])


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_github_actions():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert "GitHub Actions" in result.tech.get("infra", [])


@pytest.mark.asyncio
@respx.mock
async def test_analyse_detects_redis_service():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    assert "Cache" in result.services


@pytest.mark.asyncio
@respx.mock
async def test_analyse_url_form():
    _mock_github(respx.mock)
    result = await _analyse(f"https://github.com/{OWNER}/{REPO}")
    assert result.owner == OWNER
    assert result.repo  == REPO


@pytest.mark.asyncio
async def test_analyse_rejects_invalid_input():
    with pytest.raises(ValidationError):
        await _analyse("not-a-valid-slug")


@pytest.mark.asyncio
@respx.mock
async def test_overview_text_contains_table():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    text = _overview_text(result)
    assert "Total files"    in text
    assert "Files analysed" in text
    assert "Django"         in text


@pytest.mark.asyncio
@respx.mock
async def test_full_analysis_contains_all_sections():
    _mock_github(respx.mock)
    result = await _analyse(f"{OWNER}/{REPO}")
    text   = _full_analysis(result)
    for heading in [
        "System Architecture",
        "Data Flow",
        "Component",
        "ER Diagram",
        "Sequence",
        "Deployment",
    ]:
        assert heading in text, f"Missing section: {heading}"


@pytest.mark.asyncio
@respx.mock
async def test_analyse_404_raises_http_error():
    respx.mock.get("https://api.github.com/repos/nobody/nonexistent").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    import httpx as _httpx
    with pytest.raises(_httpx.HTTPStatusError):
        await _analyse("nobody/nonexistent")


@pytest.mark.asyncio
@respx.mock
async def test_file_fetch_error_is_graceful():
    """A 404 on a single file should not crash the whole analysis."""
    _mock_github(respx.mock)
    # Override one file to return 404
    respx.mock.get(
        "https://api.github.com/repos/testorg/testrepo/contents/backend/views.py"
    ).mock(return_value=httpx.Response(404, json={"message": "Not Found"}))

    result = await _analyse(f"{OWNER}/{REPO}")
    # Should still complete; routes from views.py may be absent but no crash
    assert result.owner == OWNER
