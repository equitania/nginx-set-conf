---
phase: 05-http3-opt-in-support
plan: "03"
subsystem: http3-security
tags: [http3, quic, nginx, utils, tdd, version-gate, default-catch-all, security]

dependency_graph:
  requires:
    - phase: 05-01
      provides: [enable_http3-flag, validate_all_inputs-guard]
    - phase: 05-02
      provides: [get_nginx_version, _quic_reuseport_already_claimed, _inject_http3_directives]
  provides:
    - nginx version gate in execute_commands (T-05-03-01 mitigated)
    - QUIC default_server catch-all block in default_ssl_reject.py (T-05-03-02 mitigated)
  affects: [05-04-release]

tech-stack:
  added: []
  patterns:
    - "click.ClickException for hard pre-file-write stops in execute_commands"
    - "get_nginx_version() called only when enable_http3=True (zero overhead for existing operators)"
    - "QUIC wildcard + default_server + reuseport is correct for catch-all; vhost QUIC stays IP-bound"

key-files:
  created: []
  modified:
    - nginx_set_conf/utils.py
    - nginx_set_conf/templates/default_ssl_reject.py
    - tests/test_templates.py

key-decisions:
  - "Version gate placed after validate_all_inputs, before content = get_config_template() — guarantees zero file writes on version failure"
  - "Gate skipped entirely when enable_http3=False — no subprocess.run overhead for existing operators"
  - "QUIC catch-all block uses wildcard listen (no IP prefix) — intentional, this IS the default_server; not an SNI leak"
  - "reuseport on QUIC catch-all block means _quic_reuseport_already_claimed detects it; vhost configs correctly omit reuseport"
  - "default_ssl_reject date header updated from 21.04.2026 to 31.05.2026 per version-header convention"

requirements-completed: [PROTO-05, PROTO-03]

duration: 20min
completed: 2026-05-31
---

# Phase 05 Plan 03: nginx Version Gate and QUIC Catch-All Summary

**nginx version gate in execute_commands raises ClickException before any file write when nginx < 1.25.0; default_ssl_reject gains a QUIC default_server catch-all block returning 444 for unknown SNI on UDP/443.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-31T12:00:00Z
- **Completed:** 2026-05-31T12:20:00Z
- **Tasks:** 2 (both TDD: RED + GREEN cycles)
- **Files modified:** 3

## Accomplishments

- nginx version gate inserted in `execute_commands` after `validate_all_inputs`, before `content = get_config_template()` — zero file writes on version failure (T-05-03-01 mitigated)
- Gate only fires when `enable_http3=True`; when False, `get_nginx_version()` is never called (no overhead for existing operators)
- Error message includes detected version string and upgrade paths (Debian bookworm-backports, Ubuntu 24.04+, RHEL 9.4+)
- `default_ssl_reject.py` extended with third server block: `listen 443 quic default_server reuseport` + IPv6 form — mirrors TCP 443 catch-all (T-05-03-02 mitigated)
- QUIC catch-all uses wildcard listen (no IP prefix) with `default_server` + `reuseport` — intentional; this IS the fallback, not an SNI leak
- `_quic_reuseport_already_claimed` (05-02) detects the reuseport claim on this block; subsequent HTTP/3 vhost configs correctly omit reuseport (T-05-03-03 mitigated)
- 9 new tests: `TestNginxVersionGate` (4) + `TestHttp3DefaultCatchAll` (5)
- Full suite: 242 passed, 2 skipped, 2 xpassed; coverage 77.43%

## Task Commits

1. **TDD RED Task 1** - `3eabaac` (test: add failing TestNginxVersionGate tests (TDD RED))
2. **TDD GREEN Task 1** - `058d547` (feat: add nginx version gate in execute_commands (TDD GREEN))
3. **TDD RED Task 2** - `d4bfeea` (test: add failing TestHttp3DefaultCatchAll tests (TDD RED))
4. **TDD GREEN Task 2** - `ec3c3a4` (feat: extend default_ssl_reject with QUIC catch-all server block (TDD GREEN))

## Files Created/Modified

- `nginx_set_conf/utils.py` — nginx version gate block inserted after `validate_all_inputs`, before `get_config_template()` call
- `nginx_set_conf/templates/default_ssl_reject.py` — QUIC catch-all server block appended; date header updated to 31.05.2026
- `tests/test_templates.py` — `TestNginxVersionGate` (4 tests) + `TestHttp3DefaultCatchAll` (5 tests); added `click` and `execute_commands` to imports

## Decisions Made

- **Version gate placement:** After `validate_all_inputs`, before `content = get_config_template()`. This ensures that if `ClickException` is raised, no cache directory has been created and no file has been touched. The `nginx -t` gate (v1.11.1 pre-reload) is a second line of defense but the version gate is the first and cheapest.
- **Gate skip when http3 disabled:** `if enable_http3:` guard ensures zero overhead (no subprocess.run) for existing operators who don't use HTTP/3. Verified by `test_gate_not_called_when_http3_disabled`.
- **Wildcard QUIC catch-all in default_ssl_reject:** Intentional deviation from the IP-bound invariant that applies to vhosts. The catch-all IS `default_server`; wildcard + `default_server` + `reuseport` is correct and safe here. An inline comment documents the rationale.
- **reuseport on catch-all block:** The catch-all claims the UDP/443 socket via `reuseport`. The `_quic_reuseport_already_claimed` scanner (05-02) detects this when deploying vhost configs and suppresses `reuseport` from them — preventing nginx reload failure.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The version gate and QUIC catch-all block are fully functional.

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns beyond those in the plan's threat model.

## TDD Gate Compliance

### Task 1 (nginx version gate)
- RED gate: commit `3eabaac` — `test(05-03): add failing TestNginxVersionGate tests (TDD RED)`
- GREEN gate: commit `058d547` — `feat(05-03): add nginx version gate in execute_commands (TDD GREEN)`

### Task 2 (QUIC catch-all)
- RED gate: commit `d4bfeea` — `test(05-03): add failing TestHttp3DefaultCatchAll tests (TDD RED)`
- GREEN gate: commit `ec3c3a4` — `feat(05-03): extend default_ssl_reject with QUIC catch-all server block (TDD GREEN)`

## Self-Check: PASSED

- nginx_set_conf/utils.py: FOUND (`grep -c "HTTP/3 requires nginx"` = 1, `grep -c "get_nginx_version"` = 2)
- nginx_set_conf/templates/default_ssl_reject.py: FOUND (3 server blocks, "listen 443 quic default_server" present, "return 444;" count = 3)
- tests/test_templates.py: FOUND (TestNginxVersionGate + TestHttp3DefaultCatchAll, 9 tests)
- Commits 3eabaac, 058d547, d4bfeea, ec3c3a4: VERIFIED in git log
- Full suite: 242 passed

---
*Phase: 05-http3-opt-in-support*
*Completed: 2026-05-31*
