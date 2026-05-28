"""
Professional PNG diagram generator using the `diagrams` library.

Generates architect-quality images with real technology icons, color-coded
clusters, labeled edges, and proper layout — not text diagrams.

Requires Graphviz to be installed on the system:
  Windows : winget install graphviz   (or https://graphviz.org/download)
  macOS   : brew install graphviz
  Linux   : sudo apt-get install graphviz   /   sudo dnf install graphviz

Falls back gracefully to Mermaid text if graphviz/diagrams is unavailable.
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

# ─── Ensure Graphviz bin is in PATH (Windows default install location) ────────
_GV_PATHS = [
    r"C:\Program Files\Graphviz\bin",
    r"C:\Program Files (x86)\Graphviz\bin",
    "/usr/bin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
]
for _p in _GV_PATHS:
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

if TYPE_CHECKING:
    from .analyzer import AnalysisResult

# ─── Optional import guard ────────────────────────────────────────────────────

DIAGRAMS_AVAILABLE = False

try:
    from diagrams import Diagram, Cluster, Edge

    # Compute / servers
    from diagrams.onprem.compute import Server
    from diagrams.onprem.client import User, Users

    # Databases
    from diagrams.onprem.database import PostgreSQL, MySQL, MongoDB, Cassandra
    from diagrams.onprem.inmemory import Redis, Memcached
    from diagrams.generic.database import SQL

    # Queues / messaging
    from diagrams.onprem.queue import Kafka, RabbitMQ, ActiveMQ

    # Network / proxy
    from diagrams.onprem.network import Nginx, Apache, HAProxy
    from diagrams.generic.network import Firewall

    # Container / orchestration
    from diagrams.onprem.container import Docker
    from diagrams.k8s.compute import Pod, Deploy
    from diagrams.k8s.network import Ingress, SVC

    # CI/CD / IaC
    from diagrams.onprem.ci import GithubActions, Jenkins, TravisCI, CircleCI, GitlabCI
    from diagrams.onprem.iac import Terraform, Ansible

    # Security
    from diagrams.onprem.security import Vault

    # Storage
    from diagrams.generic.storage import Storage

    # Frameworks & languages
    from diagrams.programming.framework import (
        React, Vue, Angular, Django, FastAPI, Flask, Rails, Spring, Laravel,
    )
    from diagrams.programming.language import (
        Python, Go, Java, JavaScript, TypeScript, Ruby,
    )

    # SaaS monitoring / alerting
    from diagrams.saas.logging import Datadog, Newrelic
    from diagrams.saas.alerting import Pagerduty
    from diagrams.saas.cdn import Cloudflare

    DIAGRAMS_AVAILABLE = True

except Exception:
    DIAGRAMS_AVAILABLE = False


# ─── Helpers ──────────────────────────────────────────────────────────────────

_GRAPH_ATTR = {
    "fontsize":  "13",
    "bgcolor":   "white",
    "pad":       "0.6",
    "splines":   "ortho",
    "nodesep":   "0.6",
    "ranksep":   "0.8",
    "fontname":  "Helvetica",
}

_NODE_ATTR = {
    "fontsize": "11",
    "fontname": "Helvetica",
}

_EDGE_ATTR = {
    "fontsize": "10",
    "fontname": "Helvetica",
}


def _read_png(path: str) -> bytes:
    return Path(path + ".png").read_bytes()


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _framework_node(tech: dict, label: str = "API Server"):
    """Return the best framework icon based on detected tech."""
    fw = " ".join(tech.get("framework", []))
    if "FastAPI"  in fw: return FastAPI(label)
    if "Django"   in fw: return Django(label)
    if "Flask"    in fw: return Flask(label)
    if "Rails"    in fw: return Rails(label)
    if "Spring"   in fw: return Spring(label)
    if "Laravel"  in fw: return Laravel(label)
    return Server(label)


def _frontend_node(tech: dict, label: str = "Frontend"):
    fw = " ".join(tech.get("framework", []))
    if "React"   in fw or "Next" in fw: return React(label)
    if "Vue"     in fw or "Nuxt" in fw: return Vue(label)
    if "Angular" in fw:                 return Angular(label)
    return Server(label)


def _db_nodes(tech: dict) -> list:
    nodes = []
    for db in tech.get("databases", []):
        if "Postgres" in db:     nodes.append(PostgreSQL(db))
        elif "MySQL"  in db:     nodes.append(MySQL(db))
        elif "Mongo"  in db:     nodes.append(MongoDB(db))
        elif "Cassandra" in db:  nodes.append(Cassandra(db))
        elif "Redis" in db:      nodes.append(Redis(db))
        else:                    nodes.append(SQL(db or "Database"))
    return nodes or [SQL("Database")]


def _lang_node(tech: dict, label: str = "Service"):
    langs = " ".join(tech.get("languages", []))
    if ".ts" in langs or ".tsx" in langs: return TypeScript(label)
    if ".py" in langs:                    return Python(label)
    if ".go" in langs:                    return Go(label)
    if ".java" in langs:                  return Java(label)
    if ".rb" in langs:                    return Ruby(label)
    if ".js" in langs:                    return JavaScript(label)
    return Server(label)


# ─── 1. Architecture diagram ──────────────────────────────────────────────────

def architecture_png(result: "AnalysisResult") -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "arch")
        with Diagram(
            f"{result.owner}/{result.repo}  —  System Architecture",
            filename=out, show=False, direction="TB",
            graph_attr=_GRAPH_ATTR, node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            user = Users("Users")

            # ── Client layer ──────────────────────────────────────────────
            if result.has_frontend:
                with Cluster("Client Layer"):
                    fe = _frontend_node(result.tech)

            # ── Backend layer ─────────────────────────────────────────────
            backend_nodes = []
            with Cluster("Backend Layer"):
                api = _framework_node(result.tech, "API Server")
                backend_nodes.append(api)

                if "Auth / JWT" in result.services:
                    auth = Vault("Auth / JWT")
                    backend_nodes.append(auth)

                if "Message Queue" in result.services:
                    mq_tech = " ".join(result.tech.get("infra", []))
                    if "Kafka"    in mq_tech: mq = Kafka("Message Queue")
                    elif "Rabbit" in mq_tech: mq = RabbitMQ("Message Queue")
                    else:                     mq = ActiveMQ("Message Queue")
                    backend_nodes.append(mq)

                if "Email" in result.services:
                    mail = Server("Email Service")
                    backend_nodes.append(mail)

            # ── Data layer ────────────────────────────────────────────────
            db_nodes = []
            with Cluster("Data Layer"):
                db_nodes = _db_nodes(result.tech)
                if "Cache" in result.services:
                    db_nodes.append(Redis("Cache"))
                if "Search" in result.services:
                    db_nodes.append(Server("Search Engine"))
                if "Storage" in result.services:
                    db_nodes.append(Storage("Object Storage"))

            # ── Infrastructure ────────────────────────────────────────────
            infra_list = result.tech.get("infra", [])
            if infra_list:
                with Cluster("Infrastructure"):
                    if "Nginx"  in infra_list: Nginx("Reverse Proxy")
                    if "Docker" in infra_list or "Docker Compose" in infra_list:
                        Docker("Containers")
                    if "Terraform" in infra_list: Terraform("IaC")
                    if "GitHub Actions" in infra_list: GithubActions("CI/CD")
                    if "GitLab CI"      in infra_list: GitlabCI("CI/CD")
                    if "CircleCI"       in infra_list: CircleCI("CI/CD")

            # ── Monitoring ────────────────────────────────────────────────
            if "Monitoring" in result.services:
                with Cluster("Observability"):
                    Datadog("Monitoring")

            # ── Edges ─────────────────────────────────────────────────────
            if result.has_frontend:
                user >> Edge(label="HTTPS", color="#2196F3") >> fe
                fe  >> Edge(label="REST / GraphQL", color="#2196F3") >> api
            else:
                user >> Edge(label="HTTPS", color="#2196F3") >> api

            if "Auth / JWT" in result.services:
                api >> Edge(label="validate", color="#FF5722", style="dashed") >> auth

            for db in db_nodes:
                api >> Edge(label="query", color="#4CAF50") >> db

            if "Message Queue" in result.services:
                api >> Edge(label="publish", color="#FF9800", style="dashed") >> mq

        return _read_png(out)


# ─── 2. Data flow diagram ─────────────────────────────────────────────────────

def data_flow_png(result: "AnalysisResult") -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "dataflow")
        with Diagram(
            f"{result.owner}/{result.repo}  —  Data Flow",
            filename=out, show=False, direction="LR",
            graph_attr={**_GRAPH_ATTR, "splines": "curved"},
            node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            user = User("Client")

            with Cluster("Entry Point"):
                gw = Nginx("API Gateway") if "Nginx" in result.tech.get("infra", []) \
                     else Server("API Gateway")

            with Cluster("Auth"):
                auth = Vault("Auth Middleware") if "Auth / JWT" in result.services \
                       else Server("Middleware")

            with Cluster("Business Logic"):
                svc = _framework_node(result.tech, "Service Layer")
                if "Message Queue" in result.services:
                    mq = RabbitMQ("Async Queue")

            with Cluster("Persistence"):
                dbs = _db_nodes(result.tech)
                if "Cache" in result.services:
                    cache = Redis("Cache")

            # Flow
            user >> Edge(label="1. Request", color="#2196F3") >> gw
            gw   >> Edge(label="2. Auth check", color="#FF5722") >> auth
            auth >> Edge(label="3. Validated", color="#4CAF50") >> svc

            if "Cache" in result.services:
                svc >> Edge(label="4a. Cache lookup", color="#9C27B0", style="dashed") >> cache
                cache >> Edge(label="Hit", color="#9C27B0", style="dashed") >> svc

            for db in dbs:
                svc >> Edge(label="4b. DB query", color="#4CAF50") >> db
                db  >> Edge(label="Result", color="#4CAF50") >> svc

            if "Message Queue" in result.services:
                svc >> Edge(label="5. Publish event", color="#FF9800", style="dashed") >> mq

            svc >> Edge(label="6. Response", color="#2196F3") >> gw
            gw  >> Edge(label="7. JSON", color="#2196F3") >> user

        return _read_png(out)


# ─── 3. Deployment diagram ────────────────────────────────────────────────────

def deployment_png(result: "AnalysisResult") -> bytes:
    infra = result.tech.get("infra", [])
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "deploy")
        with Diagram(
            f"{result.owner}/{result.repo}  —  Deployment Topology",
            filename=out, show=False, direction="TB",
            graph_attr=_GRAPH_ATTR, node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            user = Users("End Users")

            with Cluster("Internet / Edge"):
                if "Nginx" in infra:   lb = Nginx("Load Balancer")
                else:                  lb = Firewall("Edge / Firewall")

            if "Kubernetes" in infra or "Helm" in infra:
                with Cluster("Kubernetes Cluster"):
                    ing = Ingress("Ingress")
                    with Cluster("App Pods"):
                        pods = [Pod("pod-1"), Pod("pod-2"), Pod("pod-3")]
                    svc_k8s = SVC("ClusterIP")
                app_entry = ing
                app_nodes = pods
            elif "Docker" in infra or "Docker Compose" in infra:
                with Cluster("Docker"):
                    app_entry = Docker("App Container")
                    app_nodes = [app_entry]
            else:
                with Cluster("Application"):
                    app_entry = _framework_node(result.tech, "App Server")
                    app_nodes = [app_entry]

            with Cluster("Data"):
                db_nodes = _db_nodes(result.tech)
                if "Cache" in result.services:
                    db_nodes.append(Redis("Cache"))

            ci_nodes = []
            if any(ci in infra for ci in ("GitHub Actions", "GitLab CI", "CircleCI", "Jenkins")):
                with Cluster("CI / CD"):
                    if "GitHub Actions" in infra: ci_nodes.append(GithubActions("CI/CD"))
                    elif "GitLab CI"    in infra: ci_nodes.append(GitlabCI("CI/CD"))
                    elif "CircleCI"     in infra: ci_nodes.append(CircleCI("CI/CD"))
                    elif "Jenkins"      in infra: ci_nodes.append(Jenkins("CI/CD"))

            if "Terraform" in infra:
                with Cluster("Infrastructure as Code"):
                    tf = Terraform("Terraform")

            if "Monitoring" in result.services:
                with Cluster("Observability"):
                    mon = Datadog("Monitoring")

            # Edges
            user >> Edge(label="HTTPS", color="#2196F3") >> lb
            lb   >> Edge(color="#2196F3") >> app_entry

            for db in db_nodes:
                for node in app_nodes[:1]:
                    node >> Edge(label="persist", color="#4CAF50") >> db

            if ci_nodes:
                ci_nodes[0] >> Edge(label="deploy", color="#FF9800", style="dashed") >> app_entry

        return _read_png(out)


# ─── 4. Component / dependency diagram ───────────────────────────────────────

def component_png(result: "AnalysisResult") -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "component")
        with Diagram(
            f"{result.owner}/{result.repo}  —  Module Dependencies",
            filename=out, show=False, direction="LR",
            graph_attr=_GRAPH_ATTR, node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            nodes: dict = {}

            # Create a node per top-level directory
            for d in result.top_dirs[:16]:
                nodes[d] = _lang_node(result.tech, d)

            # Draw dependency edges from module graph
            for src, targets in result.module_graph.items():
                if src in nodes:
                    for tgt in sorted(targets):
                        if tgt in nodes:
                            nodes[src] >> Edge(color="#607D8B") >> nodes[tgt]

        return _read_png(out)


# ─── 5. Sequence diagram (rendered via graphviz since diagrams lib
#        doesn't have sequence natively — we build a flow instead) ────────────

def sequence_png(result: "AnalysisResult") -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "sequence")
        with Diagram(
            f"{result.owner}/{result.repo}  —  Request / Response Flow",
            filename=out, show=False, direction="LR",
            graph_attr={**_GRAPH_ATTR, "splines": "polyline", "rankdir": "LR"},
            node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            actors = []

            usr = User("User")
            actors.append(usr)

            if result.has_frontend:
                fe = _frontend_node(result.tech, "Frontend")
                actors.append(fe)

            gw = Server("API Gateway")
            actors.append(gw)

            if "Auth / JWT" in result.services:
                auth = Vault("Auth Service")
                actors.append(auth)

            svc = _framework_node(result.tech, "Backend Service")
            actors.append(svc)

            if "Cache" in result.services:
                cache = Redis("Cache")
                actors.append(cache)

            if result.has_db:
                db = _db_nodes(result.tech)[0]
                actors.append(db)

            if "Message Queue" in result.services:
                mq_tech = " ".join(result.tech.get("infra", []))
                mq = Kafka("MQ") if "Kafka" in mq_tech else RabbitMQ("MQ")
                actors.append(mq)
                worker = Server("Worker")
                actors.append(worker)

            # Chain: User → FE → GW → Auth → SVC → Cache → DB
            chain = actors[:]
            colors = ["#2196F3", "#4CAF50", "#FF5722", "#9C27B0", "#FF9800"]
            for i in range(len(chain) - 1):
                color = colors[i % len(colors)]
                chain[i] >> Edge(color=color, label=str(i + 1)) >> chain[i + 1]

            # Return path (dashed)
            for i in range(len(chain) - 1, 0, -1):
                color = colors[(i - 1) % len(colors)]
                chain[i] >> Edge(color=color, style="dashed") >> chain[i - 1]

            # Sample route annotations
            if result.routes:
                sample = " | ".join(
                    f"{r.method} {r.path}" if r.method != "ANY" else r.path
                    for r in result.routes[:3]
                )
                gw >> Edge(label=f"Routes: {sample}", color="#795548", style="dotted") >> svc

        return _read_png(out)


# ─── 6. ER diagram as a cluster layout ───────────────────────────────────────

def er_png(result: "AnalysisResult") -> bytes:
    if not result.models:
        return b""   # caller should fall back to Mermaid text

    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "er")
        with Diagram(
            f"{result.owner}/{result.repo}  —  Data Model",
            filename=out, show=False, direction="TB",
            graph_attr={**_GRAPH_ATTR, "splines": "ortho"},
            node_attr=_NODE_ATTR, edge_attr=_EDGE_ATTR,
        ):
            model_nodes: dict = {}
            drawn: set = set()

            with Cluster("Entities"):
                for model in result.models[:20]:
                    model_nodes[model.name] = SQL(model.name)

            # FK relationships
            for model in result.models[:20]:
                for field in model.fields:
                    if field.related_model and field.related_model in model_nodes:
                        pair = tuple(sorted([model.name, field.related_model]))
                        if pair not in drawn:
                            drawn.add(pair)  # type: ignore[arg-type]
                            model_nodes[model.name] >> Edge(
                                label=field.name,
                                color="#E91E63",
                            ) >> model_nodes[field.related_model]

        return _read_png(out)


# ─── Public API ───────────────────────────────────────────────────────────────

def render(diagram_type: str, result: "AnalysisResult") -> tuple[bytes | None, str]:
    """
    Returns (png_bytes, error_message).
    png_bytes is None if rendering failed or diagrams is unavailable.
    """
    if not DIAGRAMS_AVAILABLE:
        return None, (
            "Graphviz / diagrams library not installed. "
            "Install Graphviz (https://graphviz.org/download) then run "
            "`pip install diagrams`. Showing Mermaid fallback below."
        )
    try:
        fn = {
            "architecture": architecture_png,
            "data_flow":    data_flow_png,
            "deployment":   deployment_png,
            "component":    component_png,
            "sequence":     sequence_png,
            "er":           er_png,
        }.get(diagram_type)

        if fn is None:
            return None, f"Unknown diagram type: {diagram_type}"

        data = fn(result)
        if not data:
            return None, "No data to render (e.g. no models found for ER diagram)."
        return data, ""

    except Exception as exc:
        return None, f"Image rendering failed: {exc}. Showing Mermaid fallback."
