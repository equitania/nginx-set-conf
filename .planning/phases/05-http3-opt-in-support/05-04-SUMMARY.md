---
phase: 05-http3-opt-in-support
plan: "04"
subsystem: documentation
tags: [docs, release-notes, version-bump, http3]
dependency_graph:
  requires: [05-01, 05-02, 05-03]
  provides: [v1.14.0-release-docs]
  affects: [README.md, RELEASE_NOTES.md, nginx_set_conf/__init__.py, pyproject.toml]
tech_stack:
  added: []
  patterns: [blockquote-warning-callout, included-excluded-template-table]
key_files:
  created: []
  modified:
    - README.md
    - RELEASE_NOTES.md
    - nginx_set_conf/__init__.py
    - pyproject.toml
decisions:
  - "HTTP/3 README section inserted after Intranet Configuration, before IP Access Restrictions"
  - "UDP/443 firewall requirement rendered as blockquote WARNING callout (prominent, plan-specified pattern)"
  - "Excluded templates: 6 (fast_report, mailpit, redirect, redirect_ssl, default_ssl_reject, odoo_http)"
  - "v1.14.0 RELEASE_NOTES entry is first section (newest-first ordering maintained)"
  - "--migrate_to_http3 deferral to v2 (PROTO-V2-01) documented in both README and RELEASE_NOTES"
  - "Version bumped manually (not via bump-my-version) per project convention"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-31"
  tasks_completed: 2
  files_changed: 4
---

# Phase 05 Plan 04: HTTP/3 Documentation and v1.14.0 Release — Summary

**One-liner:** Operator-facing HTTP/3 documentation (README section + RELEASE_NOTES v1.14.0 entry) with UDP/443 firewall callout, 12/6 template tables, and version bump 1.13.0 → 1.14.0.

## What Was Built

### Task 1 — README.md HTTP/3 / QUIC section (commit 6a5fde3)

Added a new `## HTTP/3 / QUIC (--enable_http3)` section to `README.md`, inserted after
"Intranet Configuration (disable_domain_listen)" and before "IP Access Restrictions".

The section contains:

1. **Overview paragraph** — opt-in flag, 12 templates, default off, browser HTTP/2 fallback.
2. **Prerequisites** (5 items):
   - nginx >= 1.25.0 with upgrade paths (Debian bookworm-backports, Ubuntu 24.04+, RHEL 9.4+); version gate description.
   - UDP/443 firewall opening — rendered as a prominent blockquote `> **WARNING — Firewall action required:**` with exact `ufw allow 443/udp` command.
   - TLS 1.3 scoping (HTTP/3 block only; TCP/HTTP/2 keeps TLS 1.2+1.3).
   - ECDSA certificate recommendation.
   - Explicit opt-in design.
3. **Usage** — CLI flag example and YAML `enable_http3: true` code block.
4. **Supported templates table** — 12 entries with rationale column.
5. **Excluded templates** — 6 entries with rationale.
6. **Catch-all requirement** — `--setup_default` for QUIC SNI catch-all; cross-reference to IP-bound Listen Directives section.
7. **Manual migration paragraph** — `--migrate_to_http3` not in this release, deferred to v2 (PROTO-V2-01), per-vhost regeneration procedure.

### Task 2 — RELEASE_NOTES v1.14.0 + version bump (commit ed8df99)

- **RELEASE_NOTES.md**: `## Version 1.14.0 (31.05.2026)` inserted as first section (before v1.13.0). Contains HTTP/3 feature bullets, generated directives list, prerequisites summary, excluded templates, "Not in this release" deferral note, and test count (242 tests).
- **nginx_set_conf/__init__.py**: `__version__ = "1.14.0"`.
- **pyproject.toml**: `version = "1.14.0"` (under `[project]`; no other version strings touched).
- Full pytest suite: **242 passed, 2 skipped, 2 xpassed** — all green.

## Verification Results

```
grep -c "HTTP/3 / QUIC" README.md    → 1   ✓
grep -c "UDP/443" README.md          → 2   ✓
grep -c "WARNING" README.md          → 1   ✓
grep -c "enable_http3" README.md     → 8   ✓
grep -c "nginx >= 1.25" README.md    → 1   ✓
grep -c "migrate_to_http3" README.md → 1   ✓
grep -c "setup_default" README.md    → 12  ✓
__version__ == '1.14.0'              → OK  ✓
grep '^version = ' pyproject.toml   → version = "1.14.0"  ✓
grep -c "Version 1.14.0" RELEASE_NOTES.md → 1  ✓
v1.14.0 line number < v1.13.0 line number  → 3 < 56  ✓
grep -c "UDP/443" RELEASE_NOTES.md  → 2   ✓
grep -c "migrate_to_http3" RELEASE_NOTES.md → 1  ✓
pytest 242 passed                    → ✓
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — documentation-only plan; no data stubs introduced.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- README.md HTTP/3 section: exists ✓
- RELEASE_NOTES.md v1.14.0 entry: exists as first section ✓
- `__version__ = "1.14.0"`: confirmed ✓
- `version = "1.14.0"` in pyproject.toml: confirmed ✓
- Commits 6a5fde3 and ed8df99: exist in git log ✓
- 242 tests passing: confirmed ✓
