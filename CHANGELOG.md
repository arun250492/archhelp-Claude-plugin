# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No changes yet._

---

## [1.0.0] — 2026-05-26

### Added

- **8 MCP tools** exposed to Claude:
  - `analyze_repository` — all 6 diagrams + overview in one call
  - `generate_architecture_diagram`
  - `generate_data_flow_diagram`
  - `generate_er_diagram`
  - `generate_sequence_diagram`
  - `generate_component_diagram`
  - `generate_deployment_diagram`
  - `get_repo_overview`

- **ORM model extraction** from Django, SQLAlchemy, Prisma, TypeORM,
  Sequelize, Rails ActiveRecord, and Mongoose schemas, including
  foreign-key / relationship inference for accurate ER diagrams.

- **API route extraction** with HTTP method detection from FastAPI,
  Flask, Express, NestJS, Django `urls.py`, Rails routes, and Spring
  `@*Mapping` annotations.

- **Service detection**: Auth/JWT, Redis/Cache, Message Queues,
  Email providers, Cloud Storage, Search engines, Payment gateways,
  and Monitoring tools.

- **Technology detection**: 14 frameworks, 13 infrastructure tools,
  8 database engines, primary language ranking.

- **Module dependency graph** from import-statement analysis across
  Python, TypeScript, JavaScript, Go, Java, Rust, and Ruby.

- **Security layer** (`security.py`):
  - Strict repo-identifier validation (GitHub naming rules).
  - Prompt-injection protection: raw file content is never returned
    in tool responses.

- **Resilient GitHub client** (`github_client.py`):
  - Exponential back-off on 5xx errors.
  - `Retry-After`-aware rate-limit handling (429 / 403).
  - Per-request timeout (configurable via `GCA_REQUEST_TIMEOUT`).
  - `User-Agent` header for API identification.

- **Comprehensive test suite** (90 + test cases):
  - `test_security.py` — input validation edge cases.
  - `test_analysis.py` — unit tests for all analyser functions.
  - `test_diagrams.py` — unit tests for all 6 diagram generators.
  - `test_integration.py` — full pipeline tests with mocked HTTP
    (no real network calls).

- **GitHub Actions CI** with lint (`ruff`), type-check (`mypy`),
  tests + coverage (`pytest-cov`, threshold 80%), security scan
  (`bandit`), and plugin manifest validation.

- **pyproject.toml** with full project metadata, optional dev extras,
  and tool configuration for `pytest`, `ruff`, `mypy`, and `coverage`.

[Unreleased]: https://github.com/arun250492/archhelp-Claude-plugin/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/arun250492/archhelp-Claude-plugin/releases/tag/v1.0.0
