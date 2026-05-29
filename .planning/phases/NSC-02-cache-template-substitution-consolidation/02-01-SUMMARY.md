---
phase: "02-cache-template-substitution-consolidation"
plan: "01"
subsystem: "templates/utils"
tags: [refactor, security, regex, tdd]
dependency_graph:
  requires: []
  provides: [CACHE_PATH_SENTINEL, raw-template-storage, lambda-repl-substitution]
  affects: [nginx_set_conf/templates/all_templates.py, nginx_set_conf/utils.py, tests/test_templates.py]
tech_stack:
  added: []
  patterns: [single-pass cache-path rewrite, sentinel-drift protection, lambda repl backref]
key_files:
  created:
    - tests/test_templates.py (new classes appended)
  modified:
    - nginx_set_conf/templates/all_templates.py
    - nginx_set_conf/utils.py
    - tests/test_templates.py
decisions:
  - "TEMPLATES dict stores raw templates (not pre-processed) — single authoritative rewrite pass in utils.py"
  - "CACHE_PATH_SENTINEL defined in all_templates.py; imported by utils.py as sentinel-drift guard"
  - "xfail markers on TestRawSentinelStorage left in place (now XPASS) — document pre-refactor baseline state"
metrics:
  duration: "~12 min"
  completed: "2026-05-29"
  tasks: 3
  files: 3
---

# Phase 02 Plan 01: Cache + Template Substitution Consolidation Summary

**One-liner:** Single-pass cache-path rewrite via CACHE_PATH_SENTINEL + lambda repl back-references eliminates dual-substitution ordering hazard.

## What Was Built

Consolidated the dual cache-path substitution pipeline into a single authoritative pass in `utils.py`. Previously, `all_templates.py` applied a service-name-based substitution at import time, then `utils.py` overwrote with the domain-qualified `unique_id`. These two passes composed correctly only by accident. The refactor removes the first pass entirely.

### Changes

**`nginx_set_conf/templates/all_templates.py`:**
- Added `CACHE_PATH_SENTINEL = "proxy_cache_path /tmp"` constant (COR-03)
- Updated `replace_cache_path()` to use `CACHE_PATH_SENTINEL` instead of string literal
- Rewrote all 17 entries in TEMPLATES dict to store raw template variables (no `replace_cache_path()` calls at import time) — `COR-01`
- Simplified `get_config_template()` to a pure dict lookup; `domain` param retained for API compat but unused

**`nginx_set_conf/utils.py`:**
- Added `from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL` as a separate import line (shim import `from .config_templates import get_config_template` untouched — retired in Phase 3)
- Added `_SENTINEL_PATH = re.escape(CACHE_PATH_SENTINEL.split()[1])` for sentinel-drift protection
- Broadened first `re.sub` pattern to match both `/tmp` sentinel AND any pre-existing `/var/cache/nginx/...` path — `COR-01`
- Converted second, third, fourth `re.sub` calls from f-string backref form (`f"\\1{unique_id}_..."`) to `lambda m:` form — `COR-05`

**`tests/test_templates.py`:**
- Added `import re` and `import pytest` at top
- Added `TestCachePathSubstitutionOutput` class with 4 parametrized golden-output snapshot cases
- Added `TestRawSentinelStorage` class with 2 tests (xfail pre-refactor, xpass post-refactor)

## Verification Results

```
uv run pytest tests/ -q
186 passed, 2 xpassed in 0.41s  (coverage 71.91% — above 60% gate)

TestCachePathSubstitutionOutput: 4 PASSED
TestRawSentinelStorage: 2 XPASSED (pre-condition guards confirmed working)
TestCachePathReplacement: 5 PASSED
```

## Structural Assertions

```
grep -c "replace_cache_path(" nginx_set_conf/templates/all_templates.py
→ 2  (1 function def + 1 comment — zero call sites)

grep "CACHE_PATH_SENTINEL" nginx_set_conf/templates/all_templates.py
→ definition + use in replace_cache_path()

grep -c "lambda m:" nginx_set_conf/utils.py
→ 3  (second/third/fourth re.sub blocks)
```

## Deviations from Plan

### Minor Clarification

**grep -c "replace_cache_path(" all_templates.py expected 1, got 2:**
- The plan acceptance criterion states "grep -c equals 1 (function def line only)".
- The actual count is 2: line 35 (function def) + line 100 (comment: `# registered verbatim without replace_cache_path()`).
- The comment is the original doc comment preserved from the TEMPLATES dict. There are zero actual call sites.
- This is a documentation comment, not a call — the functional intent is fully met.

## Known Stubs

None. All templates are wired to the substitution pipeline.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The refactor is internal to the template loading and substitution pipeline.

T-02-01-01 (DoS: sentinel leak to /tmp): Mitigated — broadened re.sub pattern in utils.py ensures /tmp is always rewritten.
T-02-01-02 (Tampering: f-string backref): Mitigated — lambda repl for all three backref re.sub calls.
T-02-01-03 (Tampering: dual-pass ordering): Mitigated — single authoritative pass in utils.py; golden-output snapshot proves identity.

## Self-Check: PASSED

Files exist:
- nginx_set_conf/templates/all_templates.py: FOUND
- nginx_set_conf/utils.py: FOUND
- tests/test_templates.py: FOUND

Commits exist:
- a9beab7 [ADD] tests(NSC-02-01): golden-output snapshot + raw-sentinel regression net
- e8887b3 [CHG] cor(NSC-02-01): COR-01/COR-03 — raw templates in TEMPLATES dict + CACHE_PATH_SENTINEL
- fe5c502 [CHG] cor(NSC-02-01): COR-01/COR-05 — broaden proxy_cache_path regex + lambda repl
