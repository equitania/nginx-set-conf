---
phase: 04-docs-open-questions-release
plan: 02
subsystem: release-management
tags: [release, version-bump, concerns-audit, release-notes]
dependency_graph:
  requires:
    - "04-01 (DOC-01, Q-01, Q-02 implemented)"
  provides:
    - CONCERNS.md re-audited: zero HIGH/MEDIUM open findings annotated CLOSED
    - RELEASE_NOTES.md v1.12.0 finalised with date 29.05.2026 and all Phase 4 entries
    - pyproject.toml version = "1.12.0"
    - nginx_set_conf/__init__.py __version__ = "1.12.0"
    - git tag v1.12.0 (local, pending operator push)
  affects:
    - .planning/codebase/CONCERNS.md
    - RELEASE_NOTES.md
    - pyproject.toml
    - nginx_set_conf/__init__.py
tech_stack:
  added: []
  patterns:
    - bump-my-version with explicit CLI flags (v1.3.0 TOML files not auto-resolved)
key_files:
  created: []
  modified:
    - .planning/codebase/CONCERNS.md
    - RELEASE_NOTES.md
    - pyproject.toml
    - nginx_set_conf/__init__.py
decisions:
  - Re-audit confirms zero HIGH / zero MEDIUM open findings after Phases 1-4
  - bump-my-version v1.3.0 requires explicit --commit --tag flags; TOML files[] not auto-resolved
  - RELEASE_NOTES.md committed separately before bump so bump-my-version commit is version-only
metrics:
  duration: ~15 min
  completed: 2026-05-29
  tasks_completed: 2
  tasks_pending_operator: 1
  files_modified: 4
  files_created: 0
---

# Phase 04 Plan 02: Release v1.12.0 — Summary

**One-liner**: Re-audited CONCERNS.md confirming zero HIGH/MEDIUM open findings, finalised RELEASE_NOTES.md v1.12.0 with date and Phase 4 entries, bumped version to 1.12.0 and created local git tag v1.12.0 via bump-my-version.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Re-audit CONCERNS.md — confirm zero HIGH/MEDIUM open findings | 17351d3 | .planning/codebase/CONCERNS.md |
| 2a | Finalise RELEASE_NOTES.md v1.12.0 | 694e7e8 | RELEASE_NOTES.md |
| 2b | Run bump-my-version minor (1.11.1 → 1.12.0) | 8fc9783 | pyproject.toml, nginx_set_conf/__init__.py |

## Tasks Pending Operator (Task 3: checkpoint:human-action)

See checkpoint block below. Operator must push the tag to origin and upstream, then run `uv build` and `uvpublish` locally.

## What Was Built

### Task 1: CONCERNS.md Re-Audit

Added a re-audit header block at the top of CONCERNS.md:

```
## Re-Audit: Phase 4 Complete (29.05.2026)
All HIGH and MEDIUM findings closed by Phases 1–4 of the v1.12 roadmap.
Zero HIGH / Zero MEDIUM open findings.
LOW findings: all closed (see phase summaries above).
Open Questions: both resolved (Q-01, Q-02).
```

Annotated every finding with a `*(CLOSED — Phase N / Req-ID — description)*` line:

| Finding | Phase | Req-ID |
|---------|-------|--------|
| [HIGH] nginx restart before nginx -t | Phase 1 | HIGH-1 |
| [HIGH] auth_file template injection | Phase 1 | HIGH-2 |
| [HIGH] wildcard domain glob filename | Phase 1 | HIGH-3 |
| [MEDIUM] target_path whitespace bypass | Phase 1 | SEC-01 |
| [MEDIUM] backup symlink copytree | Phase 1 | SEC-02 |
| [MEDIUM] key file world-readable window | Phase 1 | SEC-03 |
| [LOW] retrieve_valid_input recursion | Phase 1 | SEC-04 |
| [HIGH] nginx -t after restart (correctness) | Phase 1 | HIGH-1 |
| [MEDIUM] dual cache-path pipeline | Phase 2 | COR-01 |
| [MEDIUM] redirect_ssl sentinel in log paths | Phase 2 | COR-02 |
| [MEDIUM] proxy_cache_path /tmp sentinel | Phase 2 | COR-03 |
| [LOW] default_ssl_reject absent from VALID_TEMPLATES | Phase 2 | COR-04 |
| [LOW] f-string back-reference repl | Phase 2 | COR-05 |
| [MEDIUM] egg-info dual identity | Phase 3 | TD-01 |
| [MEDIUM] config_templates.py shim | Phase 3 | TD-02 |
| [LOW] nginx_set_conf.log committed | Phase 3 | TD-03 |
| [LOW] build/dist gitignore | Phase 3 | TD-04 |
| [LOW] redirect templates unused directives | Phase 3 | TD-05 |
| [LOW] interactive mode cert_key | Phase 3 | TD-06 |
| [QUESTION] --migrate_to_ip_bound | Phase 4 | Q-01 |
| [QUESTION] --sync_config silent overwrite | Phase 4 | Q-02 |
| [LOW] CLAUDE.md replace_cache_path wrong file | Phase 4 | DOC-01 |
| [MEDIUM] HTTP/2 banner without directive | Phase 2.5 | PROTO-01 |

Verification: `grep -c "CLOSED" CONCERNS.md` → 23 lines.

### Task 2: RELEASE_NOTES.md + Version Bump

**RELEASE_NOTES.md changes:**
- `## Version 1.12.0 (development)` → `## Version 1.12.0 (29.05.2026)`
- Added `### Documentation` subsection: DOC-01 CLAUDE.md correction
- Added `### Tests` subsection: 209 passed, coverage 76%
- Added `### Migration` note: drop-in upgrade from v1.11.1; --sync_config --force is the only operator-visible change

**Version bump (bump-my-version bump minor):**
- `pyproject.toml`: `version = "1.11.1"` → `"1.12.0"`, `current_version` updated
- `nginx_set_conf/__init__.py`: `__version__ = "1.11.1"` → `"1.12.0"`
- Commit: `8fc9783` `[CHG] Bump version: 1.11.1 → 1.12.0`
- Tag: `v1.12.0` (local, not pushed)

**Test suite post-bump:** 209 passed, 2 skipped, 2 xpassed, coverage 76.08% — all green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] bump-my-version v1.3.0 TOML files[] not auto-resolved**
- **Found during:** Task 2
- **Issue:** `bump-my-version bump minor` reported "No configuration file found to update", "Would not commit", "Would not tag" even with `commit = true` and `tag = true` in `[tool.bump-my-version]`. The TOML configuration was correctly parsed (verified via `python3 -c "import tomllib..."`), but bump-my-version v1.3.0 did not apply it.
- **Fix:** Ran with explicit CLI flags: `--commit --tag --tag-name "v{new_version}"` plus the two file paths as positional args. This produced the correct file updates, commit, and tag.
- **Files modified:** pyproject.toml, nginx_set_conf/__init__.py (same as planned)
- **Commit:** 8fc9783

**2. [Rule 1 - Bug] RELEASE_NOTES.md committed separately before bump**
- **Found during:** Task 2
- **Issue:** bump-my-version only commits the files listed in its own config. RELEASE_NOTES.md is not in `[[tool.bump-my-version.files]]` and would be left as an unstaged modification if included in the same step.
- **Fix:** Committed RELEASE_NOTES.md in a separate commit (694e7e8) before running the bump. The bump commit (8fc9783) then contains only the version-bearing files — clean and traceable.
- **Commit:** 694e7e8

## Known Stubs

None — all documented behaviour is implemented, tested, and committed.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. Version bump and documentation edits only.

## Self-Check: PASSED

- CONCERNS.md Re-Audit header present: `grep "Re-Audit" .planning/codebase/CONCERNS.md` → FOUND
- CLOSED count: `grep -c "CLOSED" .planning/codebase/CONCERNS.md` → 23 (≥ 12 required)
- RELEASE_NOTES.md date: `grep "29.05.2026" RELEASE_NOTES.md` → FOUND
- pyproject.toml version: `grep 'version = "1.12.0"' pyproject.toml` → FOUND
- __init__.py version: `grep '__version__ = "1.12.0"' nginx_set_conf/__init__.py` → FOUND
- git tag v1.12.0: `git tag | grep v1.12.0` → v1.12.0
- Bump commit 8fc9783: present in `git log`
- Test suite: 209 passed, coverage 76% — all green
- Commits 17351d3, 694e7e8, 8fc9783: all present in git log
