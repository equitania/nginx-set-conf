---
phase: 05-http3-opt-in-support
plan: "02"
subsystem: http3-injection
tags: [http3, quic, nginx, utils, tdd, directive-injection, reuseport]

dependency_graph:
  requires:
    - phase: 05-01
      provides: [enable_http3-flag, HTTP3_EXCLUDED_TEMPLATES, validate_all_inputs-guard, TODO(05-02)-marker]
  provides:
    - _inject_http3_directives helper (utils.py)
    - _quic_reuseport_already_claimed helper (utils.py)
    - get_nginx_version helper (utils.py)
    - execute_commands injection call-site (TODO replaced)
  affects: [05-03-default_ssl_reject-catch-all, 05-04-release]

tech-stack:
  added: []
  patterns:
    - "_insert_after_marker reuse for in-memory config injection at substitution time"
    - "dual-form reuseport regex: optional IP prefix matches both IP-bound and wildcard forms"
    - "conf_dir scan at deploy time for reuseport claim detection"

key-files:
  created: []
  modified:
    - nginx_set_conf/utils.py
    - tests/test_templates.py

key-decisions:
  - "No IPv6 QUIC line injected: none of the 12 included templates carry listen [::]:443 ssl; (only default_ssl_reject does, and it is excluded from --enable_http3)"
  - "reuseport detection uses dual-form regex matching both IP-bound and wildcard forms (critical for 05-03 cross-plan coupling)"
  - "_inject_http3_directives placed AFTER disable_domain_listen block in execute_commands to honor replace-order invariant"
  - "effective_conf_dir uses target_path when set, falls back to /etc/nginx/conf.d"
  - "test_inject_first_only_leaves_second_block counts full listen line string, not word 'quic' (quic_retry also contains 'quic')"

patterns-established:
  - "IP-bound QUIC listen invariant: every vhost QUIC line uses formatted_listen_ip, never raw placeholder"
  - "first_only=True for qdrant gRPC block preservation"

requirements-completed: [PROTO-03, PROTO-04]

duration: 30min
completed: 2026-05-31
---

# Phase 05 Plan 02: HTTP/3 Directive Injection Helpers Summary

**_inject_http3_directives inserts 5-directive QUIC block after listen <ip>:443 ssl; via string injection, with dual-form reuseport detection (IP-bound + wildcard) and first_only=True for qdrant gRPC block preservation.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-31T11:15:00Z
- **Completed:** 2026-05-31T11:45:00Z
- **Tasks:** 2 (both TDD: RED + GREEN cycle)
- **Files modified:** 2

## Accomplishments

- Three new private helpers added to utils.py: `get_nginx_version`, `_quic_reuseport_already_claimed`, `_inject_http3_directives`
- TODO(05-02) marker in execute_commands replaced with actual injection call-site
- Dual-form reuseport regex matches both `listen 1.2.3.4:443 quic reuseport;` (IP-bound) and `listen 443 quic default_server reuseport;` (wildcard) — critical for 05-03 cross-plan coupling
- 15 new tests in test_templates.py: TestHttp3DirectiveInjection (11) + TestNginxVersionParsing (4)
- Full suite: 233 passed, 2 skipped, 2 xpassed; coverage 76.60%

## Task Commits

1. **TDD RED** - `9baf1dc` (test: add failing tests for _inject_http3_directives and get_nginx_version)
2. **TDD GREEN** - `73238bc` (feat: add three helpers + injection call-site in execute_commands)
3. **Test fix** - `f734e96` (test: fix test_inject_first_only assertion — count quic listen lines not word quic)

## Files Created/Modified

- `nginx_set_conf/utils.py` — Three new helpers + injection call-site replacing TODO(05-02)
- `tests/test_templates.py` — TestHttp3DirectiveInjection (11 tests) + TestNginxVersionParsing (4 tests)

## Decisions Made

- **No IPv6 QUIC line:** `_inject_http3_directives` does NOT inject `listen [::]:443 quic;`. Rationale: none of the 12 HTTP/3-included templates carry `listen [::]:443 ssl;` (only `default_ssl_reject` does, and that template is excluded from `--enable_http3`). Intentional omission, documented in docstring.
- **Dual-form reuseport regex:** `rf"listen\s+(?:{re.escape(ip)}:)?{port}\s+quic\b.*\breuseport"` — the `(?:...)?` group makes the IP prefix optional. This matches both the IP-bound form a vhost emits AND the wildcard form that 05-03's `default_ssl_reject` QUIC catch-all will emit. Without this, every vhost would double-claim reuseport on UDP/443, causing nginx reload failure.
- **effective_conf_dir:** When `target_path` is set (non-default deployment), use it as the scan directory. Falls back to `/etc/nginx/conf.d`. This lets tests with tmp_path work without needing an nginx install.
- **test assertion fix:** `result.count("quic") == 1` was wrong because `quic_retry on;` also contains "quic". Fixed to `result.count("listen 1.2.3.4:443 quic") == 1` which precisely measures the QUIC listen line count.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_inject_first_only_leaves_second_block assertion**
- **Found during:** TDD GREEN verification
- **Issue:** `result.count("quic") == 1` asserted count of all "quic" substrings, but `quic_retry on;` also contains "quic", making the count == 2 even with correct first_only behavior
- **Fix:** Changed to `result.count("listen 1.2.3.4:443 quic") == 1` which counts only the QUIC listen line
- **Files modified:** tests/test_templates.py
- **Verification:** Test passes, first_only behavior correctly verified
- **Committed in:** f734e96

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in test assertion)
**Impact on plan:** Necessary fix. The behavior being tested (first_only=True) was already correct; the test assertion was imprecise.

## Issues Encountered

None beyond the test assertion fix above.

## Known Stubs

None. The injection helpers are fully functional. Version gate (nginx >= 1.25.0 check) is intentionally deferred to 05-03 per plan design.

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns introduced beyond the conf_dir scan already in the plan's threat model (T-05-02-01: read-only scan with OSError/PermissionError caught).

## Next Phase Readiness

- 05-03 (default_ssl_reject QUIC catch-all + version gate) can build directly on these helpers
- `_quic_reuseport_already_claimed` already handles the wildcard form that 05-03 will emit
- `get_nginx_version()` is ready for 05-03's version gate call-site
- TestHttp3DefaultCatchAll (referenced in PATTERNS.md) is not in this plan — it belongs in 05-03

## Self-Check: PASSED

- nginx_set_conf/utils.py: FOUND (_inject_http3_directives defined 3 occurrences, get_nginx_version 1, _quic_reuseport_already_claimed 3)
- tests/test_templates.py: FOUND (TestHttp3DirectiveInjection with 11 tests, TestNginxVersionParsing with 4 tests)
- Commits 9baf1dc, 73238bc, f734e96: VERIFIED in git log
- Full suite: 233 passed

---
*Phase: 05-http3-opt-in-support*
*Completed: 2026-05-31*
