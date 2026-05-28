---
phase: "01-privileged-write-surface-hardening"
plan: "03"
subsystem: "utils.setup_default_server"
tags: ["security", "umask", "private-key", "race-condition", "SEC-03"]
dependency_graph:
  requires: []
  provides:
    - "_restrictive_umask context manager in utils.py"
    - "umask-wrapped openssl call in setup_default_server"
    - "test_key_file_created_with_mode_600 regression guard"
  affects:
    - "nginx_set_conf/utils.py"
    - "tests/test_migration.py"
tech_stack:
  added: ["contextlib (stdlib — new import)"]
  patterns: ["umask context manager", "os.open for umask-honoring file creation in tests"]
key_files:
  modified:
    - "nginx_set_conf/utils.py"
    - "tests/test_migration.py"
decisions:
  - "Use _restrictive_umask context manager (umask 0o077) to eliminate key file race window"
  - "Remove post-hoc chmod 600 entirely — communicates wrong intent after umask fix"
  - "Test uses os.open(mode=0o666) not Path.touch(mode=...) to correctly honor active umask"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-28"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  commits: 2
---

# Phase 01 Plan 03: SEC-03 — umask(0o077) private key race fix Summary

**One-liner:** Eliminated world-readable race window on private key by wrapping openssl invocation in `_restrictive_umask(os.umask(0o077))` context manager and removing the now-redundant post-hoc `chmod 600` subprocess call.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add `_restrictive_umask`, wrap openssl call, remove post-hoc chmod | `6e6d006` | `nginx_set_conf/utils.py` |
| 2 | Extend `TestSetupDefaultServer` with `test_key_file_created_with_mode_600` | `09d165d` | `tests/test_migration.py` |

## What Was Built

### `_restrictive_umask` context manager (`nginx_set_conf/utils.py`)

A new module-level private function placed before `_run_command`:

```python
@contextlib.contextmanager
def _restrictive_umask():
    """Context manager: set umask 0o077, restore on exit."""
    old_umask = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old_umask)
```

The context manager is intentionally narrow — it wraps only the `_run_command(["openssl", ...])` call inside `setup_default_server`, not the entire `if not cert_exists` block.

### `setup_default_server` openssl block (before / after)

**Before:**
```python
ok = _run_command(["openssl", "req", ...])
if not ok:
    logger.error("Failed to generate self-signed default cert")
    return False
_run_command(["chmod", "600", key_path])  # race window + misleading intent
```

**After:**
```python
with _restrictive_umask():
    ok = _run_command(["openssl", "req", ...])
if not ok:
    logger.error("Failed to generate self-signed default cert")
    return False
# post-hoc chmod removed — key is born at 0o600
```

### `test_key_file_created_with_mode_600` (`tests/test_migration.py`)

Regression guard in `TestSetupDefaultServer`. The fake `_run_command` uses `os.open(str(key_path), os.O_CREAT | os.O_WRONLY, 0o666)` to correctly exercise umask semantics (unlike `Path.touch(mode=...)` which calls `os.chmod` directly and bypasses umask). Asserts `key_path.stat().st_mode & 0o777 == 0o600`.

## Verification Results

```
uv run pytest tests/ -q
177 passed in 0.36s
Total coverage: 71.10% (gate: 60%)

uv run pytest tests/test_migration.py::TestSetupDefaultServer -v --no-cov
5 passed in 0.06s (all including test_key_file_created_with_mode_600)
```

Acceptance checks:
- `grep '_run_command(["chmod", "600"' utils.py` → no matches
- `grep 'umask\|_restrictive_umask' utils.py` → lines 180-186, 511

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- [x] `nginx_set_conf/utils.py` modified — `_restrictive_umask` present, `os.umask(0o077)` present, `contextlib` imported
- [x] Post-hoc `_run_command(["chmod", "600", key_path])` line removed
- [x] `tests/test_migration.py` contains `test_key_file_created_with_mode_600` and `os.O_CREAT`
- [x] Commits `6e6d006` and `09d165d` confirmed in git log
- [x] Full suite: 177 passed, coverage 71%
- [x] No edits outside `setup_default_server` region (~lines 490-530)
- [x] No edits to `STATE.md` or `ROADMAP.md`
