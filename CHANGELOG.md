# Changelog

This project follows a lightweight SemVer-ish scheme:

- `vMAJOR.MINOR.PATCH` tags are installable via Codex skill-installer `--ref`.
- `PATCH` is for fixes and doc/script improvements.
- `MINOR` is for backward-compatible feature additions.
- `MAJOR` is for breaking changes (avoid if possible).

## Unreleased

- (placeholder)

## v0.1.3 - 2026-02-04

- Docs: added upstream repo reference and a brief summary of the upstream-reported effectiveness numbers.

## v0.1.2 - 2026-02-04

- Docs: added explicit instructions for **opt-in (explicit use)** vs **default use** configuration.

## v0.1.1 - 2026-02-04

- Docs: added a 3-tier guide to approximate “prune on every file read”:
  - Tier 1: `developer_instructions` (soft guardrail)
  - Tier 2: Codex `rules` (strict mode)
  - Tier 3: shell-level alias/wrapper (advanced, risky)

## v0.1.0 - 2026-02-04

- Initial publishable Codex skill packaging for SWE-Pruner:
  - `pcat` (pruned cat) workflow for task-aware large-file reads
  - One-time model download script
  - Local server start scripts
  - Optional strict-mode Codex rules template (see `skills/swe-pruner/references/`)
