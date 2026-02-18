---
name: terminal-data
description: Coding standards and architectural patterns for the terminal-data project.
---

# Terminal Data Skill

This skill documents the core architecture, coding standards, and common patterns for the `terminal` project.

## Architectural Pattern: Functional Dispatch

The project follows a functional service pattern inspired by the Netflix Dispatch architecture.

- **Services (`src/terminal/*/service.py`)**:
  - Should contain standalone functions, not classes.
  - Accept `SQLModel` objects and Pydantic schemas as arguments.
  - Return `Optional` or business objects.
  - Avoid HTTP-level exceptions (raise business exceptions or return `None`).
- **Routers (`src/terminal/*/router.py`)**:
  - Handle authentication and dependency injection.
  - Responsible for resource loading and ownership verification.
  - Handle HTTP-level exceptions (e.g., `raise HTTPException(status_code=404)`).
  - Delegate business logic to services by passing loaded objects and schemas.

## Coding Standards

### Type Annotations

- Use **Python 3.14+** type annotation style.
- Prefer `| None` over `Optional`.
- Avoid `Union` where `|` can be used.

### Data Models

- Use `SQLModel` for database entities.
- Use `Pydantic` (via `TerminalBase`) for API request/response schemas.
- Ensure strict separation between DB models and API schemas.

## Common Tasks

### Testing

- Run tests using `uv run pytest tests`.
- Ensure all tests pass before committing.

### Linting

- Use `ruff` for linting and formatting.
- Run `ruff check --fix .` to auto-fix issues.
