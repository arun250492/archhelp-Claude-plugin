"""
Static analysis of a GitHub repository's file tree and source content.

All analysis is purely syntactic (regex-based).  Raw file content is
consumed here and converted into structured data (sets of names, counts,
graphs).  Tool responses are built from that structured data — raw file
content is never included in the output, which prevents prompt-injection
attacks embedded in repository source files.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# ─── Language / role classification ──────────────────────────────────────────

_LANG_GROUPS: dict[str, frozenset[str]] = {
    "backend":  frozenset({".py", ".go", ".java", ".rb", ".php", ".rs", ".cs", ".cpp", ".c", ".kt"}),
    "frontend": frozenset({".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss"}),
    "data":     frozenset({".sql", ".prisma", ".graphql", ".gql", ".proto"}),
    "infra":    frozenset({".tf", ".yaml", ".yml", ".toml"}),
    "docs":     frozenset({".md", ".rst", ".txt"}),
}

def classify_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    name = Path(path).name
    for group, exts in _LANG_GROUPS.items():
        if ext in exts:
            return group
    if name in {"Dockerfile", "Makefile", "Procfile"}:
        return "infra"
    return "other"


# ─── Technology detection ─────────────────────────────────────────────────────

_ROOT_FRAMEWORK_MARKERS: dict[str, tuple[str, ...]] = {
    "Next.js":       ("next.config.js", "next.config.ts", "next.config.mjs"),
    "Nuxt.js":       ("nuxt.config.js", "nuxt.config.ts"),
    "Vue":           ("vue.config.js",),
    "SvelteKit":     ("svelte.config.js",),
    "Django":        ("manage.py",),
    "Rails":         ("Gemfile",),
    "Spring Boot":   ("pom.xml", "build.gradle"),
    "Laravel":       ("artisan",),
    "FastAPI/Flask": ("requirements.txt",),
    "Express":       ("package.json",),
    "NestJS":        ("nest-cli.json",),
}

_PATH_INFRA_MARKERS: dict[str, str] = {
    "Docker":          "Dockerfile",
    "Docker Compose":  "docker-compose",
    "Kubernetes":      "k8s",
    "Helm":            "helm",
    "Terraform":       ".tf",
    "GitHub Actions":  ".github/workflows",
    "GitLab CI":       ".gitlab-ci",
    "CircleCI":        ".circleci",
    "Nginx":           "nginx",
    "Redis":           "redis",
    "Celery":          "celery",
    "RabbitMQ":        "rabbitmq",
    "Kafka":           "kafka",
}

_PATH_DB_MARKERS = {
    "PostgreSQL": ("postgres", "pg"),
    "MySQL":      ("mysql",),
    "SQLite":     ("sqlite",),
    "MongoDB":    ("mongo",),
    "Redis DB":   ("redis",),
    "Prisma":     ("prisma",),
    "Elasticsearch": ("elasticsearch", "elastic"),
}


def detect_technologies(tree: list[dict]) -> dict[str, list[str]]:
    paths = [item["path"] for item in tree]
    path_blob = " ".join(paths).lower()
    root_files = {p for p in paths if "/" not in p}

    frameworks: list[str] = []
    for fw, markers in _ROOT_FRAMEWORK_MARKERS.items():
        if any(m in root_files for m in markers):
            frameworks.append(fw)

    infra: list[str] = []
    for name, marker in _PATH_INFRA_MARKERS.items():
        if marker.lower() in path_blob:
            infra.append(name)

    databases: list[str] = []
    for db, markers in _PATH_DB_MARKERS.items():
        if any(m in path_blob for m in markers):
            databases.append(db)

    lang_counts: dict[str, int] = defaultdict(int)
    for item in tree:
        if item.get("type") == "blob":
            ext = Path(item["path"]).suffix.lower()
            if ext:
                lang_counts[ext] += 1
    top_langs = sorted(lang_counts, key=lang_counts.__getitem__, reverse=True)[:8]

    return {
        "framework": frameworks,
        "infra":     infra,
        "databases": databases,
        "languages": top_langs,
    }


# ─── ORM model extraction ─────────────────────────────────────────────────────

class ModelField(NamedTuple):
    name: str
    field_type: str
    related_model: str | None  # e.g. "User" if this is a FK to User


class ModelDef(NamedTuple):
    name: str
    fields: list[ModelField]


_MODEL_PATTERNS: dict[str, re.Pattern] = {
    "django":     re.compile(r"^class\s+(\w+)\s*\([^)]*Model[^)]*\)", re.M),
    "sqlalchemy": re.compile(r"^class\s+(\w+)\s*\([^)]*(?:Base|db\.Model)[^)]*\)", re.M),
    "prisma":     re.compile(r"^model\s+(\w+)\s*\{", re.M),
    "typeorm":    re.compile(r"@Entity\(\)\s*(?:export\s+)?class\s+(\w+)", re.M),
    "sequelize":  re.compile(r"sequelize\.define\s*\(\s*['\"](\w+)['\"]", re.M),
    "rails":      re.compile(r"^class\s+(\w+)\s*<\s*(?:ApplicationRecord|ActiveRecord::Base)", re.M),
    "mongoose":   re.compile(r"new\s+Schema\s*\(\s*\{[^}]*\},\s*\{[^}]*collection\s*:\s*['\"](\w+)['\"]", re.M),
}

# FK / relationship patterns per ORM
_FK_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Django: user = models.ForeignKey('User',  or  models.ForeignKey(User,
    ("django", re.compile(r"=\s*models\.(?:ForeignKey|OneToOneField|ManyToManyField)\s*\(\s*['\"]?(\w+)['\"]?")),
    # SQLAlchemy: relationship("User")
    ("sqlalchemy", re.compile(r'relationship\s*\(\s*["\'](\w+)["\']')),
    # Prisma: authorId  Int  /  author   User  @relation
    ("prisma", re.compile(r"^\s*\w+\s+(\w+)\s+@relation", re.M)),
    # TypeORM: @ManyToOne(() => User)
    ("typeorm", re.compile(r"@(?:ManyToOne|OneToMany|OneToOne|ManyToMany)\s*\(\s*\(\)\s*=>\s*(\w+)")),
    # Rails: belongs_to :user
    ("rails", re.compile(r"(?:belongs_to|has_many|has_one)\s+:(\w+)")),
    # Sequelize: belongsTo(User)
    ("sequelize", re.compile(r"(?:belongsTo|hasMany|hasOne)\s*\(\s*(\w+)")),
]


def _pascal(name: str) -> str:
    """Convert snake_case or plural to a likely PascalCase model name."""
    singular = name.rstrip("s") if name.endswith("s") else name
    return "".join(w.capitalize() for w in re.split(r"[_\s]+", singular))


def extract_models(contents: dict[str, str]) -> list[ModelDef]:
    found: dict[str, ModelDef] = {}

    for path, content in contents.items():
        if not content:
            continue
        for orm, pattern in _MODEL_PATTERNS.items():
            for match in pattern.finditer(content):
                name = match.group(1)
                if name in ("Base", "Model", "AbstractModel", "TimeStampedModel"):
                    continue
                # Extract FK relations from the same block of text around the match
                block_start = match.start()
                block_end   = min(len(content), match.end() + 2000)
                block       = content[block_start:block_end]

                fields: list[ModelField] = []
                for _orm2, fk_pat in _FK_PATTERNS:
                    for fk_match in fk_pat.finditer(block):
                        related = _pascal(fk_match.group(1))
                        fields.append(ModelField(
                            name=fk_match.group(1),
                            field_type="FK",
                            related_model=related,
                        ))

                if name not in found:
                    found[name] = ModelDef(name=name, fields=fields)

    return list(found.values())


# ─── API route extraction ─────────────────────────────────────────────────────

class Route(NamedTuple):
    method: str
    path: str


_ROUTE_PATTERNS: list[tuple[str, re.Pattern]] = [
    # FastAPI / Flask decorators: @app.get("/users")
    ("decorator", re.compile(
        r'@(?:app|router|blueprint|api)\.'
        r'(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']',
        re.I | re.M,
    )),
    # Express: router.get('/users', ...)
    ("express", re.compile(
        r'router\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
        re.I | re.M,
    )),
    # Django urls.py: path('users/', ...)
    ("django_url", re.compile(r"path\s*\(\s*['\"]([^'\"]+)['\"]", re.M)),
    # Rails: get '/users'
    ("rails", re.compile(r"(?:get|post|put|patch|delete)\s+'([^']+)'", re.M)),
    # Spring: @GetMapping("/users")
    ("spring", re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)'
        r'\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
        re.M,
    )),
]

_METHOD_MAP = {
    "GetMapping":    "GET",
    "PostMapping":   "POST",
    "PutMapping":    "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping":  "PATCH",
    "RequestMapping": "ANY",
}


def extract_routes(contents: dict[str, str]) -> list[Route]:
    seen: set[tuple[str, str]] = set()
    routes: list[Route] = []

    for _path, content in contents.items():
        if not content:
            continue

        for style, pat in _ROUTE_PATTERNS:
            for m in pat.finditer(content):
                if style == "decorator" or style == "express":
                    method = m.group(1).upper()
                    route_path = m.group(2)
                elif style == "django_url":
                    method = "ANY"
                    route_path = "/" + m.group(1).lstrip("/")
                elif style == "rails":
                    method = "ANY"
                    route_path = m.group(1)
                elif style == "spring":
                    method = _METHOD_MAP.get(m.group(1), "ANY")
                    route_path = m.group(2)
                else:
                    continue

                key = (method, route_path)
                if key not in seen and len(routes) < 50:
                    seen.add(key)
                    routes.append(Route(method=method, path=route_path))

    return routes


# ─── Module dependency graph ──────────────────────────────────────────────────

_IMPORT_PATTERNS: dict[str, re.Pattern] = {
    ".py":   re.compile(r"^(?:from|import)\s+([\w.]+)", re.M),
    ".ts":   re.compile(r'(?:import|require)\s*(?:.*?from\s*)?["\']([^"\']+)["\']', re.M),
    ".tsx":  re.compile(r'(?:import|require)\s*(?:.*?from\s*)?["\']([^"\']+)["\']', re.M),
    ".js":   re.compile(r'(?:import|require)\s*(?:.*?from\s*)?["\']([^"\']+)["\']', re.M),
    ".jsx":  re.compile(r'(?:import|require)\s*(?:.*?from\s*)?["\']([^"\']+)["\']', re.M),
    ".go":   re.compile(r'"([^"]+)"', re.M),
    ".java": re.compile(r"^import\s+([\w.]+);", re.M),
    ".rs":   re.compile(r"^use\s+([\w:]+)", re.M),
    ".rb":   re.compile(r"^require[_all]?\s+['\"]([^'\"]+)['\"]", re.M),
}


def extract_top_dirs(tree: list[dict]) -> list[str]:
    dirs: set[str] = set()
    for item in tree:
        if item.get("type") == "tree":
            top = item["path"].split("/")[0]
            dirs.add(top)
    return sorted(dirs)


def build_module_graph(
    tree: list[dict], contents: dict[str, str]
) -> dict[str, set[str]]:
    top_dirs = set(extract_top_dirs(tree))
    graph: dict[str, set[str]] = defaultdict(set)

    for file_path, content in contents.items():
        if not content or "/" not in file_path:
            continue
        ext = Path(file_path).suffix.lower()
        pat = _IMPORT_PATTERNS.get(ext)
        if not pat:
            continue

        src_module = file_path.split("/")[0]
        for m in pat.finditer(content):
            imported = m.group(1).split(".")[0].split("/")[0].lstrip(".")
            if imported in top_dirs and imported != src_module:
                graph[src_module].add(imported)

    return {k: v for k, v in graph.items() if v}


# ─── Services / middleware detection ─────────────────────────────────────────

_SERVICE_PATTERNS = {
    "Auth / JWT":   re.compile(r"jwt|auth|token|oauth|passport|devise|omniauth", re.I),
    "Message Queue": re.compile(r"rabbitmq|celery|kafka|sidekiq|bull|sqs|pubsub", re.I),
    "Cache":        re.compile(r"redis|memcache|cache", re.I),
    "Email":        re.compile(r"sendgrid|ses|smtp|mailgun|nodemailer|actionmailer", re.I),
    "Storage":      re.compile(r"s3|gcs|blob|minio|cloudinary|active.?storage", re.I),
    "Search":       re.compile(r"elasticsearch|algolia|solr|typesense|meilisearch", re.I),
    "Payments":     re.compile(r"stripe|paypal|braintree|square", re.I),
    "Monitoring":   re.compile(r"sentry|datadog|newrelic|prometheus|grafana|opentelemetry", re.I),
}


def detect_services(tree: list[dict], contents: dict[str, str]) -> list[str]:
    path_blob   = " ".join(item["path"] for item in tree).lower()
    content_blob = " ".join(contents.values())[:200_000].lower()
    corpus = path_blob + " " + content_blob

    return [name for name, pat in _SERVICE_PATTERNS.items() if pat.search(corpus)]


# ─── High-level analysis result ───────────────────────────────────────────────

class AnalysisResult(NamedTuple):
    owner:          str
    repo:           str
    total_files:    int
    analyzed_files: int
    top_dirs:       list[str]
    tech:           dict[str, list[str]]
    models:         list[ModelDef]
    routes:         list[Route]
    module_graph:   dict[str, set[str]]
    services:       list[str]
    has_frontend:   bool
    has_backend:    bool
    has_db:         bool
    has_infra:      bool
    has_auth:       bool
