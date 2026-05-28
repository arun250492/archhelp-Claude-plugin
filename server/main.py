"""
GitHub Code Analyzer — MCP Server entry point.

Wires together the GitHub client, analyzer, and diagram modules and
exposes them as MCP tools.  All raw file content stays inside the
analyzer; tool responses contain only synthesised, structured output
(Mermaid diagrams, counts, detected names) so that adversarial content
embedded in a repository cannot be relayed to the model as instructions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import base64

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, ImageContent, Tool

from .analyzer import (
    AnalysisResult,
    build_module_graph,
    detect_services,
    detect_technologies,
    extract_models,
    extract_routes,
    extract_top_dirs,
    classify_file,
)
from . import diagrams
from . import image_renderer
from .github_client import (
    fetch_file_content,
    fetch_repo_meta,
    fetch_tree,
    make_client,
)
from .security import ValidationError, validate_repo_identifier

# Log to stderr (stdout is reserved for the MCP stdio transport)
logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("LOG_LEVEL", "WARNING").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Tunables ─────────────────────────────────────────────────────────────────

DEFAULT_MAX_FILES = int(os.environ.get("GCA_DEFAULT_MAX_FILES", "80"))
ABS_MAX_FILES     = int(os.environ.get("GCA_ABS_MAX_FILES",     "300"))

# File extensions to prioritise when capping the fetch list
_PRIORITY_EXTS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".go", ".java", ".rb", ".rs", ".cs",
    ".graphql", ".gql", ".prisma", ".sql", ".proto",
})

# ─── Core analysis orchestration ──────────────────────────────────────────────

async def _analyse(repo_id: str, max_files: int = DEFAULT_MAX_FILES) -> AnalysisResult:
    owner, repo = validate_repo_identifier(repo_id)
    max_files   = max(1, min(max_files, ABS_MAX_FILES))

    async with make_client() as client:
        meta   = await fetch_repo_meta(owner, repo, client)
        branch = meta.get("default_branch", "main")
        tree   = await fetch_tree(owner, repo, branch, client)

        blobs = [n for n in tree if n.get("type") == "blob"]

        # Prioritise source + schema files; fall back to others
        priority   = [b for b in blobs if Path(b["path"]).suffix.lower() in _PRIORITY_EXTS]
        rest       = [b for b in blobs if b not in priority]
        fetch_list = (priority + rest)[:max_files]

        tasks         = [fetch_file_content(owner, repo, b["path"], client) for b in fetch_list]
        contents_list = await asyncio.gather(*tasks)
        contents      = {b["path"]: c for b, c in zip(fetch_list, contents_list) if c}

    logger.info("Fetched %d/%d files from %s/%s", len(contents), len(blobs), owner, repo)

    top_dirs  = extract_top_dirs(tree)
    tech      = detect_technologies(tree)
    models    = extract_models(contents)
    routes    = extract_routes(contents)
    mod_graph = build_module_graph(tree, contents)
    services  = detect_services(tree, contents)

    file_classes  = [classify_file(b["path"]) for b in blobs]
    databases_str = str(tech.get("databases", []))
    services_str  = " ".join(services).lower()

    has_frontend = "frontend" in file_classes
    has_backend  = "backend"  in file_classes
    has_db = (
        bool(models)
        or "data" in file_classes
        or any(kw in databases_str.lower() for kw in ("postgres", "mysql", "sqlite", "mongo", "prisma", "redis"))
    )
    has_infra = "infra" in file_classes or bool(tech.get("infra"))
    has_auth  = "Auth / JWT" in services

    return AnalysisResult(
        owner          = owner,
        repo           = repo,
        total_files    = len(blobs),
        analyzed_files = len(contents),
        top_dirs       = top_dirs,
        tech           = tech,
        models         = models,
        routes         = routes,
        module_graph   = mod_graph,
        services       = services,
        has_frontend   = has_frontend,
        has_backend    = has_backend,
        has_db         = has_db,
        has_infra      = has_infra,
        has_auth       = has_auth,
    )


# ─── Tool schema definitions ──────────────────────────────────────────────────

_REPO_SCHEMA = {
    "type":       "object",
    "properties": {
        "repo": {
            "type":        "string",
            "description": (
                "GitHub repository URL (https://github.com/owner/repo) "
                "or slug (owner/repo)."
            ),
        },
    },
    "required": ["repo"],
}

_REPO_WITH_MAX_FILES_SCHEMA = {
    "type":       "object",
    "properties": {
        "repo": _REPO_SCHEMA["properties"]["repo"],
        "max_files": {
            "type":        "integer",
            "description": f"Max source files to read (default {DEFAULT_MAX_FILES}, max {ABS_MAX_FILES}).",
            "default":     DEFAULT_MAX_FILES,
            "minimum":     1,
            "maximum":     ABS_MAX_FILES,
        },
    },
    "required": ["repo"],
}


def _tools() -> list[Tool]:
    img_note = (
        " Returns a professional PNG image with real technology icons, "
        "color-coded layers, and labeled data-flow edges. "
        "Falls back to Mermaid text if Graphviz is not installed."
    )
    return [
        Tool(
            name        = "analyze_repository",
            description = (
                "Comprehensively analyse a GitHub repository and produce ALL six "
                "professional PNG architecture diagrams (architecture, data flow, "
                "component map, ER, sequence, deployment) plus a plain-text overview "
                "in a single call. Accepts a GitHub URL or 'owner/repo' slug."
            ),
            inputSchema = _REPO_WITH_MAX_FILES_SCHEMA,
        ),
        Tool(
            name        = "generate_architecture_diagram",
            description = (
                "Generate a professional layered system architecture diagram showing "
                "client, backend, data, and infrastructure layers with real technology "
                "icons (React, Django, PostgreSQL, Redis, Docker, K8s, etc.), "
                "color-coded clusters, and labeled edges." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "generate_data_flow_diagram",
            description = (
                "Generate a professional data flow diagram tracing a request from the "
                "user through API gateway → auth middleware → business logic → cache → "
                "database → message queue, with numbered steps and color-coded "
                "channels." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "generate_er_diagram",
            description = (
                "Generate a professional Entity-Relationship diagram by extracting "
                "ORM model definitions and FK/relation fields from Django, Prisma, "
                "TypeORM, SQLAlchemy, Sequelize, and Rails. Shows entities as nodes "
                "with labeled relationship edges." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "generate_sequence_diagram",
            description = (
                "Generate a professional request/response flow diagram showing all "
                "actors (user, frontend, gateway, auth, service, cache, DB, worker) "
                "with numbered forward arrows and dashed return paths." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "generate_component_diagram",
            description = (
                "Generate a professional module dependency diagram built from static "
                "import analysis across Python, TypeScript, JavaScript, Go, Java, "
                "Rust, and Ruby source files. Shows inter-module coupling." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "generate_deployment_diagram",
            description = (
                "Generate a professional deployment topology diagram detecting Docker, "
                "Kubernetes (with Ingress/Pods/Services), Terraform, CI/CD pipelines, "
                "load balancers, and external services." + img_note
            ),
            inputSchema = _REPO_SCHEMA,
        ),
        Tool(
            name        = "get_repo_overview",
            description = (
                "Return a plain-text structural overview of a GitHub repository: "
                "file counts, primary languages, detected frameworks, databases, "
                "infrastructure tools, external services, ORM models, and API routes."
            ),
            inputSchema = _REPO_SCHEMA,
        ),
    ]


# ─── MCP server ───────────────────────────────────────────────────────────────

app = Server("archhelp-claude-plugin")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return _tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    repo_id   = (arguments.get("repo") or "").strip()
    max_files = int(arguments.get("max_files") or DEFAULT_MAX_FILES)

    try:
        result = await _analyse(repo_id, max_files)
    except ValidationError as exc:
        return [TextContent(type="text", text=f"**Invalid input:** {exc}")]
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            return [TextContent(type="text", text=
                f"**Repository not found:** `{repo_id}`. "
                "Check the owner/repo spelling and ensure the repository is public "
                "(or set GITHUB_TOKEN for private repos)."
            )]
        if code in (401, 403):
            return [TextContent(type="text", text=
                "**GitHub API authentication error.** "
                "The repository may be private, or the API rate limit has been reached. "
                "Set the `GITHUB_TOKEN` environment variable with a personal access token "
                "(Settings → Developer settings → Personal access tokens, `read:repo` scope)."
            )]
        return [TextContent(type="text", text=f"**GitHub API error {code}:** {exc}")]
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        return [TextContent(type="text", text=
            f"**Network error:** Could not reach GitHub. Details: {exc}"
        )]
    except Exception as exc:
        logger.exception("Unexpected error analysing %s", repo_id)
        return [TextContent(type="text", text=
            f"**Unexpected error:** {type(exc).__name__}: {exc}"
        )]

    if name == "get_repo_overview":
        return [TextContent(type="text", text=_overview_text(result))]

    # Map tool name → (image_renderer type, mermaid fallback fn)
    _diagram_map: dict[str, tuple[str, object]] = {
        "generate_architecture_diagram": ("architecture", lambda r: diagrams.architecture(r)),
        "generate_data_flow_diagram":    ("data_flow",    lambda r: diagrams.data_flow(r)),
        "generate_er_diagram":           ("er",           lambda r: diagrams.er_diagram(r.models)),
        "generate_sequence_diagram":     ("sequence",     lambda r: diagrams.sequence(r)),
        "generate_component_diagram":    ("component",    lambda r: diagrams.component(r)),
        "generate_deployment_diagram":   ("deployment",   lambda r: diagrams.deployment(r)),
    }

    if name in _diagram_map:
        heading     = name.replace("generate_", "").replace("_", " ").title()
        diag_type, mermaid_fn = _diagram_map[name]

        # Try PNG image first
        png_bytes, err = image_renderer.render(diag_type, result)

        contents: list = []
        contents.append(TextContent(
            type="text",
            text=f"## {heading} — `{result.owner}/{result.repo}`\n",
        ))

        if png_bytes:
            contents.append(ImageContent(
                type="image",
                data=base64.b64encode(png_bytes).decode(),
                mimeType="image/png",
            ))
        else:
            # Fallback: Mermaid text + install hint
            if err:
                contents.append(TextContent(type="text", text=f"> {err}\n"))
            contents.append(TextContent(
                type="text",
                text=mermaid_fn(result),  # type: ignore[operator]
            ))

        return contents

    if name == "analyze_repository":
        return _full_analysis_response(result)

    return [TextContent(type="text", text=f"**Unknown tool:** `{name}`")]


# ─── Formatted text helpers ───────────────────────────────────────────────────

def _overview_text(r: AnalysisResult) -> str:
    model_names = ", ".join(m.name for m in r.models[:20]) or "none detected"
    routes_text = "\n".join(
        f"  - `{rt.method} {rt.path}`" if rt.method != "ANY" else f"  - `{rt.path}`"
        for rt in r.routes[:20]
    ) or "  none detected"

    return (
        f"# Repository Overview: `{r.owner}/{r.repo}`\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Total files | {r.total_files} |\n"
        f"| Files analysed | {r.analyzed_files} |\n"
        f"| Top-level dirs | {len(r.top_dirs)} |\n"
        f"| ORM models found | {len(r.models)} |\n"
        f"| API routes found | {len(r.routes)} |\n\n"
        f"**Frameworks:** {', '.join(r.tech.get('framework', [])) or 'none detected'}\n\n"
        f"**Databases:** {', '.join(r.tech.get('databases', [])) or 'none detected'}\n\n"
        f"**Infrastructure:** {', '.join(r.tech.get('infra', [])) or 'none detected'}\n\n"
        f"**External services:** {', '.join(r.services) or 'none detected'}\n\n"
        f"**Primary languages:** {', '.join(r.tech.get('languages', []))}\n\n"
        f"**Layers detected:** "
        f"{'Frontend ' if r.has_frontend else ''}"
        f"{'Backend ' if r.has_backend else ''}"
        f"{'Database ' if r.has_db else ''}"
        f"{'Infrastructure' if r.has_infra else ''}\n\n"
        f"**ORM Models:** {model_names}\n\n"
        f"**API Routes:**\n{routes_text}\n"
    )


def _full_analysis_response(r: AnalysisResult) -> list:
    """Return a mixed list of ImageContent + TextContent for all 6 diagrams."""
    out: list = []

    out.append(TextContent(type="text", text=(
        f"# GitHub Code Analysis: `{r.owner}/{r.repo}`\n\n"
        f"> **{r.total_files}** files in repo | "
        f"**{r.analyzed_files}** read for deep analysis\n\n"
        f"**Stack:** {', '.join(r.tech.get('framework', [])) or 'unknown'} | "
        f"**Services:** {', '.join(r.services) or 'none detected'}\n\n---\n"
    )))

    diagram_sections = [
        ("1. System Architecture",      "architecture", lambda: diagrams.architecture(r)),
        ("2. Data Flow",                 "data_flow",    lambda: diagrams.data_flow(r)),
        ("3. Component / Module Map",    "component",    lambda: diagrams.component(r)),
        ("4. Entity-Relationship",       "er",           lambda: diagrams.er_diagram(r.models)),
        ("5. Request / Response Flow",   "sequence",     lambda: diagrams.sequence(r)),
        ("6. Deployment Topology",       "deployment",   lambda: diagrams.deployment(r)),
    ]

    for heading, diag_type, mermaid_fn in diagram_sections:
        out.append(TextContent(type="text", text=f"\n## {heading}\n"))
        png_bytes, err = image_renderer.render(diag_type, r)
        if png_bytes:
            out.append(ImageContent(
                type="image",
                data=base64.b64encode(png_bytes).decode(),
                mimeType="image/png",
            ))
        else:
            if err:
                out.append(TextContent(type="text", text=f"> {err}\n"))
            out.append(TextContent(type="text", text=mermaid_fn()))

    out.append(TextContent(type="text", text=f"\n---\n\n{_overview_text(r)}"))
    return out


def _full_analysis(r: AnalysisResult) -> str:
    """Legacy text-only fallback (kept for tests)."""
    return (
        f"# GitHub Code Analysis: `{r.owner}/{r.repo}`\n\n"
        f"**Stack:** {', '.join(r.tech.get('framework', [])) or 'unknown'}\n\n"
        "---\n\n"
        f"## 1. System Architecture\n\n{diagrams.architecture(r)}\n\n"
        f"## 2. Data Flow\n\n{diagrams.data_flow(r)}\n\n"
        f"## 3. Component Map\n\n{diagrams.component(r)}\n\n"
        f"## 4. ER Diagram\n\n{diagrams.er_diagram(r.models)}\n\n"
        f"## 5. Sequence\n\n{diagrams.sequence(r)}\n\n"
        f"## 6. Deployment\n\n{diagrams.deployment(r)}\n\n"
        f"{_overview_text(r)}"
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
