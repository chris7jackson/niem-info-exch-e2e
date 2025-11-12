# Contributing to NIEM Information Exchange

Thanks for your interest in contributing! This guide will help you get started.

## Quick Start

1. **Fork and clone** the repository
2. **Set up your environment** - Follow the [Quick Start in README.md](README.md#quick-start)
3. **Create a branch** for your changes
4. **Make your changes** following our guidelines below
5. **Submit a pull request**

## Development Setup

See the [README Quick Start](README.md#quick-start) for:
- Prerequisites (Docker, ports, etc.)
- Starting the system with Docker Compose
- Accessing the UI and services
- Rebuilding after code changes

### Local Development Setup (without Docker)

For API development without Docker, we use [uv](https://docs.astral.sh/uv/) for Python dependency management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to API directory
cd api

# Install dependencies (includes dev dependencies)
uv sync --all-extras

# Run the API server
uv run uvicorn src.niem_api.main:app --reload
```

Dependencies are managed in `api/pyproject.toml` and locked in `api/uv.lock`.

## Architecture Overview

This project follows a layered architecture. Before making changes, familiarize yourself with:

- **[docs/API_ARCHITECTURE.md](docs/API_ARCHITECTURE.md)** - Backend layer separation
- **[CLAUDE.md](CLAUDE.md)** - Development guardrails and conventions

### Key Principles

- **handlers/** - HTTP orchestration only, no business logic
- **services/** - Domain logic (schema, xml_to_graph, graph)
- **clients/** - Thin wrappers to Neo4j/MinIO/CMF with timeouts
- Keep changes local to one layer unless explicitly refactoring

## Code Style & Quality

### Python (API)

- Follow conventions in [CLAUDE.md](CLAUDE.md#quality--security-poc-strict)
- Use type hints for all function parameters and returns
- Run `ruff` and `black` on changes
- No `print` statements - use structured logging
- Validate all inputs (Pydantic models)
- Parameterize Cypher queries (never string interpolation)

### TypeScript (UI)

- Avoid `any` in new code
- Props should be read-only
- Extract nested ternaries into independent statements
- Follow existing component patterns

## Testing Requirements

All code changes must include tests. See [docs/UNIT_TESTING.md](docs/UNIT_TESTING.md) for comprehensive testing guide.

**Run tests:**
```bash
# API tests
cd api
uv run pytest

# UI tests
cd ui
npm test
```

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/). See [CLAUDE.md](CLAUDE.md#commit-structure--conventions) for full details.

**Format:**
```
<type>: <short summary in present tense>

<optional body explaining WHY and WHAT changed>
```

**Types:**
- `feat:` - New feature or enhancement
- `fix:` - Bug fix
- `refactor:` - Code restructuring without behavior change
- `test:` - Add/update tests
- `docs:` - Documentation only
- `chore:` - Build/tooling/dependencies

**Example:**
```
feat: add JSON validation error aggregation

Updated JSON Schema validation to collect and display all errors
in a single response instead of stopping at the first error.

- Switched from validate() to iter_errors()
- Added HTTPException re-raising to preserve error details
```

**Guidelines:**
- Max 72 chars for subject line
- Use imperative mood ("add" not "added")

## Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** following the guidelines above

3. **Write/update tests** - PRs without tests may be rejected

4. **Ensure tests pass**
   ```bash
   # API
   cd api && uv run pytest

   # UI (if UI changes)
   cd ui && npm test
   ```

5. **Commit using conventional commits**

6. **Push and create PR** with:
   - Clear description of what changed and why
   - Reference any related issues
   - Note any breaking changes

## Finding Your Way Around

| Need to... | Look in... |
|------------|------------|
| Add API endpoint | `api/src/niem_api/main.py` (routes) → `handlers/` |
| Add business logic | `api/src/niem_api/services/domain/` |
| Add external service integration | `api/src/niem_api/clients/` |
| Understand API architecture | `docs/API_ARCHITECTURE.md` |
| Write tests | `docs/UNIT_TESTING.md` |
| Check CI/CD | `docs/CI_CD_PIPELINE.md` |

## Questions or Issues?

- Check existing documentation in `docs/`
- Search [GitHub Issues](../../issues)
- Review the [README](README.md) and [CLAUDE.md](CLAUDE.md)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
