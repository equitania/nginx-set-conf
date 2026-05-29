---
phase: "02-cache-template-substitution-consolidation"
plan: "03"
subsystem: "validators"
tags: [documentation, regression-guard, tdd, COR-04]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [COR-04-documentation, default_ssl_reject-exclusion-locked]
  affects: [nginx_set_conf/validators.py, tests/test_validators.py]
tech_stack:
  added: []
  patterns: [inline comment rationale above whitelist, regression-guard tests in existing class]
key_files:
  created: []
  modified:
    - nginx_set_conf/validators.py
    - tests/test_validators.py
decisions:
  - "Replaced single-line 'Valid template names (whitelist)' comment with 5-line block explaining default_ssl_reject exclusion rationale — points to CONCERNS.md §COR-LOW-1"
  - "Two regression guard tests appended inside existing TestValidateConfigTemplate class (not a new class) — consistent with test file structure"
  - "No code behaviour changed — comment and tests only"
metrics:
  duration: "~4 min"
  completed: "2026-05-29"
  tasks: 2
  files: 2
---

# Phase 02 Plan 03: default_ssl_reject Exclusion Documentation (COR-04) Summary

**One-liner:** Inline comment above VALID_TEMPLATES documents default_ssl_reject exclusion rationale; two regression guard tests lock the decision in place.

## What Was Built

Closed documentation gap COR-LOW-1: the absence of `default_ssl_reject` from `VALID_TEMPLATES` was correct but unexplained. Future operators or contributors had no inline signal that the omission was intentional.

### Changes

**`nginx_set_conf/validators.py`:**
- Replaced single-line `# Valid template names (whitelist)` comment with a 5-line block
- New block explains: `default_ssl_reject` is generated only by `--setup_default` (via `setup_default_server` in utils.py), writes to `00-default.conf` with a sacrificial self-signed cert, and must never be routable via `--config_template` to avoid overwriting the SNI catch-all
- References `CONCERNS.md §COR-LOW-1` for full threat traceability
- No code change — comment only

**`tests/test_validators.py`:**
- Appended two methods to existing `TestValidateConfigTemplate` class:
  - `test_default_ssl_reject_not_in_valid_templates` — asserts `"default_ssl_reject" not in VALID_TEMPLATES`
  - `test_default_ssl_reject_not_in_compat_templates` — asserts `"ngx_default_ssl_reject" not in VALID_TEMPLATES_COMPAT`
- Both methods include descriptive assertion messages referencing `CONCERNS.md §COR-LOW-1`

## Verification Results

```
uv run pytest tests/test_validators.py::TestValidateConfigTemplate -v --no-cov
7 passed in 0.04s  (includes both new guards)

uv run pytest tests/ -q
192 passed, 2 xpassed in 0.36s  (coverage 72.42% — above 60% gate)
```

## Structural Assertions

```
grep -n "default_ssl_reject" nginx_set_conf/validators.py
→ line 34: comment only (starts with #) — not in set body

grep -c "VALID_TEMPLATES: template names" nginx_set_conf/validators.py
→ 1

grep -c "Valid template names" nginx_set_conf/validators.py
→ 0 (old single-line comment replaced)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Surface Scan

T-02-03-01 (Tampering: phantom whitelist addition): Mitigated — regression tests assert exclusion; inline comment provides clear signal to future reviewers.
T-02-03-02 (Elevation of Privilege: operator uses --config_template default_ssl_reject to overwrite SNI catch-all): Accepted — runtime protection already present in prior phase; this plan adds documentation and regression tests only.
T-02-03-SC: No new dependencies added.

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

Files exist:
- nginx_set_conf/validators.py: FOUND
- tests/test_validators.py: FOUND

Commits exist:
- b892424 [CHG] docs(NSC-02-03): COR-04 — document default_ssl_reject exclusion from VALID_TEMPLATES
- 181ec87 [ADD] tests(NSC-02-03): COR-04 regression guard — default_ssl_reject excluded from VALID_TEMPLATES
