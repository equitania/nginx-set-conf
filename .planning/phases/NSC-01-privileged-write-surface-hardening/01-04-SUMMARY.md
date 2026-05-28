---
phase: "01-privileged-write-surface-hardening"
plan: "04"
subsystem: "input-validation"
tags: [security, hardening, dos-prevention, iterative-refactor, testing]
dependency_graph:
  requires: []
  provides: [iterative-retrieve-valid-input, input-length-cap, eof-handling]
  affects: [nginx_set_conf/utils.py, tests/test_utils.py]
tech_stack:
  added: []
  patterns: [iterative-loop-over-recursion, eofhandle-systemexit]
key_files:
  created: []
  modified:
    - nginx_set_conf/utils.py
    - tests/test_utils.py
decisions:
  - "Silent truncation ([:4096]) preferred over rejection — downstream validators emit clear error messages"
  - "click.echo used for EOF message to stay consistent with existing user-facing output in utils.py"
  - "click imported at module level (was missing from utils.py imports)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 01 Plan 04: SEC-04 — Iterative retrieve_valid_input Summary

**One-liner:** Converted recursive `retrieve_valid_input` to iterative `while True` loop with 4096-char input cap and clean `EOFError` → `SystemExit(1)` handler.

## What Was Built

**Task 1 — `nginx_set_conf/utils.py` (commit `9b974a7`)**

Added module-level constant `_MAX_INPUT_LENGTH = 4096` and rewrote `retrieve_valid_input` from a tail-recursive function into an iterative `while True:` loop. Each iteration wraps `input()` in a `try/except EOFError` block; on EOF, `click.echo` prints a message and `SystemExit(1)` is raised. Input is silently truncated to `_MAX_INPUT_LENGTH` characters before the non-empty check. The function signature `(message: str) -> str` is unchanged — no callers required updating.

Also added `import click` which was missing from `utils.py` but required by the new `click.echo` call in the `EOFError` handler.

**Task 2 — `tests/test_utils.py` (commit `c834fc4`)**

Appended class `TestRetrieveValidInput` with five regression tests covering all threat scenarios from the plan's STRIDE register:

| Test | Threat | Outcome |
|------|--------|---------|
| `test_returns_nonempty_input_immediately` | baseline | correct value returned |
| `test_loops_past_empty_input` | loop behavior | skips 2 empty → returns "finally" |
| `test_truncates_oversized_input` | T-01-04-02 (100KB stdin) | 8000-char input capped to 4096 |
| `test_eof_raises_system_exit` | T-01-04-03 (piped stdin EOF) | `SystemExit` raised cleanly |
| `test_no_recursion_on_many_empty_enters` | T-01-04-01 (unbounded recursion) | 1001 iterations, no `RecursionError` |

## Acceptance Checks

All three checks passed before SUMMARY was written:

```
grep -n 'def retrieve_valid_input' utils.py        → line 168 (exactly 1 match)
python3 AST self-call check                        → exit 0 (no recursive call)
grep -n '_MAX_INPUT_LENGTH\s*=\s*4096' utils.py    → line 165
```

## Test Results

```
uv run pytest tests/test_utils.py::TestRetrieveValidInput -v --no-cov
5 passed in 0.06s

uv run pytest tests/ -q
182 passed — 72% coverage (gate: 60%) — 0 failures
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical dependency] Added `import click` to utils.py**
- **Found during:** Task 1 verification
- **Issue:** The plan stated "Do NOT add the import for click — it is already present" but `grep -n "import click" nginx_set_conf/utils.py` returned no output — `click` was NOT imported in `utils.py`.
- **Fix:** Added `import click` to the stdlib/third-party imports block.
- **Files modified:** `nginx_set_conf/utils.py`
- **Commit:** `9b974a7` (included in Task 1 commit)

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Changes are limited to the interactive input loop inside `retrieve_valid_input`. No threat flags.

## Known Stubs

None.

## Self-Check: PASSED

- `nginx_set_conf/utils.py` — modified (confirmed, `_MAX_INPUT_LENGTH` on line 165)
- `tests/test_utils.py` — modified (confirmed, `TestRetrieveValidInput` appended)
- Commit `9b974a7` — exists (`git log --oneline` verified)
- Commit `c834fc4` — exists (`git log --oneline` verified)
- Full test suite: 182 passed, 0 failed
