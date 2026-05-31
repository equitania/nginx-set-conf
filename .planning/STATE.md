---
gsd_state_version: 1.0
milestone: v1.11.1
milestone_name: milestone
status: verified
last_updated: "2026-05-31T14:00:00.000Z"
last_activity: 2026-05-31
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 17
  completed_plans: 17
  percent: 100
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (initialized 2026-05-28)

**Core value:** A YAML-driven generator must never become a privileged file-write surface on the host, and a routine deploy must never take nginx down.
**Current focus:** Phase 05 VERIFIED. Both blockers (CR-01, CR-02) closed; v1.14.0 shippable.

## Current Position

Phase 05 (http3-opt-in-support) — GOAL VERIFIED (7/7 SC).
Initial verification returned gaps_found (5/7). Both blockers fixed and re-verified
on 2026-05-31:
- CR-02 (SC-1) CLOSED: removed `ssl_protocols TLSv1.3;` from the injected QUIC
  block — TCP/443 keeps http-scope `TLSv1.2 TLSv1.3`. Commit b3000b7.
- CR-01 CLOSED: mutual-exclusion guard rejects `--enable_http3` +
  `--disable_domain_listen` with a ClickException. Commit b3000b7 (test fix ffe762f).
Full suite: 244 passed, 2 skipped, coverage gate reached.
v1.12.0 released (GSD milestone output). v1.13.0 released out-of-GSD (PatchMon
template, commit 089b9db, 2026-05-31). v1.14.0 now shippable (operator publishes).
Phase: 05 (http3-opt-in-support) — COMPLETE
Plan: 4 of 4 executed + gap closure verified
Status: Ready for /gsd-complete-milestone, then publish v1.14.0 (local-only)
Last activity: 2026-05-31

Progress: [██████████] 100% (6/6 phases goal-verified)

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
| Phase 05-http3-opt-in-support P02 | 30min | 2 tasks | 2 files |
| Phase 05-http3-opt-in-support P03 | 20min | 2 tasks | 3 files |
| Phase 05-http3-opt-in-support P04 | 10min | 2 tasks | 4 files |

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
- 05-02: _inject_http3_directives inserts 5-directive QUIC block (quic listen, http3 on, quic_retry on, ssl_protocols TLSv1.3, Alt-Svc) after first listen <ip>:443 ssl; via string injection; dual-form reuseport regex (optional IP prefix) matches both IP-bound and wildcard forms; no IPv6 QUIC line (intentional: no included template has listen [::]:443 ssl;); get_nginx_version parses nginx -v stderr; version gate deferred to 05-03
- 05-03: version gate in execute_commands after validate_all_inputs, before content = get_config_template(); gate only fires when enable_http3=True (zero subprocess overhead for existing operators); QUIC catch-all block in default_ssl_reject uses wildcard listen + default_server + reuseport (intentional: catch-all IS the fallback, not an SNI leak; reuseport claimed here so vhosts omit it via _quic_reuseport_already_claimed)
- 05-04: UDP/443 firewall callout rendered as blockquote WARNING in both README and RELEASE_NOTES; --migrate_to_http3 deferred to v2 (PROTO-V2-01); version bumped manually 1.13.0 → 1.14.0 (not via bump-my-version)
- v1.14.0 released: HTTP/3 opt-in support complete — 12 templates, nginx >= 1.25.0 version gate, QUIC SNI catch-all, Alt-Svc header; 244 tests passing
- 05 gap closure: CR-02 fixed by removing server-scope ssl_protocols from QUIC injection (QUIC enforces TLS 1.3 at protocol level; TCP/443 keeps http-scope TLSv1.2 TLSv1.3 — SC-1 satisfied). CR-01 fixed via mutual-exclusion guard (enable_http3 + disable_domain_listen → ClickException). Re-verified 2026-05-31: 7/7 SC.

## Next Action

Phase 05 VERIFIED. All 4 plans executed + both blockers closed. All 6 phases goal-verified.

1. `/gsd-complete-milestone` — archive completed milestone
2. Outstanding operator tasks (release publishing — local-only, never CI):
   - Create git tag `v1.14.0` locally: `git tag v1.14.0`
   - Push branch `2026` + tags `v1.12.0` / `v1.13.0` / `v1.14.0` to origin + upstream
   - `uv build` + `uvpublish` for v1.14.0; confirm PyPI shows nginx-set-conf 1.14.0

---

*State initialized: 2026-05-28*
