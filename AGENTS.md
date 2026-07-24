# Repository Guidelines

## Project Structure & Module Organization

BottleCRM is a multi-tenant CRM with a Django REST API, SvelteKit web app, Flutter app, and MCP integration. Backend apps live in `backend/` (for example, `common/`, `leads/`, `opportunity/`) with their models, views, serializers, URLs, migrations, and tests. Shared tenant/RLS code is in `backend/common/`, and Django settings are in `backend/crm/`. The web app is in `frontend/src/`, with pages under `routes/`, UI under `lib/`, and static files in `frontend/static/`. Flutter code and tests are in `mobile/`; MCP code and tests are in `mcp_server/src/bcrm_mcp/` and `mcp_server/tests/`.

## Organization Context

Bruens Duurzame Technieken is the only company that will use this CRM. Its organization ID is `ed15ae00-82e8-4b7b-bf42-a50db01650a6`, and its status is active. At the time this context was recorded, it had 127 leads, 0 accounts, and 0 contacts. Treat this organization as the sole production tenant unless instructed otherwise.

## Build, Test, and Development Commands

- `docker compose up --build` starts the complete local stack.
- From `backend/`, run `uv sync`, then `uv run python manage.py migrate` and `uv run python manage.py runserver`.
- `cd backend && uv run pytest` runs Django tests with coverage; use `uv run pytest --no-cov -x` for a quick failure-focused run.
- `cd frontend && pnpm install && pnpm run dev` starts the web client. Use `pnpm run check`, `pnpm run lint`, and `pnpm run build` before submission.
- `cd mobile && flutter analyze && flutter test` checks the Flutter app. Use `dart format .` to format Dart.
- `cd mcp_server && uv run pytest` runs MCP-server tests.

## Coding Style & Naming Conventions

Use four spaces and double quotes for Python. Ruff (`backend/ruff.toml`) enforces E, F, and import-order rules; run `uv run ruff check .` and `uv run ruff format .` from `backend/`. Follow Django conventions: `snake_case` modules/functions, `PascalCase` classes, and descriptive migration names. Svelte/JavaScript is formatted by Prettier with two spaces, single quotes, no trailing commas, and 100-column width; run `pnpm run format`. Keep Svelte components `PascalCase.svelte` and route files in SvelteKit’s required `+page.*`/`+server.*` form.

## Testing Guidelines

Add or update focused tests beside the relevant feature: Django tests use `test_*.py`, MCP tests live in `mcp_server/tests/`, and Flutter tests use `*_test.dart`. Pytest runs with coverage and strict markers; mark database-specific tests with `@pytest.mark.postgres_only` and slow tests with `@pytest.mark.slow`. Exercise organization boundaries whenever changing tenant-scoped backend data or RLS behavior.

## Commit & Pull Request Guidelines

Use concise Conventional Commit-style subjects reflected in history: `feat: add export`, `fix: prevent duplicate leads`, or `refactor: simplify auth flow`. Keep commits narrowly scoped. PRs should explain user-visible and architectural changes, link the relevant issue, list tests run, include screenshots for UI changes, and call out migrations, configuration, or RLS/security implications.
