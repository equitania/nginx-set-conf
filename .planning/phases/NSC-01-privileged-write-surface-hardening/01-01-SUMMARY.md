---
phase: "01-privileged-write-surface-hardening"
plan: "01"
subsystem: "validators"
tags: ["security", "path-traversal", "input-validation", "SEC-01"]
dependency_graph:
  requires: []
  provides: ["SEC-01-closed"]
  affects: ["nginx_set_conf/validators.py", "tests/test_validators.py"]
tech_stack:
  added: []
  patterns: ["strip-before-check", "segment-split traversal detection", "_reject_path_traversal delegation"]
key_files:
  created: []
  modified:
    - "nginx_set_conf/validators.py"
    - "tests/test_validators.py"
decisions:
  - "Strip all Unicode whitespace (str.strip covers NBSP U+00A0, tab, space) before traversal check — Python built-in, no extra dependency"
  - "Delegate to existing _reject_path_traversal() helper (segment-split) instead of raw '.. in' substring — consistent with validate_cert_name/cert_key/auth_file pattern"
  - "Call os.path.realpath AFTER strip + traversal check to prevent masking (Pitfall 1 from RESEARCH.md)"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
  commits: 2
---

# Phase 01 Plan 01: SEC-01 — validate_target_path Hardening Summary

**One-liner:** Strip-before-check + segment-split traversal guard in validate_target_path, aligned with the _reject_path_traversal pattern used by all sibling validators.

## What Was Done

SEC-01 closed a consistency gap in `validate_target_path`: the only validator in the module that used a raw `".." in value` substring test instead of the established `_reject_path_traversal()` segment-split helper. Additionally, `os.path.realpath()` was called _before_ the traversal check, which opens a masking window where symlinks or relative path resolution collapses traversal sequences before they can be detected.

### Task 1 — Harden validate_target_path (commit `9c38ebc`)

Two-line edit to `nginx_set_conf/validators.py`, function `validate_target_path`:

1. Added `target_path = target_path.strip()` immediately after the empty-string early-return guard
2. Replaced `if ".." in target_path: raise ValidationError(...)` with `_reject_path_traversal(target_path, "target_path")`
3. `os.path.realpath()` now runs after both strip and segment-split check

Resulting call order: empty-guard → strip → `_reject_path_traversal` → `realpath` → abs-check → return.

### Task 2 — Regression Tests (commit `dc1e583`)

Four new methods appended to `TestValidateTargetPath` in `tests/test_validators.py`:

| Method | Input | Expected |
|--------|-------|----------|
| `test_leading_whitespace_path_traversal` | `"  ../etc"` | ValidationError "Path traversal" |
| `test_tab_prefix_traversal` | `"\t../etc"` | ValidationError "Path traversal" |
| `test_nbsp_traversal` | `"\xa0../etc"` | ValidationError "Path traversal" |
| `test_leading_whitespace_absolute_accepted` | `"  /tmp/nginx_test"` | returns path ending with `/tmp/nginx_test` |

## Verification

```
uv run pytest tests/test_validators.py::TestValidateTargetPath -v --no-cov
# 8 passed (4 existing + 4 new)

uv run pytest tests/ -q
# 173 passed, coverage 67.78% (gate: 60%)
```

## Commits

| Hash | Message |
|------|---------|
| `9c38ebc` | `[FIX] sec(NSC-01-01): SEC-01 — strip whitespace + segment-split in validate_target_path` |
| `dc1e583` | `[ADD] tests(NSC-01-01): SEC-01 whitespace-variant regression tests for validate_target_path` |

## Deviations from Plan

None — plan executed exactly as written. Both tasks required only the specified 2-line implementation change and 4 new test methods.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The change is purely defensive: tightening an existing input validator. No new threat surface.

## Self-Check: PASSED

- [x] `nginx_set_conf/validators.py` contains `target_path.strip()` (line 172)
- [x] `nginx_set_conf/validators.py` contains `_reject_path_traversal(target_path` (line 173)
- [x] `nginx_set_conf/validators.py` does NOT contain `".." in target_path`
- [x] `tests/test_validators.py` contains all four new test method names
- [x] Both commits exist on branch `2026`
- [x] Full suite: 173 passed, 0 failed
- [x] STATE.md and ROADMAP.md: not touched
- [x] No files outside `validators.py` and `test_validators.py` modified
