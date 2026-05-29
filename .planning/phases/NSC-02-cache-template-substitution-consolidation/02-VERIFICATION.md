---
phase: 02-cache-template-substitution-consolidation
verified: 2026-05-29T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 02: Cache + Template Substitution Consolidation Verification Report

**Phase Goal:** One authoritative pass rewrites cache paths from a single sentinel. Redirect templates can no longer leak their literal `target.domain.de` sentinel into nginx log file paths.
**Verified:** 2026-05-29
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `all_templates.py` no longer pre-substitutes `proxy_cache_path`; `utils.py` is the single authoritative substitution site producing identical output | ✓ VERIFIED | `get_config_template()` is a pure dict lookup (confirmed line 122–145); `TEMPLATES` dict stores raw template variables with zero `replace_cache_path()` call sites (grep returns function def at line 35 + comment at line 100 only) |
| 2 | A `redirect`/`redirect_ssl` invocation without `--redirect_domain` fails validation before any file is written | ✓ VERIFIED | `validators.py:356–360` raises `ValidationError("'redirect_domain' is required for template '...'")` immediately after `validate_config_template`; `execute_commands` catches `ValidationError` and returns before any file write; `TestValidateRedirectDomain` — 4/4 PASSED |
| 3 | `CACHE_PATH_SENTINEL` is defined once and imported by every consumer; no magic `/tmp` literal in executed code paths | ✓ VERIFIED | Defined at `all_templates.py:31`; imported by `utils.py:31` as `from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL`; used in `replace_cache_path()` at line 64; used as `_SENTINEL_PATH` at `utils.py:671`. Template `.py` files contain literal `/tmp` strings — this is correct per design (templates are raw nginx config text; Python cannot inject a constant into a string body); `TestRawSentinelStorage::test_sentinel_constant_matches_template_literals` XPASS confirms all template literals match the constant's value |
| 4 | `default_ssl_reject` status in `VALID_TEMPLATES` is explicit or its exclusion is justified inline at `validators.py` (~lines 25–43) | ✓ VERIFIED | 5-line comment block at `validators.py:32–36` explains exclusion rationale: "generated only by `--setup_default` (setup_default_server in utils.py) which writes to 00-default.conf using a sacrificial self-signed cert … See CONCERNS.md §COR-LOW-1"; old single-line comment replaced; two regression guard tests in `TestValidateConfigTemplate` — both PASSED |
| 5 | Cache-path regex uses a `lambda` `repl` instead of an `f"\\1..."` back-reference; output unchanged for existing domains | ✓ VERIFIED | `utils.py:685,691,697` — all three back-reference `re.sub` calls use `lambda m:` form; first `re.sub` (plain replacement, no groups) uses f-string correctly; `TestCachePathSubstitutionOutput` — 4/4 PASSED with golden-output snapshot |
| 6 | Full test suite green; no template output diffs except intentional changes | ✓ VERIFIED | `python -m pytest -q` → `192 passed, 2 xpassed in 0.28s`; coverage 72.42% (above 60% gate); 2 xpassed are pre-refactor xfail markers that now correctly XPASS after COR-01/COR-03 fix |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `nginx_set_conf/templates/all_templates.py` | `CACHE_PATH_SENTINEL` constant; raw `TEMPLATES` dict | ✓ VERIFIED | `CACHE_PATH_SENTINEL = "proxy_cache_path /tmp"` at line 31; `TEMPLATES` dict at line 96 stores raw template variables without `replace_cache_path()` calls |
| `nginx_set_conf/utils.py` | Broadened first `re.sub` + 3x `lambda m:` repl | ✓ VERIFIED | Pattern at line 677 covers both `/tmp` sentinel and `/var/cache/nginx/...`; `lambda m:` at lines 685, 691, 697 |
| `nginx_set_conf/validators.py` | `redirect_domain` required guard + `default_ssl_reject` comment | ✓ VERIFIED | Guard at lines 356–360; comment block at lines 32–36 |
| `tests/test_templates.py` | `TestCachePathSubstitutionOutput` + `TestRawSentinelStorage` | ✓ VERIFIED | Both classes present; 4 PASSED + 2 XPASSED |
| `tests/test_validators.py` | `TestValidateRedirectDomain` + 2 guards in `TestValidateConfigTemplate` | ✓ VERIFIED | All 4 `TestValidateRedirectDomain` methods PASSED; both exclusion guards PASSED |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `all_templates.py` | `utils.py` | `CACHE_PATH_SENTINEL` imported | ✓ WIRED | `utils.py:31`: `from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL` |
| `validators.py` | `utils.py` `execute_commands` | `validate_all_inputs` called before file write | ✓ WIRED | `utils.py:607`: `validate_all_inputs(...)` called at start of `execute_commands`; `ValidationError` caught and returns before any file operation |
| `validators.py` `VALID_TEMPLATES` | `default_ssl_reject` exclusion | Comment + regression tests | ✓ WIRED | Comment at lines 32–36; tests `test_default_ssl_reject_not_in_valid_templates` and `test_default_ssl_reject_not_in_compat_templates` both PASSED |

### Data-Flow Trace (Level 4)

Not applicable — phase produces configuration file output (nginx configs), not dynamic UI rendering. The relevant data flow is: raw template → `execute_commands` → `validate_all_inputs` (guard fires here for redirect without domain) → `replace_cache_path` via `utils.py` regex → file write. All steps verified by unit tests.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| redirect template + empty redirect_domain raises ValidationError | `python -c "from nginx_set_conf.validators import validate_all_inputs, ValidationError; validate_all_inputs('redirect','e.com','1.2.3.4','80',cert_name='e.com',redirect_domain='')"` | `ERROR: 'redirect_domain' is required for template 'redirect'` | ✓ PASS |
| lambda repl in utils.py (3 occurrences) | `grep -c "lambda m:" nginx_set_conf/utils.py` | `3` | ✓ PASS |
| TEMPLATES dict stores raw sentinel | `TestRawSentinelStorage` — XPASS | Both conditions met | ✓ PASS |
| Full test suite | `python -m pytest -q` | `192 passed, 2 xpassed` | ✓ PASS |

### Probe Execution

No phase-declared probes. Conventional probe paths not applicable (not a migration/tooling phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| COR-01 | 02-01 | Single authoritative cache-path substitution pass | ✓ SATISFIED | `get_config_template()` pure dict lookup; `TEMPLATES` stores raw templates; `utils.py` is sole rewrite site |
| COR-02 | 02-02 | `redirect_domain` required for redirect/redirect_ssl templates | ✓ SATISFIED | `validators.py:358–360`; `TestValidateRedirectDomain` 4/4 PASSED |
| COR-03 | 02-01 | Single `CACHE_PATH_SENTINEL` constant; sentinel-drift protection | ✓ SATISFIED | `all_templates.py:31`; imported by `utils.py:31`; `TestRawSentinelStorage` XPASS |
| COR-04 | 02-03 | `default_ssl_reject` absence from `VALID_TEMPLATES` documented inline | ✓ SATISFIED | 5-line comment at `validators.py:32–36`; 2 regression guards PASSED |
| COR-05 | 02-01 | Lambda `repl` for back-reference `re.sub` calls | ✓ SATISFIED | `utils.py:685,691,697` use `lambda m:` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_templates.py` | 371, 388 | `@pytest.mark.xfail` markers (pre-refactor baseline docs) | ℹ️ Info | Both now XPASS — conditions met; markers document the pre-refactor state intentionally. No issue. |

No `TBD`, `FIXME`, or `XXX` markers found in any modified file.

### Human Verification Required

None. All success criteria are verifiable programmatically and the test suite confirms all behaviors.

### Gaps Summary

No gaps. All 6 success criteria are met in the codebase with direct evidence. The test suite passes at 192 + 2 xpassed with 72.42% coverage (above the 60% gate). All five requirement IDs (COR-01 through COR-05) are satisfied.

---

**Note on SC-3 / COR-03 implementation detail:** Individual template `.py` files contain raw `/tmp` string literals rather than importing `CACHE_PATH_SENTINEL`. This is the correct and intended design — template files are pure nginx config text modules that cannot import Python constants into string bodies. The RESEARCH document (§COR-03) explicitly states: "The template files themselves contain only raw nginx config text — they do not import Python. The constant cannot be injected into template string content directly." Sentinel-drift protection is enforced by `TestRawSentinelStorage::test_sentinel_constant_matches_template_literals` (XPASS), which verifies all template literals match `CACHE_PATH_SENTINEL.split()[1]`.

---

_Verified: 2026-05-29_
_Verifier: Claude (gsd-verifier)_
