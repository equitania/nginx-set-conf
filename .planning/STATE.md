# Project State

## Project Reference

See: `.planning/PROJECT.md` (initialized 2026-05-28)

**Core value:** A YAML-driven generator must never become a privileged file-write surface on the host, and a routine deploy must never take nginx down.
**Current focus:** Phase 1 — Privileged write-surface hardening

## Current Position

Phase: 1 of 6 (Privileged write-surface hardening)
Plan: 0 of TBD (planning not yet run)
Status: Ready to plan
Last activity: 2026-05-28 — `/gsd:discuss-phase --all` added HTTP/2 fix (Phase 2.5) and HTTP/3 opt-in (Phase 5) to scope; 2 CONTEXT.md files written

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Privileged write-surface hardening | 0 / TBD | — | — |
| 2. Cache + template substitution consolidation | 0 / TBD | — | — |
| 2.5. HTTP/2 actually enabled (INSERTED) | 0 / 1 | — | — |
| 3. Tech debt + repository cleanup | 0 / TBD | — | — |
| 4. Docs, open questions, release | 0 / TBD | — | — |
| 5. HTTP/3 opt-in support | 0 / 4 | — | — |

## Recent Releases (out-of-GSD context)

| Version | Date | Type | Summary |
|---------|------|------|---------|
| v1.11.1 | 2026-05-28 | Security patch (direct sprint, pre-GSD) | 3 HIGH findings fixed: pre-reload `nginx -t`, `auth_file` constraints, wildcard filename sanitisation |
| v1.11.0 | 2026-04-22 | Minor | IP-bound `listen` directives (Pattern C) |
| v1.10.2 | 2026-04-21 | Patch (rollback fix) | Restored hostname-bound default; opt-in `--migrate_to_wildcard` |
| v1.10.0 | 2026-04-21 | Reverted | Wildcard listens — caused SNI fallback leak, reverted same day |

## Next Action

Run `/gsd:plan-phase 1` to break Phase 1 into executable plans.

---

*State initialized: 2026-05-28*
