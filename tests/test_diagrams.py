"""Unit tests for the Mermaid diagram generators (diagrams.py)."""

from __future__ import annotations

import re
import pytest
from server import diagrams
from server.analyzer import ModelDef, ModelField, Route


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_valid_mermaid_block(text: str) -> bool:
    return text.strip().startswith("```mermaid") and text.strip().endswith("```")


def _node_ids(text: str) -> list[str]:
    """Extract all bare node/participant IDs declared in a Mermaid block."""
    return re.findall(r"^\s{4}(\w+)\[", text, re.M)


# ─── Architecture diagram ─────────────────────────────────────────────────────

def test_architecture_is_valid_mermaid(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert _is_valid_mermaid_block(out)


def test_architecture_contains_graph_tb(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "graph TB" in out


def test_architecture_has_client_layer(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "Client Layer" in out


def test_architecture_has_backend_layer(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "Backend Layer" in out


def test_architecture_has_data_layer(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "Data Layer" in out


def test_architecture_shows_auth_service(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "AUTH" in out or "Auth" in out


def test_architecture_minimal_no_frontend(minimal_result):
    out = diagrams.architecture(minimal_result)
    assert "Client Layer" not in out
    assert _is_valid_mermaid_block(out)


def test_architecture_minimal_no_db(minimal_result):
    out = diagrams.architecture(minimal_result)
    assert "Data Layer" not in out


def test_architecture_shows_infra(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    assert "Infrastructure" in out


def test_architecture_no_special_chars_in_node_ids(fullstack_result):
    out = diagrams.architecture(fullstack_result)
    for nid in _node_ids(out):
        assert re.match(r"^\w+$", nid), f"Bad node id: {nid!r}"


# ─── Data flow diagram ────────────────────────────────────────────────────────

def test_data_flow_is_valid_mermaid(fullstack_result):
    assert _is_valid_mermaid_block(diagrams.data_flow(fullstack_result))


def test_data_flow_has_flowchart_lr(fullstack_result):
    assert "flowchart LR" in diagrams.data_flow(fullstack_result)


def test_data_flow_shows_routes(fullstack_result):
    out = diagrams.data_flow(fullstack_result)
    assert "/api/users" in out or "api_users" in out


def test_data_flow_shows_cache_when_present(fullstack_result):
    out = diagrams.data_flow(fullstack_result)
    assert "Cache" in out or "CACHE" in out


def test_data_flow_no_cache_when_absent(minimal_result):
    out = diagrams.data_flow(minimal_result)
    assert "CACHE" not in out


def test_data_flow_shows_mq_when_present(fullstack_result):
    out = diagrams.data_flow(fullstack_result)
    assert "MQ" in out or "Queue" in out


# ─── ER diagram ───────────────────────────────────────────────────────────────

def test_er_no_models_returns_message():
    out = diagrams.er_diagram([])
    assert "No ORM models detected" in out
    assert "```" not in out


def test_er_is_valid_mermaid(fullstack_result):
    assert _is_valid_mermaid_block(diagrams.er_diagram(fullstack_result.models))


def test_er_contains_erdiagram(fullstack_result):
    assert "erDiagram" in diagrams.er_diagram(fullstack_result.models)


def test_er_shows_model_names(fullstack_result):
    out = diagrams.er_diagram(fullstack_result.models)
    for model in fullstack_result.models:
        assert model.name in out


def test_er_shows_relationships(fullstack_result):
    out = diagrams.er_diagram(fullstack_result.models)
    # Post has FK to User → expect a relation line
    assert "Post" in out
    assert "User" in out
    assert "||" in out or "}o" in out


def test_er_caps_at_25_models():
    many_models = [ModelDef(name=f"Model{i}", fields=[]) for i in range(40)]
    out = diagrams.er_diagram(many_models)
    assert out.count(" {") <= 25


def test_er_no_duplicate_relations():
    models = [
        ModelDef("A", [ModelField("b_id", "FK", "B")]),
        ModelDef("B", [ModelField("a_id", "FK", "A")]),
    ]
    out = diagrams.er_diagram(models)
    # The same pair should only appear once
    relation_lines = [l for l in out.splitlines() if "||" in l or "}o" in l]
    assert len(relation_lines) <= 2  # at most one per directed edge stored


# ─── Sequence diagram ─────────────────────────────────────────────────────────

def test_sequence_is_valid_mermaid(fullstack_result):
    assert _is_valid_mermaid_block(diagrams.sequence(fullstack_result))


def test_sequence_has_autonumber(fullstack_result):
    assert "autonumber" in diagrams.sequence(fullstack_result)


def test_sequence_shows_auth_steps(fullstack_result):
    out = diagrams.sequence(fullstack_result)
    assert "AUTH" in out


def test_sequence_no_auth_when_absent(minimal_result):
    out = diagrams.sequence(minimal_result)
    assert "AUTH" not in out


def test_sequence_shows_cache_branch(fullstack_result):
    out = diagrams.sequence(fullstack_result)
    assert "Cache" in out or "CACHE" in out
    assert "alt" in out  # alt/else block for cache hit/miss


def test_sequence_shows_route_note(fullstack_result):
    out = diagrams.sequence(fullstack_result)
    assert "Note" in out


def test_sequence_minimal_no_frontend(minimal_result):
    out = diagrams.sequence(minimal_result)
    assert "FE" not in out


# ─── Component diagram ────────────────────────────────────────────────────────

def test_component_is_valid_mermaid(fullstack_result):
    assert _is_valid_mermaid_block(diagrams.component(fullstack_result))


def test_component_has_graph_lr(fullstack_result):
    assert "graph LR" in diagrams.component(fullstack_result)


def test_component_shows_top_dirs(fullstack_result):
    out = diagrams.component(fullstack_result)
    for d in ["frontend", "backend", "api"]:
        assert d in out


def test_component_shows_edges(fullstack_result):
    out = diagrams.component(fullstack_result)
    assert "-->" in out


def test_component_no_invalid_node_ids(fullstack_result):
    out = diagrams.component(fullstack_result)
    for nid in _node_ids(out):
        assert re.match(r"^\w+$", nid), f"Bad node id: {nid!r}"


def test_component_empty_module_graph(minimal_result):
    out = diagrams.component(minimal_result)
    assert _is_valid_mermaid_block(out)


# ─── Deployment diagram ───────────────────────────────────────────────────────

def test_deployment_is_valid_mermaid(fullstack_result):
    assert _is_valid_mermaid_block(diagrams.deployment(fullstack_result))


def test_deployment_has_graph_tb(fullstack_result):
    assert "graph TB" in diagrams.deployment(fullstack_result)


def test_deployment_shows_containers(fullstack_result):
    out = diagrams.deployment(fullstack_result)
    assert "Container" in out or "DOCKER" in out or "K8S" in out


def test_deployment_shows_terraform(fullstack_result):
    out = diagrams.deployment(fullstack_result)
    assert "Terraform" in out or "TF" in out


def test_deployment_shows_ci(fullstack_result):
    out = diagrams.deployment(fullstack_result)
    assert "CI" in out or "Actions" in out


def test_deployment_shows_external_services(fullstack_result):
    out = diagrams.deployment(fullstack_result)
    assert "Monitoring" in out or "Email" in out


def test_deployment_minimal(minimal_result):
    out = diagrams.deployment(minimal_result)
    assert _is_valid_mermaid_block(out)
    assert "Container" not in out
    assert "Terraform" not in out
