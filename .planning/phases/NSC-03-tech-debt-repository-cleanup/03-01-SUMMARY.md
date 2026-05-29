---
phase: 03-tech-debt-repository-cleanup
plan: "01"
subsystem: nginx_set_conf
tags: [tech-debt, import-cleanup, dead-code-removal, tdd]
dependency_graph:
  requires: []
  provides: [config-templates-removed, import-surface-direct]
  affects: [nginx_set_conf/nginx_set_conf.py, nginx_set_conf/utils.py, nginx_set_conf/__init__.py]
tech_stack:
  added: []
  patterns: [TDD RED/GREEN, git-rm for tracked deletion]
key_files:
  created:
    - tests/test_config_templates_removed.py
  modified:
    - nginx_set_conf/__init__.py
    - nginx_set_conf/nginx_set_conf.py
    - nginx_set_conf/utils.py
    - tests/test_templates.py
    - RELEASE_NOTES.md
  deleted:
    - nginx_set_conf/config_templates.py
decisions:
  - "D-01: config_templates.py hard-deleted via git rm — no deprecation period kept"
  - "D-02: All imports repointed directly to nginx_set_conf.templates.all_templates"
  - "D-03: ngx_ backward-compat prefix test removed — shim that provided it is gone"
  - "D-04: v1.12.0 RELEASE_NOTES section documents migration path"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-29"
  tasks_completed: 2
  files_modified: 6
---

# Phase 03 Plan 01: Delete config_templates.py Shim Summary

**One-liner:** Hard-deleted config_templates.py shim with direct all_templates import repoint across nginx_set_conf.py, utils.py, and __init__.py; 196 tests green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED  | Failing test for ModuleNotFoundError | d451a67 | tests/test_config_templates_removed.py (new), baseline files |
| 1    | Delete config_templates.py and repair all imports | 9adb887 | nginx_set_conf/config_templates.py (deleted), __init__.py, nginx_set_conf.py, utils.py, tests/test_templates.py |
| 2    | Add RELEASE_NOTES.md migration note | 3576358 | RELEASE_NOTES.md |

## What Was Built

The deprecated `nginx_set_conf/config_templates.py` shim has been permanently removed.
This module existed only as a backward-compat wrapper around `nginx_set_conf.templates.all_templates`,
and contained eager module-level evaluation of `config_template_dict` that fired `print()` side-effects
on every template fetch. All three import sites were updated to resolve directly through `all_templates`:

- `nginx_set_conf/nginx_set_conf.py` line 26: `from .config_templates import get_config_template` → `from .templates.all_templates import get_config_template`
- `nginx_set_conf/utils.py`: combined separate imports into `from .templates.all_templates import get_config_template, CACHE_PATH_SENTINEL`
- `nginx_set_conf/__init__.py`: removed `from . import config_templates as config_templates` and its `__all__` entry

A new test file `tests/test_config_templates_removed.py` documents the intended post-removal state and serves as a regression guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] utils.py also imported from config_templates**
- **Found during:** Task 1, GREEN phase — import verification
- **Issue:** `nginx_set_conf/utils.py` line 30 contained `from .config_templates import get_config_template` and line 31 had a separate `from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL`. The plan only mentioned `nginx_set_conf.py` line 26 as the import to fix.
- **Fix:** Combined both imports into `from .templates.all_templates import get_config_template, CACHE_PATH_SENTINEL`
- **Files modified:** `nginx_set_conf/utils.py`
- **Commit:** 9adb887

## TDD Gate Compliance

The TDD cycle was followed:
1. **RED (d451a67):** `tests/test_config_templates_removed.py` written with 4 tests — `test_config_templates_module_not_importable` FAILED as expected (module still existed at commit time)
2. **GREEN (9adb887):** Implementation completed — all 4 new tests PASS, plus all 196 existing tests pass
3. **REFACTOR:** Not required — changes were clean and minimal

Additionally, `tests/test_templates.py` was updated:
- Import line 7 `from nginx_set_conf.config_templates import get_config_template` → `from nginx_set_conf.templates.all_templates import get_config_template`
- Removed redundant alias import (lines 13-15)
- `test_backward_compat_ngx_prefix` → `test_canonical_name_resolves` (the ngx_ prefix was a shim feature, now gone)

## Threat Flags

None. The import-surface change is purely internal. The sentinel-leak and log-path guards from Phase 2 (in utils.py redirect_domain validator) are untouched.

## Known Stubs

None.

## Self-Check

- [x] `nginx_set_conf/config_templates.py` does not exist on disk: CONFIRMED
- [x] `git ls-files nginx_set_conf/config_templates.py` returns empty: CONFIRMED
- [x] `nginx_set_conf/nginx_set_conf.py` line 26 contains direct all_templates import: CONFIRMED
- [x] `nginx_set_conf/__init__.py` has no "config_templates" reference: CONFIRMED
- [x] `tests/test_templates.py` has no import from nginx_set_conf.config_templates: CONFIRMED (only a comment with the phrase)
- [x] `pytest` exits 0 with 196 passed, 2 xpassed: CONFIRMED
- [x] `RELEASE_NOTES.md` has `## Version 1.12.0` before `## Version 1.11.1`: CONFIRMED
- [x] Commits d451a67, 9adb887, 3576358 exist: CONFIRMED

## Self-Check: PASSED
