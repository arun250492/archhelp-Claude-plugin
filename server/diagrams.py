"""
Mermaid diagram generators.

Each function accepts only pre-processed, structured data (AnalysisResult
fields) and returns a Mermaid fenced code block string.  No raw file
content is ever passed in, preventing prompt-injection from repository
source.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analyzer import AnalysisResult, ModelDef, Route


def _safe_id(text: str, max_len: int = 40) -> str:
    """Return a Mermaid-safe node identifier."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", text).strip("_")
    return (safe or "node")[:max_len]


# ─── 1. Architecture diagram ──────────────────────────────────────────────────

def architecture(result: "AnalysisResult") -> str:
    lines = ["```mermaid", "graph TB"]
    lines += [
        f'    title["{result.owner}/{result.repo} - Architecture"]',
        '    style title fill:#f5f5f5,stroke:#ccc,color:#333',
        "",
    ]

    if result.has_frontend:
        lines += [
            '    subgraph Client["Client Layer"]',
            "        FE[Frontend App]",
            "    end",
        ]

    if result.has_backend:
        lines += ['    subgraph Backend["Backend Layer"]']
        lines.append("        API[API Server]")
        lines.append("        BL[Business Logic]")
        if "Auth / JWT" in result.services:
            lines.append("        AUTH[Auth Service]")
        if "Message Queue" in result.services:
            lines.append("        MQ[Message Queue]")
        lines.append("    end")

    if result.has_db:
        lines += ['    subgraph Data["Data Layer"]']
        for db in result.tech.get("databases", []) or ["Database"]:
            nid = _safe_id(db)
            lines.append(f'        {nid}[("{db}")]')
        if "Cache" in result.services:
            lines.append("        CACHE[(Cache)]")
        lines.append("    end")

    if result.services:
        ext_services = [s for s in result.services
                        if s not in ("Auth / JWT", "Message Queue", "Cache")]
        if ext_services:
            lines += ['    subgraph External["External Services"]']
            for svc in ext_services[:6]:
                nid = _safe_id(svc)
                lines.append(f'        {nid}["{svc}"]')
            lines.append("    end")

    if result.has_infra:
        infra = result.tech.get("infra", [])
        if infra:
            lines += ['    subgraph Infra["Infrastructure"]']
            for t in infra[:6]:
                nid = _safe_id(t)
                lines.append(f'        {nid}["{t}"]')
            lines.append("    end")

    # Edges
    if result.has_frontend and result.has_backend:
        lines.append("    FE -->|HTTP/REST| API")
        lines.append("    API --> BL")
    if result.has_backend and "Auth / JWT" in result.services:
        lines.append("    API --> AUTH")
    if result.has_backend and result.has_db:
        for db in result.tech.get("databases", []) or ["Database"]:
            lines.append(f"    BL --> {_safe_id(db)}")
    if result.has_backend and "Message Queue" in result.services:
        lines.append("    BL --> MQ")
    if result.has_backend and "Cache" in result.services:
        lines.append("    BL --> CACHE")

    lines.append("```")
    return "\n".join(lines)


# ─── 2. Data flow diagram ─────────────────────────────────────────────────────

def data_flow(result: "AnalysisResult") -> str:
    lines = ["```mermaid", "flowchart LR"]
    lines += [
        "    User([User / Client])",
        "    GW[API Gateway]",
    ]

    if "Auth / JWT" in result.services:
        lines.append("    AUTH[Auth Middleware]")
    lines += [
        "    BL[Business Logic]",
        "    DB[(Database)]",
        "",
        "    User -->|Request| GW",
        "    GW --> AUTH" if "Auth / JWT" in result.services else "",
        "    AUTH -->|Validated| BL" if "Auth / JWT" in result.services else "    GW --> BL",
        "    BL -->|Query| DB",
        "    DB -->|Result| BL",
        "    BL -->|Response| GW",
        "    GW -->|JSON| User",
    ]

    if "Cache" in result.services:
        lines += [
            "    CACHE[(Cache)]",
            "    BL -.->|Cache read| CACHE",
            "    CACHE -.->|Hit| BL",
        ]
    if "Message Queue" in result.services:
        lines += [
            "    MQ([Message Queue])",
            "    BL -->|Publish| MQ",
            "    MQ -->|Consume| WORKER[Worker]",
        ]

    # Show up to 10 routes as a subgraph
    routes_to_show = result.routes[:10]
    if routes_to_show:
        lines += ['    subgraph Routes["API Routes"]']
        for r in routes_to_show:
            nid = _safe_id(f"{r.method}_{r.path}")
            label = f"{r.method} {r.path}" if r.method != "ANY" else r.path
            lines.append(f'        {nid}["{label}"]')
        lines.append("    end")
        lines.append("    GW --> Routes")

    # Remove blank strings that sneak in from ternary expressions
    lines = [l for l in lines if l is not None]
    lines.append("```")
    return "\n".join(lines)


# ─── 3. Entity-Relationship diagram ──────────────────────────────────────────

def er_diagram(models: list["ModelDef"]) -> str:
    if not models:
        return (
            "> **No ORM models detected.**  Add schema files such as "
            "`models.py` (Django/SQLAlchemy), `schema.prisma`, "
            "`*.entity.ts` (TypeORM), or Rails model classes to generate "
            "an ER diagram."
        )

    lines = ["```mermaid", "erDiagram"]
    model_names = {m.name for m in models}
    drawn_relations: set[tuple[str, str]] = set()

    for model in models[:25]:
        lines.append(f"    {model.name} {{")
        lines.append(f"        int id PK")
        lines.append(f"        datetime created_at")
        lines.append(f"    }}")

        for field in model.fields:
            if field.related_model and field.related_model in model_names:
                pair = tuple(sorted([model.name, field.related_model]))
                if pair not in drawn_relations:
                    drawn_relations.add(pair)  # type: ignore[arg-type]
                    lines.append(
                        f'    {model.name} }}o--|| {field.related_model} : "{field.name}"'
                    )

    lines.append("```")
    return "\n".join(lines)


# ─── 4. Sequence diagram ──────────────────────────────────────────────────────

def sequence(result: "AnalysisResult") -> str:
    lines = ["```mermaid", "sequenceDiagram", "    autonumber"]

    # Participants
    lines.append("    actor User")
    if result.has_frontend:
        lines.append("    participant FE as Frontend")
    lines.append("    participant GW as API Gateway")
    if "Auth / JWT" in result.services:
        lines.append("    participant AUTH as Auth Service")
    lines.append("    participant SVC as Backend Service")
    if result.has_db:
        lines.append("    participant DB as Database")
    if "Cache" in result.services:
        lines.append("    participant CACHE as Cache")
    if "Message Queue" in result.services:
        lines.append("    participant MQ as Message Queue")
    lines.append("")

    # Happy-path flow
    if result.has_frontend:
        lines.append("    User->>FE: User interaction")
        lines.append("    FE->>GW: HTTP Request")
    else:
        lines.append("    User->>GW: HTTP Request")

    if "Auth / JWT" in result.services:
        lines.append("    GW->>AUTH: Validate token")
        lines.append("    AUTH-->>GW: 200 OK / 401")

    lines.append("    GW->>SVC: Forward request")

    if "Cache" in result.services:
        lines.append("    SVC->>CACHE: Cache lookup")
        lines.append("    alt Cache hit")
        lines.append("        CACHE-->>SVC: Cached result")
        lines.append("    else Cache miss")

    if result.has_db:
        lines.append("        SVC->>DB: Query / Mutation")
        lines.append("        DB-->>SVC: Row set")

    if "Cache" in result.services:
        lines.append("        SVC->>CACHE: Store result")
        lines.append("    end")

    if "Message Queue" in result.services:
        lines.append("    SVC->>MQ: Publish event")

    lines.append("    SVC-->>GW: Processed response")
    if result.has_frontend:
        lines.append("    GW-->>FE: JSON response")
        lines.append("    FE-->>User: Render / update UI")
    else:
        lines.append("    GW-->>User: JSON response")

    # Annotate with sample routes
    sample_routes = [
        (f"{r.method} {r.path}" if r.method != "ANY" else r.path)
        for r in result.routes[:3]
    ]
    if sample_routes:
        note = ", ".join(sample_routes)
        lines.append(f'    Note over GW,SVC: Example routes: {note}')

    lines.append("```")
    return "\n".join(lines)


# ─── 5. Component / module dependency diagram ─────────────────────────────────

def component(result: "AnalysisResult") -> str:
    lines = ["```mermaid", "graph LR", "    %% Module dependency map"]
    added: set[str] = set()

    def node(name: str) -> str:
        nid = _safe_id(name)
        if nid not in added:
            lines.append(f'    {nid}["{name}"]')
            added.add(nid)
        return nid

    for src, targets in result.module_graph.items():
        sid = node(src)
        for tgt in sorted(targets):
            tid = node(tgt)
            lines.append(f"    {sid} --> {tid}")

    # Add any top-level dirs not yet in graph
    for d in result.top_dirs:
        node(d)

    lines.append("```")
    return "\n".join(lines)


# ─── 6. Deployment diagram ────────────────────────────────────────────────────

def deployment(result: "AnalysisResult") -> str:
    infra  = result.tech.get("infra", [])
    lines  = ["```mermaid", "graph TB"]

    lines += [
        '    subgraph Internet["Internet"]',
        "        USER([Client])",
        "        CDN[CDN / Load Balancer]",
        "    end",
        '    subgraph App["Application Layer"]',
        "        WEB[Web / Reverse Proxy]",
        "        APP[App Server]",
        "    end",
        '    subgraph Persistence["Persistence Layer"]',
        "        DB[(Primary DB)]",
        "        REPLICA[(Read Replica)]",
        "    end",
    ]

    if any(i in infra for i in ("Docker", "Docker Compose", "Kubernetes", "Helm")):
        lines += ['    subgraph Containers["Container Layer"]']
        if "Docker" in infra or "Docker Compose" in infra:
            lines.append("        DOCKER[Docker]")
        if "Kubernetes" in infra or "Helm" in infra:
            lines.append("        K8S[Kubernetes / Helm]")
        lines.append("    end")

    if "Terraform" in infra:
        lines += [
            '    subgraph IaC["Infrastructure as Code"]',
            "        TF[Terraform]",
            "    end",
        ]

    ci_tools = [i for i in infra if "CI" in i or "Actions" in i or "Circle" in i or "GitLab" in i]
    if ci_tools:
        lines += ['    subgraph CI["CI / CD Pipeline"]']
        for ci in ci_tools:
            lines.append(f'        {_safe_id(ci)}["{ci}"]')
        lines.append("    end")

    # Optional external services
    ext = [s for s in result.services if s in ("Email", "Storage", "Monitoring", "Payments", "Search")]
    if ext:
        lines += ['    subgraph External["External Services"]']
        for s in ext:
            lines.append(f'        {_safe_id(s)}["{s}"]')
        lines.append("    end")

    # Edges
    lines += [
        "    USER --> CDN",
        "    CDN --> WEB",
        "    WEB --> APP",
        "    APP --> DB",
        "    DB --> REPLICA",
    ]
    if "Cache" in result.services:
        lines += [
            "    CACHE[(Cache)]",
            "    APP --> CACHE",
        ]
    if "Message Queue" in result.services:
        lines += [
            "    MQ([Message Queue])",
            "    APP --> MQ",
        ]

    lines.append("```")
    return "\n".join(lines)
