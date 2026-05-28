"""
Async GitHub REST API client with retry/back-off and rate-limit handling.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Tunables (can be overridden via environment variables for testing)
MAX_RETRIES   = int(os.environ.get("GCA_MAX_RETRIES", "3"))
BASE_BACKOFF  = float(os.environ.get("GCA_BASE_BACKOFF", "1.0"))   # seconds
REQUEST_TIMEOUT = float(os.environ.get("GCA_REQUEST_TIMEOUT", "20.0"))
MAX_FILE_BYTES  = int(os.environ.get("GCA_MAX_FILE_BYTES", "40000"))


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "archhelp-claude-plugin-mcp/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _get(path: str, client: httpx.AsyncClient) -> Any:
    """
    GET a GitHub API path with automatic retry on transient errors.

    Handles:
    - 429 Too Many Requests  → honour Retry-After header
    - 403 rate-limited       → back off and retry
    - 5xx server errors      → exponential back-off
    """
    url = path if path.startswith("http") else f"{GITHUB_API}{path}"
    headers = _build_headers()
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            # Rate-limit: wait and retry
            if resp.status_code in (429, 403):
                retry_after = float(resp.headers.get("Retry-After", BASE_BACKOFF * attempt))
                logger.warning("Rate-limited by GitHub (attempt %d); sleeping %.1fs", attempt, retry_after)
                await asyncio.sleep(min(retry_after, 60.0))
                last_exc = httpx.HTTPStatusError(
                    f"{resp.status_code}", request=resp.request, response=resp
                )
                continue

            # Transient server error
            if resp.status_code >= 500:
                wait = BASE_BACKOFF * (2 ** (attempt - 1))
                logger.warning("GitHub 5xx (attempt %d); retrying in %.1fs", attempt, wait)
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    f"{resp.status_code}", request=resp.request, response=resp
                )
                continue

            resp.raise_for_status()
            return resp.json()

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            wait = BASE_BACKOFF * (2 ** (attempt - 1))
            logger.warning("Network error (attempt %d): %s; retrying in %.1fs", attempt, exc, wait)
            await asyncio.sleep(wait)
            last_exc = exc

    raise last_exc or RuntimeError("Exhausted retries without a response")


async def fetch_repo_meta(owner: str, repo: str, client: httpx.AsyncClient) -> dict:
    return await _get(f"/repos/{owner}/{repo}", client)


async def fetch_tree(owner: str, repo: str, branch: str, client: httpx.AsyncClient) -> list[dict]:
    data = await _get(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", client)
    return data.get("tree", [])


async def fetch_file_content(
    owner: str, repo: str, path: str, client: httpx.AsyncClient
) -> str:
    """Fetch and decode a single file; return empty string on any error."""
    try:
        data = await _get(f"/repos/{owner}/{repo}/contents/{path}", client)
        if not isinstance(data, dict):
            return ""
        encoding = data.get("encoding", "")
        content  = data.get("content", "")
        if encoding == "base64":
            import base64
            raw = base64.b64decode(content).decode("utf-8", errors="replace")
            return raw[:MAX_FILE_BYTES]
        return ""
    except Exception as exc:
        logger.debug("Could not fetch %s: %s", path, exc)
        return ""


def make_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient suitable for a full analysis session."""
    return httpx.AsyncClient(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
