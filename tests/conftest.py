"""Shared pytest fixtures for archhelp-claude-plugin tests."""

from __future__ import annotations

import pytest
from server.analyzer import AnalysisResult, ModelDef, ModelField, Route


@pytest.fixture()
def minimal_result() -> AnalysisResult:
    """Minimal result with no detected tech."""
    return AnalysisResult(
        owner="acme", repo="minimal",
        total_files=5, analyzed_files=3,
        top_dirs=["src"],
        tech={"framework": [], "infra": [], "databases": [], "languages": [".py"]},
        models=[], routes=[], module_graph={}, services=[],
        has_frontend=False, has_backend=True,
        has_db=False, has_infra=False, has_auth=False,
    )


@pytest.fixture()
def fullstack_result() -> AnalysisResult:
    """Full-stack app with auth, cache, queue, and DB."""
    models = [
        ModelDef(name="User",    fields=[]),
        ModelDef(name="Post",    fields=[ModelField("author_id", "FK", "User")]),
        ModelDef(name="Comment", fields=[ModelField("post_id", "FK", "Post"),
                                         ModelField("user_id", "FK", "User")]),
        ModelDef(name="Tag",     fields=[]),
        ModelDef(name="Order",   fields=[ModelField("user_id", "FK", "User")]),
    ]
    routes = [
        Route("GET",    "/api/users"),
        Route("POST",   "/api/users"),
        Route("GET",    "/api/users/{id}"),
        Route("PUT",    "/api/users/{id}"),
        Route("DELETE", "/api/users/{id}"),
        Route("GET",    "/api/posts"),
        Route("POST",   "/api/posts"),
        Route("GET",    "/api/auth/me"),
        Route("POST",   "/api/auth/login"),
        Route("POST",   "/api/auth/logout"),
    ]
    module_graph = {
        "frontend": {"api", "components"},
        "backend":  {"workers", "models"},
        "api":      {"backend"},
        "workers":  {"models"},
    }
    return AnalysisResult(
        owner="acme", repo="webapp",
        total_files=320, analyzed_files=80,
        top_dirs=["frontend", "backend", "api", "workers", "models", "infra", "migrations"],
        tech={
            "framework": ["React", "Next.js", "Django"],
            "infra":     ["Docker", "Kubernetes", "GitHub Actions", "Terraform"],
            "databases": ["PostgreSQL", "Redis"],
            "languages": [".py", ".ts", ".tsx", ".go"],
        },
        models=models,
        routes=routes,
        module_graph=module_graph,
        services=["Auth / JWT", "Cache", "Message Queue", "Email", "Monitoring"],
        has_frontend=True, has_backend=True,
        has_db=True, has_infra=True, has_auth=True,
    )


@pytest.fixture()
def sample_tree() -> list[dict]:
    return [
        {"path": "frontend",             "type": "tree"},
        {"path": "backend",              "type": "tree"},
        {"path": "infra",                "type": "tree"},
        {"path": ".github",              "type": "tree"},
        {"path": ".github/workflows",    "type": "tree"},
        {"path": "frontend/index.tsx",   "type": "blob"},
        {"path": "frontend/App.tsx",     "type": "blob"},
        {"path": "backend/models.py",    "type": "blob"},
        {"path": "backend/views.py",     "type": "blob"},
        {"path": "infra/Dockerfile",     "type": "blob"},
        {"path": "infra/k8s/deploy.yml", "type": "blob"},
        {"path": ".github/workflows/ci.yml", "type": "blob"},
        {"path": "manage.py",            "type": "blob"},
        {"path": "requirements.txt",     "type": "blob"},
    ]


@pytest.fixture()
def django_models_content() -> str:
    return """
from django.db import models

class User(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey('User', on_delete=models.CASCADE)
    tags = models.ManyToManyField('Tag')
    created_at = models.DateTimeField(auto_now_add=True)

class Comment(models.Model):
    body = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey('User', on_delete=models.CASCADE)

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
"""


@pytest.fixture()
def prisma_content() -> str:
    return """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  posts     Post[]
  createdAt DateTime @default(now())
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  content   String?
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int
}

model Comment {
  id      Int    @id @default(autoincrement())
  text    String
  post    Post   @relation(fields: [postId], references: [id])
  postId  Int
}
"""


@pytest.fixture()
def fastapi_routes_content() -> str:
    return """
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
async def list_users(): ...

@router.post("/users")
async def create_user(): ...

@router.get("/users/{user_id}")
async def get_user(user_id: int): ...

@router.put("/users/{user_id}")
async def update_user(user_id: int): ...

@router.delete("/users/{user_id}")
async def delete_user(user_id: int): ...

@router.post("/auth/login")
async def login(): ...

@router.post("/auth/logout")
async def logout(): ...
"""
