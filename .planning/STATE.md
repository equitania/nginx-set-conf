---
gsd_state_version: 1.0
milestone: v1.11.1
milestone_name: milestone
status: executing
last_updated: "2026-05-31T11:08:19.335Z"
last_activity: 2026-05-31
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 17
  completed_plans: 14
  percent: 82
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (initialized 2026-05-28)

**Core value:** A YAML-driven generator must never become a privileged file-write surface on the host, and a routine deploy must never take nginx down.
**Current focus:** Phase 05 — http3-opt-in-support

## Current Position

Phases 1–4 (+2.5): COMPLETE — 13 / 13 plans across NSC-01..NSC-04 + 02.5.
v1.12.0 released (GSD milestone output). v1.13.0 released out-of-GSD (PatchMon
template, commit 089b9db, 2026-05-31).
Phase: 05 (http3-opt-in-support) — EXECUTING
Plan: 2 of 4
Status: Executing Phase 05
Last activity: 2026-05-31 -- 05-01 complete: --enable_http3 plumbing + HTTP3_EXCLUDED_TEMPLATES

Progress: [████████░░] 82%

## Open Verification Debt

- NSC-03 `03-VERIFICATION.md`: status `human_needed` — manual test run still
  outstanding. Non-blocking. Review via `/gsd-audit-uat`.

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Privileged write-surface hardening | 4 / 4 | ~24 min | ~6 min |
| 2. Cache + template substitution consolidation | 0 / 3 | — | — |
| 2.5. HTTP/2 actually enabled (INSERTED) | 0 / 1 | — | — |
| 3. Tech debt + repository cleanup | 0 / TBD | — | — |
| 4. Docs, open questions, release | 0 / TBD | — | — |
| 5. HTTP/3 opt-in support | 0 / 4 | — | — |
| Phase 02 P01 | 12m | 3 tasks | 3 files |
| 02 | 3 | - | - |
| Phase 04 P01 | 18m | 3 tasks | 6 files |

## Recent Releases (out-of-GSD context)

| Version | Date | Type | Summary |
|---------|------|------|---------|
| v1.13.0 | 2026-05-31 | Minor (out-of-GSD direct feature) | PatchMon nginx template — single-port Go server, WebSocket support for in-browser RDP (guacd); no rate-limit. NOTE: this consumed the v1.13.0 number ROADMAP §306 earmarked for Phase 5 — HTTP/3 now targets v1.14.0 |
| v1.12.0 | 2026-05-29 | Minor (GSD milestone output) | Phases 1–4: write-surface hardening, cache/template consolidation, real HTTP/2, tech-debt cleanup, docs + `--force` sync gate |
| v1.11.1 | 2026-05-28 | Security patch (direct sprint, pre-GSD) | 3 HIGH findings fixed: pre-reload `nginx -t`, `auth_file` constraints, wildcard filename sanitisation |
| v1.11.0 | 2026-04-22 | Minor | IP-bound `listen` directives (Pattern C) |
| v1.10.2 | 2026-04-21 | Patch (rollback fix) | Restored hostname-bound default; opt-in `--migrate_to_wildcard` |
| v1.10.0 | 2026-04-21 | Reverted | Wildcard listens — caused SNI fallback leak, reverted same day |

## Decisions

- Strip orphaned proxy_cache_path/limit_req_zone from redirect templates via TDD RED/GREEN cycle
- cert_key interactive prompt uses existing retrieve_valid_input helper; empty string is valid for LE auto-generation
- DOC-01: CLAUDE.md Important Files corrected — all_templates.py is the home of replace_cache_path() and CACHE_PATH_SENTINEL; __init__.py covers version only
- Q-01: --migrate_to_ip_bound not implemented; MIG-01 deferred to v2; manual per-vhost regeneration procedure documented in README
- Q-02: --force gate implemented on --sync_config; warn-and-abort without --force, proceed-with-notice with --force; interactive prompt removed
- Re-audit CONCERNS.md: zero HIGH / zero MEDIUM open findings confirmed after Phases 1-4
- v1.12.0 release: RELEASE_NOTES finalised, version bumped, git tag v1.12.0 created locally
- bump-my-version v1.3.0: TOML files[] not auto-resolved; workaround via explicit CLI flags
- v1.13.0 (out-of-GSD): PatchMon template added directly; version bumped manually (NOT via bump-my-version, to avoid its auto-commit/tag). This took the v1.13.0 slot ROADMAP §306 had reserved for Phase 5 → HTTP/3 now targets v1.14.0
- 05-01: --enable_http3 is_flag wired CLI → YAML → execute_commands → validate_all_inputs; HTTP3_EXCLUDED_TEMPLATES frozenset (6 templates) in validators.py with exclusion guard; default_ssl_reject excluded from HTTP3 guard via validate_config_template (not in VALID_TEMPLATES)

## Next Action

Execute Phase 05 Plan 02 (HTTP/3 directive emission in templates).

Outstanding operator tasks (release publishing — local-only, never CI):

- Push branch `2026` + tags `v1.12.0` / `v1.13.0` to origin + upstream
- `uv build` + `uvpublish` for v1.13.0; confirm PyPI shows nginx-set-conf 1.13.0

---

*State initialized: 2026-05-28*
