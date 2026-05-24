# Changelog

All notable changes to **ivycode** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `.github/` collaboration scaffolding: CI workflow, issue/PR templates, CODEOWNERS, Dependabot, sponsor button.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, `Makefile`, `.editorconfig`.

## [0.5.0] — 2026-05-24

### Added
- Skills command center — registry, store, `@skill` decorator, FS and CodeGraph built-ins.
- CLI integration for skills (`ivycode skills list`, `ivycode skills run`).

## [0.4.0] — 2026-05-24

### Added
- CodeGraph foundation — SQLite-backed symbol index, FastAPI route extraction.
- `search_symbols`, `get_impact_radius`, `get_framework_routes` queries.
- `ivycode index --force` command.

## [0.3.0] — 2026-05-24

### Added
- Provider foundation — `ProviderProfile`, `TransportConfig`, OpenAI-compatible chat codec.
- `HttpProvider` + `ProviderFactory` with per-profile `httpx.AsyncClient` pooling.

## [0.2.0] — 2026-05-24

### Added
- Rich UI theme tokens, console singleton, static `Layout`, basic `MessagePanel`.
- Quiet Luxury palette wired through `ui/theme.py`.

## [0.1.0] — 2026-05-24

### Added
- Project metadata and strict tooling (ruff, mypy, pytest, hatchling).
- Immutable Pydantic envelope contracts (`Message`, `StreamEvent`, `CallerMeta`).
- Runtime settings with `IVYCODE_` env support.
- Typer entrypoint and `ivycode doctor`.

[Unreleased]: https://github.com/whipedev/ivycode/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/whipedev/ivycode/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/whipedev/ivycode/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/whipedev/ivycode/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/whipedev/ivycode/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/whipedev/ivycode/releases/tag/v0.1.0
