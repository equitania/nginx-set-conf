---
phase: "01-privileged-write-surface-hardening"
plan: "02"
subsystem: "config_verification"
tags: ["security", "symlink-hardening", "backup", "tdd"]
dependency_graph:
  requires: []
  provides: ["SEC-02-mitigated"]
  affects: ["nginx_set_conf/config_verification.py", "tests/test_backup.py"]
tech_stack:
  added: []
  patterns: ["injectable-path-params", "islink-guard", "explicit-symlinks=False"]
key_files:
  modified:
    - nginx_set_conf/config_verification.py
  created:
    - tests/test_backup.py
decisions:
  - "Injectable path parameters (nginx_conf_path, nginxconfig_dir) follow the same pattern as setup_default_server (target_path, ssl_dir) — string defaults, Path()-wrapped inside the function body"
  - "islink guard placed inside the existing `if server_nginxconfig_dir.exists():` block — consistent with the surrounding guard structure"
  - "symlinks=False is an explicit keyword argument even though it is shutil.copytree's default, to make the security intent self-documenting"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-28T18:14:55Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 01 Plan 02: SEC-02 backup_configuration Symlink Hardening Summary

**One-liner:** `backup_configuration` hardened against symlink attacks via `is_symlink()` source guard, explicit `symlinks=False` on `copytree`, and injectable path parameters for testability.

## What Was Built

### Task 1 — Implementation (`nginx_set_conf/config_verification.py`)

**Commit:** `324ff73`

Hardened `backup_configuration` in three steps:

1. **Injectable path parameters:** Extended the signature with two keyword parameters:
   - `nginx_conf_path: str = "/etc/nginx/nginx.conf"`
   - `nginxconfig_dir: str = "/etc/nginx/nginxconfig.io"`
   All hard-coded `Path("/etc/nginx/nginx.conf")` and `Path("/etc/nginx/nginxconfig.io")` literals inside the function body replaced with `Path(nginx_conf_path)` and `Path(nginxconfig_dir)`.

2. **islink guard (threat T-01-02-01):** Before the `shutil.copytree` call, added:
   ```python
   if server_nginxconfig_dir.is_symlink():
       logger.error("Refusing to backup symlinked source directory: %s", server_nginxconfig_dir)
       return False
   ```
   Closes the attack vector where `/etc/nginx/nginxconfig.io` is replaced with a symlink to `/root` or `/etc/shadow`.

3. **Explicit `symlinks=False` (threat T-01-02-02):** `shutil.copytree` is now called with `symlinks=False` as an explicit keyword argument. This was already the default, but making it explicit documents the security contract and protects against future Python version changes.

### Task 2 — Tests (`tests/test_backup.py`)

**Commit:** `bfb2b62`

New file with `class TestBackupConfiguration` (3 methods):

| Method | Coverage |
|--------|---------|
| `test_refuses_symlinked_nginxconfig_source` | Returns `False` when `nginxconfig_dir` is a symlink (T-01-02-01) |
| `test_accepts_real_nginxconfig_directory` | Returns `True` and creates backup for real directory (happy path) |
| `test_copytree_does_not_follow_symlinks_in_source` | Contract test: `symlinks=False` dereferences in-tree symlinks (T-01-02-02) |

All tests use `tmp_path` fixture; no test touches `/etc/nginx` or `/var/backups`.

## Verification Results

```
tests/test_backup.py::TestBackupConfiguration::test_refuses_symlinked_nginxconfig_source PASSED
tests/test_backup.py::TestBackupConfiguration::test_accepts_real_nginxconfig_directory PASSED
tests/test_backup.py::TestBackupConfiguration::test_copytree_does_not_follow_symlinks_in_source PASSED

176 passed in 0.31s
Total coverage: 70.81% (gate: 60%)
config_verification.py coverage: 24% (was 0%)
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The changes are purely defensive (narrowing the write/read surface of `backup_configuration`).

## Known Stubs

None.

## Self-Check: PASSED

- `/Users/picard/gitbase/PyPi-Projects/nginx-set-conf/nginx_set_conf/config_verification.py` — FOUND
- `/Users/picard/gitbase/PyPi-Projects/nginx-set-conf/tests/test_backup.py` — FOUND
- Commit `324ff73` — FOUND (`[FIX] sec(NSC-01-02): SEC-02 — islink guard...`)
- Commit `bfb2b62` — FOUND (`[ADD] tests(NSC-01-02): SEC-02 TestBackupConfiguration...`)
- `uv run pytest tests/test_backup.py -v --no-cov` — 3 PASSED
- `uv run pytest tests/ -q` — 176 PASSED, 70.81% coverage
