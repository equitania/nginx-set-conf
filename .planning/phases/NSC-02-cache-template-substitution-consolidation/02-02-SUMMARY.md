---
phase: "02-cache-template-substitution-consolidation"
plan: "02"
subsystem: "validators"
tags: [security, validation, tdd, bug-fix]
dependency_graph:
  requires: [02-01]
  provides: [COR-02-guard, redirect-domain-required-check]
  affects: [nginx_set_conf/validators.py, tests/test_validators.py]
tech_stack:
  added: []
  patterns: [required-presence guard in validate_all_inputs, sentinel-leak prevention]
key_files:
  created: []
  modified:
    - nginx_set_conf/validators.py
    - tests/test_validators.py
decisions:
  - "Required-presence guard inserted immediately after validate_config_template in validate_all_inputs — ensures invalid template name fails first (not redirect_domain check)"
  - "validate_redirect_domain() left unchanged — it validates format only; presence check lives exclusively in validate_all_inputs"
  - "Substring match 'redirect' in config_template covers both 'redirect' and 'redirect_ssl' — consistent with existing pattern in utils.py:773"
metrics:
  duration: "~8 min"
  completed: "2026-05-29"
  tasks: 2
  files: 2
---

# Phase 02 Plan 02: redirect_domain Required Guard (COR-02) Summary

**One-liner:** Sentinel-leak guard in validate_all_inputs prevents "target.domain.de" from reaching nginx log paths when redirect_domain is omitted for redirect templates.

## What Was Built

Added a required-presence check for `redirect_domain` in `validate_all_inputs()` (validators.py). Previously, omitting `redirect_domain` for redirect or redirect_ssl templates was silently accepted — the literal nginx-template sentinel `target.domain.de` propagated through to the nginx config, writing to `/var/log/nginx/target.domain.de-access.log`. The guard closes this correctness bug (COR-MED-2) before any filesystem side-effect can occur.

### Changes

**`nginx_set_conf/validators.py`:**
- Added 6-line block (comment + condition + raise) inside `validate_all_inputs()`, immediately after the `validate_config_template(config_template)` call
- Block uses `"redirect" in config_template and not redirect_domain.strip()` — same substring pattern already used in utils.py:773
- Raises `ValidationError("'redirect_domain' is required for template '{config_template}'")`
- `validate_redirect_domain()` function body is untouched — format-only validation

**`tests/test_validators.py`:**
- Appended `TestValidateRedirectDomain` class after `TestValidateAllInputs`
- 4 test methods covering all cases from COR-02 test approach:
  - `test_redirect_without_domain_raises` — redirect template, empty redirect_domain
  - `test_redirect_ssl_without_domain_raises` — redirect_ssl template, empty redirect_domain
  - `test_redirect_with_valid_domain_passes` — redirect template, valid redirect_domain (happy path)
  - `test_non_redirect_does_not_require_domain` — odoo_ssl template, empty redirect_domain (unaffected)

## Verification Results

```
uv run pytest tests/test_validators.py::TestValidateRedirectDomain -v --no-cov
4 passed in 0.04s

uv run pytest tests/ -q
190 passed, 2 xpassed in 0.31s  (coverage 72.42% — above 60% gate)
```

## Structural Assertions

```
grep -n "redirect_domain.*required" nginx_set_conf/validators.py
→ 1 match inside validate_all_inputs

grep "TestValidateRedirectDomain" tests/test_validators.py
→ class definition found
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Surface Scan

T-02-02-01 (Information Disclosure: redirect_domain sentinel leak): Mitigated — ValidationError raised before execute_commands writes any file.
T-02-02-02 (Tampering: log injection via crafted redirect_domain): Mitigated — validate_redirect_domain still validates format as RFC 1123 domain; new guard adds required-presence check on top.
T-02-02-SC: No new dependencies added.

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

Files exist:
- nginx_set_conf/validators.py: FOUND
- tests/test_validators.py: FOUND

Commits exist:
- ecc50c8 [FIX] cor(NSC-02-02): COR-02 — require redirect_domain for redirect templates
- 500ff85 [ADD] tests(NSC-02-02): COR-02 redirect_domain required regression tests
