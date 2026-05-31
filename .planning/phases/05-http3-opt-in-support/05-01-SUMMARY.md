---
phase: 05-http3-opt-in-support
plan: "01"
subsystem: cli-plumbing + validators
tags: [http3, quic, click, validators, tdd]
dependency_graph:
  requires: []
  provides: [enable_http3-flag, HTTP3_EXCLUDED_TEMPLATES, validate_all_inputs-guard]
  affects: [nginx_set_conf.py, utils.py, validators.py, test_validators.py]
tech_stack:
  added: []
  patterns: [is_flag Click option, frozenset constant, validate_all_inputs guard]
key_files:
  created: []
  modified:
    - nginx_set_conf/nginx_set_conf.py
    - nginx_set_conf/utils.py
    - nginx_set_conf/validators.py
    - tests/test_validators.py
decisions:
  - "--enable_http3 added as is_flag after --disable_domain_listen in decorator chain"
  - "enable_http3=False added as last param in execute_commands for backward compat"
  - "HTTP3_EXCLUDED_TEMPLATES is frozenset adjacent to VALID_TEMPLATES with per-template rationale"
  - "default_ssl_reject exclusion test passes via validate_config_template rejecting it (not in VALID_TEMPLATES) before HTTP3 guard — ValidationError still raised as required"
  - "Interactive path forwards enable_http3 via retrieve_valid_input yes/no prompt"
  - "TODO(05-02) comment placed at HTTP/3 injection point in execute_commands"
metrics:
  duration: "~15 min"
  completed: "2026-05-31"
  tasks_completed: 2
  files_modified: 4
---

# Phase 05 Plan 01: --enable_http3 plumbing + HTTP3_EXCLUDED_TEMPLATES Summary

**One-liner:** --enable_http3 Click flag wired from CLI → YAML read-through → execute_commands → validate_all_inputs with HTTP3_EXCLUDED_TEMPLATES frozenset guard rejecting 6 excluded templates.

## What Was Built

### Task 1: --enable_http3 CLI plumbing

Added the `--enable_http3` flag end-to-end through the CLI layer with no HTTP/3 directive emission (deferred to 05-02):

- `nginx_set_conf.py`: `@click.option("--enable_http3", is_flag=True, ...)` after `--disable_domain_listen`
- `nginx_set_conf.py`: `enable_http3` parameter in `start_nginx_set_conf` after `disable_domain_listen`
- `nginx_set_conf.py`: `yaml_enable_http3 = yaml_config.get("enable_http3", False)` in YAML read-through block
- `nginx_set_conf.py`: `enable_http3=yaml_enable_http3` and `enable_http3=enable_http3` at both execute_commands call sites
- `nginx_set_conf.py`: interactive path forwards `enable_http3` via yes/no prompt
- `utils.py`: `enable_http3=False` as last parameter in `execute_commands` signature
- `utils.py`: `enable_http3=enable_http3` passed to `validate_all_inputs`
- `utils.py`: `TODO(05-02)` comment at HTTP/3 injection point after `disable_domain_listen` block
- `validators.py`: `enable_http3: bool = False` parameter added to `validate_all_inputs` (no guard yet)

### Task 2: HTTP3_EXCLUDED_TEMPLATES + exclusion guard + tests

- `validators.py`: `HTTP3_EXCLUDED_TEMPLATES = frozenset({...})` with 6 members and per-template rationale comments, adjacent to `VALID_TEMPLATES`
- `validators.py`: HTTP/3 exclusion guard in `validate_all_inputs` after COR-02 guard, raises `ValidationError` naming template and listing HTTP/3-capable alternatives
- `tests/test_validators.py`: `TestHttp3Exclusion` class with 4 methods (9 test cases via parametrize): all pass

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 4b300cb | feat(05-01): wire --enable_http3 flag end-to-end (plumbing only) |
| Task 2 | 9191fe9 | feat(05-01): HTTP3_EXCLUDED_TEMPLATES constant + validate_all_inputs guard + tests |

## Test Results

- Full suite: 218 passed, 2 skipped, 2 xpassed
- TestHttp3Exclusion: 9 tests collected, all PASSED
  - test_excluded_template_raises_validation_error
  - test_included_template_passes
  - test_all_excluded_templates_reject_http3[fast_report]
  - test_all_excluded_templates_reject_http3[mailpit]
  - test_all_excluded_templates_reject_http3[redirect]
  - test_all_excluded_templates_reject_http3[redirect_ssl]
  - test_all_excluded_templates_reject_http3[default_ssl_reject]
  - test_all_excluded_templates_reject_http3[odoo_http]
  - test_http3_false_skips_exclusion_check
- Coverage: 76.29% (gate: 60%)

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written, with one clarification:

**Note on default_ssl_reject parametrize test:** The plan requires `default_ssl_reject` in the parametrize list. Since `default_ssl_reject` is intentionally excluded from `VALID_TEMPLATES`, calling `validate_all_inputs(config_template="default_ssl_reject", enable_http3=True)` raises `ValidationError` via `validate_config_template` (before the HTTP/3 guard runs). The test still passes because it only asserts `pytest.raises(ValidationError)` — the requirement is satisfied. The HTTP/3 guard is not the only path to rejection for this template; the template-validity check fires first. This is correct and intentional.

### Notes on Interactive Path

The plan mentions forwarding `enable_http3` in the interactive path "unchanged". The interactive path collects `enable_http3` from a `retrieve_valid_input` yes/no prompt (same pattern as `disable_domain_listen`) and passes it as `enable_http3=enable_http3` to `execute_commands`. This matches the `disable_domain_listen` analog exactly.

## Known Stubs

None. This plan is pure plumbing — no HTTP/3 directives emitted yet (that is 05-02).

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns introduced. The `enable_http3` YAML value is read via `yaml_config.get("enable_http3", False)` — PyYAML returns a Python bool, no eval risk (T-05-01-01 mitigated). The `HTTP3_EXCLUDED_TEMPLATES` frozenset is immutable — bypass is not possible (T-05-01-02 mitigated).

## Self-Check: PASSED

- nginx_set_conf/nginx_set_conf.py: FOUND (9 occurrences of enable_http3)
- nginx_set_conf/utils.py: FOUND (4 occurrences of enable_http3)
- nginx_set_conf/validators.py: FOUND (HTTP3_EXCLUDED_TEMPLATES frozenset defined)
- tests/test_validators.py: FOUND (TestHttp3Exclusion class with 9 tests)
- Commits 4b300cb and 9191fe9: VERIFIED in git log
