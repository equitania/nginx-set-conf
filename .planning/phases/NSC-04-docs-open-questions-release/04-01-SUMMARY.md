---
phase: 04-docs-open-questions-release
plan: 01
subsystem: docs-verification-cli
tags: [documentation, safety-gate, sync-config, force-flag, release-notes]
dependency_graph:
  requires: []
  provides:
    - CLAUDE.md corrected Important Files section
    - README.md manual IP-bound migration procedure
    - RELEASE_NOTES.md v1.12.0 Q-01 and Q-02 decision entries
    - sync_configurations force parameter (safety gate)
    - --force Click option wired to sync_configurations
    - tests/test_sync_config.py 5 green tests
  affects:
    - nginx_set_conf/config_verification.py (sync_configurations signature)
    - nginx_set_conf/nginx_set_conf.py (CLI surface)
tech_stack:
  added: []
  patterns:
    - force flag gate pattern (warn-and-abort without --force, proceed-with-notice with --force)
    - monkeypatch + unittest.mock.patch for _perform_sync spy
key_files:
  created:
    - tests/test_sync_config.py
  modified:
    - CLAUDE.md
    - README.md
    - RELEASE_NOTES.md
    - nginx_set_conf/config_verification.py
    - nginx_set_conf/nginx_set_conf.py
decisions:
  - DOC-01: CLAUDE.md Important Files split into __init__.py (version only) and all_templates.py (replace_cache_path + CACHE_PATH_SENTINEL)
  - Q-01: --migrate_to_ip_bound not implemented; manual procedure documented in README; teaser removed from RELEASE_NOTES v1.11.0
  - Q-02: --force gate implemented on sync_configurations; interactive prompt removed; warn-and-abort without --force, proceed-with-notice with --force
metrics:
  duration: ~18 min
  completed: 2026-05-29
  tasks_completed: 3
  files_modified: 5
  files_created: 1
---

# Phase 04 Plan 01: Docs, Open Questions, Release — Implementation Summary

**One-liner**: Corrected CLAUDE.md doc drift, removed migrate_to_ip_bound teaser, added manual migration guide, and implemented --force safety gate on --sync_config to prevent silent operator data loss.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DOC-01 + Q-01 — Fix CLAUDE.md, remove teaser, document manual migration, add RELEASE_NOTES entries | bc932a3 | CLAUDE.md, README.md, RELEASE_NOTES.md |
| 2 | Q-02 — Implement --force gate on sync_configurations + wire Click option | ad0050e | config_verification.py, nginx_set_conf.py |
| 3 | Q-02 — Tests for --force gate (warn-and-abort, proceed paths) | 6aeb9cc | tests/test_sync_config.py |

## What Was Built

### Task 1: Documentation (DOC-01 + Q-01)

**CLAUDE.md**:
- Split the single `__init__.py` "Important Files" bullet into two entries: `__init__.py` (version only) and `all_templates.py` (replace_cache_path + CACHE_PATH_SENTINEL)
- Updated the "Version 1.4.5 Changes" bullet to name `all_templates.py` explicitly

**RELEASE_NOTES.md**:
- Removed the "A future minor release may add an atomic --migrate_to_ip_bound companion" teaser from v1.11.0 Migration section
- Added `### Q-01: --migrate_to_ip_bound not implemented` subsection in v1.12.0 with full decision rationale (MIG-01 deferred to v2, v1.10.0 risk class)
- Added `### Q-02: --sync_config now requires --force to overwrite server files` subsection with before/after behaviour description

**README.md**:
- Added `## Manual Migration: Hostname-bound to IP-bound Listen` section with step-by-step procedure: grep for hostname-bound configs, regenerate per-vhost with --ip, nginx -t, reload

### Task 2: --force Gate Implementation (Q-02)

**config_verification.py** `sync_configurations` signature change:
```python
# Before
def sync_configurations(self, results: dict[str, dict]) -> bool

# After
def sync_configurations(self, results: dict[str, dict], force: bool = False) -> bool
```

Behaviour:
- Without `force=True` and with `files_to_update` non-empty: emits yellow WARNING about permanent overwrite, echoes "Aborting. Pass --force to proceed.", returns `False` immediately — `_perform_sync` is never called
- With `force=True`: emits the same warning as a NOTICE, then calls `backup_configuration()` and `_perform_sync()` — no interactive prompt
- All-consistent / nothing-to-update path: returns `False` (unchanged from previous behaviour)
- Interactive `click.prompt` / `click.confirm` gate removed entirely

**nginx_set_conf.py**:
- Added `--force` Click `is_flag=True` option adjacent to `--sync_config`
- Added `force` to `start_nginx_set_conf` function signature
- Updated call site: `verifier.sync_configurations(results, force=force)`

### Task 3: Tests (Q-02)

Created `tests/test_sync_config.py` with class `TestSyncConfigForceGate`:

| Test | Assertion |
|------|-----------|
| `test_sync_without_force_aborts_when_files_differ` | Returns False; `_perform_sync` not called |
| `test_sync_without_force_succeeds_when_nothing_to_update` | Returns False (nothing to sync — real behaviour confirmed) |
| `test_sync_with_force_calls_perform_sync` | `_perform_sync` called once |
| `test_sync_with_force_emits_warning` | Output contains "customis" or "overwrite" |
| `test_sync_without_force_emits_abort_message` | Output contains "force" or "aborting" |

Full suite: **209 passed, 2 skipped, 2 xpassed**, coverage 76% (gate: 60%).

## Verification Results

```
1. grep "all_templates.py" CLAUDE.md | grep -i replace_cache  → 2 matching lines (Important Files + Version 1.4.5 Changes)
2. grep -c "future minor release.*migrate_to_ip_bound" RELEASE_NOTES.md → 0 (teaser gone)
3. grep "Q-01\|Q-02" RELEASE_NOTES.md → 2 section headings in v1.12.0 block
4. grep "Manual Migration" README.md → section heading found
5. python force-in-params check → True
6. grep "--force" nginx_set_conf.py → Click option line 233
7. pytest tests/test_sync_config.py -v → 5 PASSED
8. pytest tests/ → 209 passed, coverage 76%
```

## Deviations from Plan

### Auto-fixed Issues

None.

### Plan-checker Warning Addressed

The plan-checker flagged `test_sync_without_force_succeeds_when_nothing_to_update` — it noted that assuming `False` return might be wrong. Before writing the test, the actual code was read (lines 336-338 of config_verification.py):

```python
if not files_to_update and not missing_files:
    click.echo("All configuration files are already up to date. Nothing to sync.")
    return False
```

The real return value is `False`. The test asserts `False` — matching actual behaviour, not a blind assumption.

### accept_criteria Note on migrate_to_ip_bound count

The plan stated "grep -c 'migrate_to_ip_bound' returns 1". After the changes, it returns 2 (both occurrences are in the new Q-01 subsection of v1.12.0 — the section heading and the decision sentence). The old teaser ("A future minor release may add...") is confirmed gone via `grep -c "future minor release.*migrate_to_ip_bound" → 0`. This is the correct outcome; the plan's count-check was an approximation.

## Known Stubs

None — all documented behaviour is implemented and tested.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. The --force gate reduces the threat surface by preventing accidental data loss (T-04-01 mitigated as planned).

## Self-Check: PASSED

- tests/test_sync_config.py: EXISTS
- CLAUDE.md corrected: VERIFIED (grep confirms)
- RELEASE_NOTES.md teaser removed: VERIFIED (count = 0)
- README.md Manual Migration section: VERIFIED
- sync_configurations force param: VERIFIED (import check)
- Commits bc932a3, ad0050e, 6aeb9cc: all present in git log
