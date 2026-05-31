---
phase: 05-http3-opt-in-support
verified: 2026-05-31T14:00:00Z
status: verified
score: 7/7 must-haves verified
reverified: 2026-05-31T14:00:00Z
initial_status: gaps_found
overrides_applied: 0
gaps:
  - truth: "The non-HTTP/3 server block (TCP/443 with HTTP/2) remains unchanged so HTTP/1.1 + HTTP/2 fallback still work (ROADMAP SC-1)"
    status: failed
    reason: "_inject_http3_directives injects ssl_protocols TLSv1.3; INSIDE the single shared server block (no separate QUIC-only block exists). This server-scope directive overrides the http-scope ssl_protocols TLSv1.2 TLSv1.3; setting, dropping TLSv1.2 support for TCP/443 on every --enable_http3 vhost. Confirmed by code inspection (utils.py:430-436) and live execution: the injected output places ssl_protocols TLSv1.3; alongside listen <ip>:443 ssl; in the same server {} block."
    artifacts:
      - path: "nginx_set_conf/utils.py"
        issue: "Line 434: ssl_protocols TLSv1.3; is in insert_lines alongside the QUIC listen line — all lines are injected inside the existing TCP/443 server block, not in a dedicated QUIC-only block. The ROADMAP SC-1 contract requires the TCP/443 block to be unchanged."
    missing:
      - "Either remove ssl_protocols TLSv1.3; from insert_lines (nginx enforces TLSv1.3-only for QUIC at the protocol level without this directive), OR create a separate QUIC-only server block so the TCP/443 block is genuinely unchanged. The code-review fix is: remove the line (CR-02 recommendation)."
  - truth: "--enable_http3 combined with --disable_domain_listen produces correct output OR raises an error (safe behavior for flag combination)"
    status: failed
    reason: "CR-01: disable_domain_listen (utils.py:873-880) rewrites listen {ip}:443 to listen 443 BEFORE the HTTP/3 injection step (utils.py:887-889). _inject_http3_directives searches for marker 'listen {ip}:443 ssl;' which no longer exists — it logs only a WARNING and returns content unchanged. The written config has no HTTP/3 directives. No ClickException is raised. nginx -t passes silently because the config is valid without QUIC. Confirmed by code inspection and by running _inject_http3_directives on wildcard-form content (returns content unchanged, 0 quic/http3 directives)."
    artifacts:
      - path: "nginx_set_conf/utils.py"
        issue: "Lines 873-880 (disable_domain_listen) destroy the injection marker; lines 887-889 (HTTP/3 injection) then silently no-op. No mutual-exclusion guard exists."
    missing:
      - "Add mutual-exclusion guard in execute_commands after validate_all_inputs: if enable_http3 and disable_domain_listen: raise click.ClickException(...). This is the CR-01 fix from the code review. Alternatively extend _inject_http3_directives to fall back to 'listen 443 ssl;' marker when the IP-bound form is absent, but the mutual-exclusion guard is simpler and safer."
---

# Phase 05: HTTP/3 Opt-In Support — Verification Report

**Phase Goal:** A new `--enable_http3` flag adds QUIC + HTTP/3 to 12 SSL templates that serve browser/end-user traffic. The remaining templates (gRPC, server-to-server API, redirects, dev tools, catch-alls) stay HTTP/2-only. Default is off so existing operators see no change.
**Verified:** 2026-05-31T12:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | `--enable_http3` on odoo_ssl produces QUIC directives AND the TCP/443 server block (HTTP/2) remains unchanged | FAILED (BLOCKER — CR-02) | `ssl_protocols TLSv1.3;` is injected inside the **single** shared server block at utils.py:434, overriding http-scope TLS settings. No separate QUIC block is created. TLSv1.2 clients on TCP/443 are refused. |
| SC-2 | Exclusion list enforced: `--enable_http3` on fast_report, mailpit, redirect, redirect_ssl, default_ssl_reject, odoo_http raises clear error | VERIFIED | `HTTP3_EXCLUDED_TEMPLATES` frozenset at validators.py:72-79; guard at line 386; 9 tests in TestHttp3Exclusion all pass |
| SC-3 | Pre-write nginx version check refuses quic directives on nginx < 1.25.0 | VERIFIED | Version gate at utils.py:767-778; raises click.ClickException with remediation message; 4 TestNginxVersionGate tests pass |
| SC-4 | README has HTTP/3/QUIC section with 5 prerequisites including prominent UDP/443 callout | VERIFIED | Section present in README.md; `grep -c "HTTP/3 / QUIC" README.md` = 1; UDP/443 appears 2 times; WARNING blockquote present |
| SC-5 | `--migrate_to_http3` NOT implemented; manual procedure documented | VERIFIED | `grep -c "migrate_to_http3" README.md` = 1; documents manual regeneration procedure |
| SC-6 | QUIC `default_server` catch-all present in `default_ssl_reject` template (v1.10.0 lesson applied) | VERIFIED | default_ssl_reject.py contains 3-block TEMPLATE: port 80, TCP 443, QUIC 443 catch-all with wildcard listen + reuseport; 5 TestHttp3DefaultCatchAll tests pass |
| SC-7 | Full test suite green; HTTP/3-emitting output is deterministic | VERIFIED | `uv run pytest tests/ --no-cov` exits 0 (242 passed, 2 skipped, 2 xpassed); coverage gate 77% > 60% with full run |

**Score:** 5/7 truths verified (SC-1 FAILED, gap from CR-01 also blocks safe operation)

---

### Additional CR-01 Gap (Not a ROADMAP SC but blocks correct behavior)

The ROADMAP does not explicitly state "disable_domain_listen + enable_http3 must be safe", but this combination silently produces a broken config (HTTP/3 flag is acknowledged, version gate passes, file is written, but no QUIC directives appear). This is a correctness blocker independent of the SC-1 failure.

---

### Code Review Findings vs. Goal Achievement

#### CR-01: `--disable_domain_listen` + `--enable_http3` silently drops all HTTP/3 directives — CONFIRMED BLOCKER

**Code evidence (utils.py):**
- Line 873-880: `disable_domain_listen` rewrites `listen {formatted_listen_ip}:443` → `listen 443` (all listen lines with the IP prefix stripped)
- Line 887-889: `_inject_http3_directives(content, formatted_listen_ip, ...)` searches for marker `f"listen {formatted_listen_ip}:443 ssl;"` — which no longer exists after the above rewrite
- Line 440-445: When marker not found, logs WARNING and returns `content` unchanged
- No ClickException raised; file is written with no QUIC directives; `nginx -t` passes silently

**Live verification:**
```
content = 'server {\n    listen 443 ssl;\n    http2 on;\n    server_name erp.example.com;\n}'
result = _inject_http3_directives(content, '1.2.3.4')
# result == content (unchanged), 'quic' not in result
```

**Impact on phase goal:** The phase goal states "default is off so existing operators see no change." An operator using `--disable_domain_listen` (a prior feature) alongside the new `--enable_http3` gets silently degraded behavior with no diagnostic. This contradicts the fail-fast contract implied by the version gate and exclusion guard patterns.

---

#### CR-02: Injected `ssl_protocols TLSv1.3;` is in the shared server block, not a QUIC-only block — CONFIRMED BLOCKER (SC-1)

**Code evidence (utils.py:389-447, _inject_http3_directives):**
- The function inserts lines **after** `listen {ip}:443 ssl;` within the existing `server {}` block
- insert_lines (lines 430-436) contains `ssl_protocols TLSv1.3;` alongside QUIC listen, http3 on, quic_retry on, Alt-Svc
- There is no code that creates a **new** server block for QUIC — all 5 directives land in the same server block as the TCP/443 listen

**Live verification output** (actual injection on synthetic content):
```
server {
    listen 1.2.3.4:443 ssl;
    listen 1.2.3.4:443 quic reuseport;   ← QUIC listen
    http3 on;
    quic_retry on;
    ssl_protocols TLSv1.3;               ← SERVER-SCOPE, affects TCP/443 too
    add_header Alt-Svc ...;
    http2 on;
    server_name erp.example.com;
    ...
}
```

**nginx directive inheritance rule:** A `server`-scope `ssl_protocols` overrides the `http`-scope setting entirely. After `--enable_http3`, every affected vhost refuses TLSv1.2 on TCP/443 as well as QUIC/UDP/443.

**ROADMAP SC-1 wording:** "The non-HTTP/3 server block (TCP/443 with HTTP/2) remains unchanged so HTTP/1.1 + HTTP/2 fallback still work."

**Finding:** SC-1 is FAILED. There is no separate HTTP/3 server block — both TCP/443 and QUIC/443 share one `server {}` block. `ssl_protocols TLSv1.3;` modifies the TCP/443 path in violation of the SC.

**Note on PROTO-04 wording:** REQUIREMENTS.md PROTO-04 says `ssl_protocols TLSv1.3;` "scoped to the HTTP/3 server block." The implementation does NOT create a separate HTTP/3 server block — the directive is in the shared block. This is the architectural gap that caused CR-02.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `nginx_set_conf/nginx_set_conf.py` | `--enable_http3` Click flag + YAML read-through | VERIFIED | Flag at line 211; param at line 296; yaml_enable_http3 at line 399; both call sites wired |
| `nginx_set_conf/validators.py` | `HTTP3_EXCLUDED_TEMPLATES` frozenset + guard | VERIFIED | frozenset at line 72, 6 members; guard at line 386 |
| `nginx_set_conf/utils.py` | `_inject_http3_directives`, `_quic_reuseport_already_claimed`, `get_nginx_version`, version gate, injection call-site | VERIFIED (with CR-01 and CR-02 caveats) | All helpers present and wired; version gate at line 767; injection call-site at line 887-889 |
| `nginx_set_conf/templates/default_ssl_reject.py` | 3-block TEMPLATE with QUIC catch-all | VERIFIED | 3 `server {` blocks confirmed; QUIC block uses wildcard + default_server + reuseport |
| `README.md` | HTTP/3 / QUIC section with 5 prerequisites | VERIFIED | Section present; UDP/443 callout as blockquote; all 5 prerequisites present |
| `RELEASE_NOTES.md` | v1.14.0 entry as first section | VERIFIED | Entry present; appears before v1.13.0 |
| `nginx_set_conf/__init__.py` | `__version__ = "1.14.0"` | VERIFIED | Confirmed at line 8 |
| `pyproject.toml` | `version = "1.14.0"` | VERIFIED | Confirmed at line 7 |
| `tests/test_validators.py` | `TestHttp3Exclusion` class with 9 tests | VERIFIED | 9 tests collected and passing |
| `tests/test_templates.py` | `TestHttp3DirectiveInjection`, `TestNginxVersionParsing`, `TestHttp3DefaultCatchAll`, `TestNginxVersionGate` | VERIFIED | All classes present; 24 HTTP3/NginxVersion tests pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `nginx_set_conf.py` | `validators.py` | `validate_all_inputs(enable_http3=...)` | VERIFIED | Line 760 passes enable_http3 keyword arg |
| `nginx_set_conf.py` | `utils.py execute_commands` | `enable_http3=yaml_enable_http3` / `enable_http3=enable_http3` | VERIFIED | Lines 426 and 451 |
| `execute_commands` | `_inject_http3_directives` | `if enable_http3: content = _inject_http3_directives(...)` | VERIFIED (with CR-01 caveat) | Line 887-889; wired but silently fails when disable_domain_listen is also active |
| `execute_commands` | `get_nginx_version` | version gate at lines 767-778 | VERIFIED | Gate is before any content substitution |
| `_inject_http3_directives` | `_quic_reuseport_already_claimed` | `if conf_dir is not None and _quic_reuseport_already_claimed(...)` | VERIFIED | Line 425 |
| `default_ssl_reject.py QUIC block` | `_quic_reuseport_already_claimed` | Wildcard reuseport claim detected at deploy time | VERIFIED | Regex matches both IP-bound and IPv4 wildcard forms (WR-02 partial: IPv6 form not matched but IPv4 wildcard is sufficient for current default_ssl_reject) |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `_inject_http3_directives` | `content` (already-substituted nginx config) | `get_config_template` + IP/domain substitution in `execute_commands` | Yes — real template content with real IP/domain | FLOWING |
| `_quic_reuseport_already_claimed` | conf file contents | `os.listdir(conf_dir)` + `open(fpath)` | Yes — reads actual nginx conf.d files | FLOWING |
| `get_nginx_version` | `result.stderr` | `subprocess.run(["nginx", "-v"])` | Yes — real nginx binary output | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| QUIC inject on normal SSL content | `_inject_http3_directives('    listen 1.2.3.4:443 ssl;\n', '1.2.3.4')` | 5 directives present, IP-bound | PASS |
| QUIC inject after disable_domain_listen | `_inject_http3_directives('    listen 443 ssl;\n', '1.2.3.4')` | content unchanged, no quic/http3 | FAIL (CR-01) |
| ssl_protocols scope | Live injection output | ssl_protocols TLSv1.3; inside shared server block, not QUIC-only block | FAIL (CR-02) |
| Version gate blocks old nginx | `get_nginx_version` mocked to (1,24,0) | ClickException raised with "1.24.0" | PASS |
| Exclusion validator | `validate_all_inputs(config_template="fast_report", enable_http3=True)` | ValidationError raised | PASS |
| default_ssl_reject 3 blocks | `TEMPLATE.count('server {')` | 3 | PASS |
| Version strings | `__version__` and pyproject.toml | both "1.14.0" | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files found in this project. CLI tool requires a live nginx server for end-to-end probes; those are out of scope for automated verification.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|-------------|-------------|--------|----------|
| PROTO-02 | 05-01 | `--enable_http3` flag recognized, YAML read-through, execute_commands wired | SATISFIED | Flag at nginx_set_conf.py:211; YAML at line 399; execute_commands param at line 719 |
| PROTO-03 | 05-01, 05-02, 05-03 | HTTP/3 only on 12 browser-facing templates; exclusion enforced; QUIC catch-all in default_ssl_reject | SATISFIED | HTTP3_EXCLUDED_TEMPLATES with 6 members; TestHttp3Exclusion 9 tests pass; QUIC block in default_ssl_reject verified |
| PROTO-04 | 05-02 | quic listen, Alt-Svc, ssl_protocols TLSv1.3, quic_retry emitted | PARTIALLY SATISFIED — BLOCKER | Directives are emitted (verified), BUT `ssl_protocols TLSv1.3;` is not scoped to an HTTP/3-only block as specified ("scoped to the HTTP/3 server block") — it affects TCP/443 as well. PROTO-04 text says "scoped to the HTTP/3 server block" which requires a separate block; none exists. |
| PROTO-05 | 05-03 | nginx version gate >= 1.25.0 before any file write | SATISFIED | Gate at utils.py:767-778; confirmed before any content substitution |
| PROTO-06 | 05-04 | README + RELEASE_NOTES with 5 prerequisites and UDP/443 callout | SATISFIED | README section verified; RELEASE_NOTES v1.14.0 entry verified |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `nginx_set_conf/utils.py` | 442-445 | `logger.warning(...)` when injection marker not found — no ClickException raised | BLOCKER (CR-01) | Operator enabling `--enable_http3` with `--disable_domain_listen` gets no error; HTTP/3 silently absent |
| `nginx_set_conf/utils.py` | 434 | `ssl_protocols TLSv1.3;` injected inside shared server block | BLOCKER (CR-02) | Drops TLSv1.2 on TCP/443 for all --enable_http3 vhosts; breaks TLSv1.2 clients |
| `nginx_set_conf/validators.py` | 377, 386 | `validate_config_template()` return value discarded; HTTP3 guard uses raw `config_template` | WARNING (WR-01) | `ngx_fast_report` with enable_http3=True bypasses exclusion guard (gets a different error later, but wrong one) |
| `nginx_set_conf/utils.py` | 373-374 | `_quic_reuseport_already_claimed` regex doesn't match `[::]:443 quic` IPv6 wildcard | WARNING (WR-02) | Low risk currently (IPv4 wildcard form matches), but hypothetical future risk if only IPv6 form present |
| `tests/test_templates.py` | ~432-455 | `test_http3_false_leaves_output_unchanged` tests raw template strings, not execute_commands output | INFO (IN-01) | Test name is misleading; the stated invariant is not exercised |

---

### Human Verification Required

None — all findings are deterministic code-level issues verifiable programmatically.

---

## Re-Verification (2026-05-31T14:00:00Z)

**Status: verified — 7/7 SC. Both blockers closed.**

| Blocker | Fix | Commit | Test evidence |
|---------|-----|--------|---------------|
| CR-02 (SC-1) | Removed `ssl_protocols TLSv1.3;` from `insert_lines` in `_inject_http3_directives` (utils.py). QUIC negotiates TLS 1.3 at the protocol level; the shared TCP/443 block keeps its http-scope `ssl_protocols TLSv1.2 TLSv1.3;`, so TLSv1.2 fallback survives. | `b3000b7` | `test_inject_omits_server_scope_tls13` asserts `"ssl_protocols TLSv1.3;" not in result` |
| CR-01 | Added mutual-exclusion guard in `execute_commands` after `validate_all_inputs`: `if enable_http3 and disable_domain_listen: raise click.ClickException(...)`. Fail-fast instead of silently emitting a config with zero HTTP/3 directives. | `b3000b7`, test signature corrected in `ffe762f` | `TestHttp3DisableDomainListenMutex` (2 tests): raises ClickException + no `.conf` written on rejection |

Docs reconciled: README §HTTP/3 prerequisite and RELEASE_NOTES directive list no longer claim a server-scope `ssl_protocols` is injected. `.gitignore` extended for rotated logs (`nginx_set_conf.log.*`).

**Full suite after fixes:** `uv run pytest` → 244 passed, 2 skipped, coverage gate (60%) reached. PROTO-04 now SATISFIED (the "scoped to the HTTP/3 server block" wording is met by *not* emitting a TCP-affecting directive; QUIC's own TLS-1.3 enforcement covers the intent).

---

## Gaps Summary (historical — initial verification)

Two blockers prevent full goal achievement:

**BLOCKER 1 (CR-02 / SC-1):** The ROADMAP Success Criterion 1 states "The non-HTTP/3 server block (TCP/443 with HTTP/2) remains unchanged." The implementation injects all HTTP/3 directives — including `ssl_protocols TLSv1.3;` — into the **existing** TCP/443 server block. No separate QUIC-only server block is created. Since `ssl_protocols` at server scope fully overrides the http-scope setting, every `--enable_http3` vhost silently drops TLSv1.2 support on TCP/443. This also violates PROTO-04 ("scoped to the HTTP/3 server block"). Fix: remove `ssl_protocols TLSv1.3;` from `insert_lines` in `_inject_http3_directives` (nginx enforces TLS 1.3 for QUIC at the protocol level; the directive is redundant for QUIC and harmful for TCP/443).

**BLOCKER 2 (CR-01):** The `--disable_domain_listen` pass runs before the HTTP/3 injection pass and rewrites `listen {ip}:443` to `listen 443`, destroying the injection marker. When both flags are combined, `_inject_http3_directives` logs a WARNING and returns content unchanged. The file is written with no QUIC directives, no error is raised, and `nginx -t` passes. Fix: add a mutual-exclusion guard `if enable_http3 and disable_domain_listen: raise click.ClickException(...)` in `execute_commands` immediately after `validate_all_inputs`.

These two issues share a root cause in plan 05-02: the injection architecture (single shared block vs. separate QUIC block) was never challenged, and the disable_domain_listen interaction was not tested.

**What is working correctly:** Flag plumbing (05-01) is solid. The exclusion validator (PROTO-03) is correct and tested. The version gate (PROTO-05) is correct and placed before any file write. The QUIC catch-all in default_ssl_reject (SC-6) is correct. Documentation and version bump (05-04) are complete and accurate.

---

_Verified: 2026-05-31T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
