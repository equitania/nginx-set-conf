---
phase: "03-tech-debt-repository-cleanup"
plan: "03"
subsystem: "templates, cli-wizard"
tags: ["template-cleanup", "tdd", "interactive-wizard", "nginx-directives"]
dependency_graph:
  requires: ["03-01"]
  provides: ["03-04"]
  affects: ["nginx_set_conf/templates/redirect.py", "nginx_set_conf/templates/redirect_ssl.py", "nginx_set_conf/nginx_set_conf.py"]
tech_stack:
  added: []
  patterns: ["TDD RED/GREEN", "Click option help text", "retrieve_valid_input pattern"]
key_files:
  created: []
  modified:
    - "nginx_set_conf/templates/redirect.py"
    - "nginx_set_conf/templates/redirect_ssl.py"
    - "nginx_set_conf/nginx_set_conf.py"
    - "tests/test_templates.py"
decisions:
  - "TDD RED-GREEN cycle: absence tests written first, then templates stripped"
  - "cert_key prompt uses retrieve_valid_input (existing helper, no new function)"
  - "Empty cert_key input is valid — semantics match existing LE auto-generate default"
metrics:
  duration: "~8 min"
  completed: "2026-05-29"
  tasks_completed: 2
  files_modified: 4
requirements:
  - TD-05
  - TD-06
---

# Phase 03 Plan 03: Redirect Template Slim-Down + Interactive cert_key Prompt Summary

Stripped orphaned proxy_cache_path/limit_req_zone directives from redirect templates via TDD, and added cert_key prompt to interactive wizard with clarified --help text.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing absence tests for redirect template slim-down | 0d044a0 | tests/test_templates.py |
| 1 (GREEN) | Strip proxy_cache_path and limit_req_zone from redirect templates | e73c7ce | redirect.py, redirect_ssl.py |
| 2 | cert_key prompt in interactive wizard + clarified --help | 43024ea | nginx_set_conf.py |

## What Was Built

**Task 1 — Redirect template slim-down (TDD):**
- Added `TestRedirectTemplateSlimDown` class to `tests/test_templates.py` with 6 test methods:
  - `test_redirect_no_proxy_cache_path` (absence assertion)
  - `test_redirect_no_limit_req_zone` (absence assertion)
  - `test_redirect_ssl_no_proxy_cache_path` (absence assertion)
  - `test_redirect_ssl_no_limit_req_zone` (absence assertion)
  - `test_redirect_core_functionality_intact` (rewrite + upstream still present)
  - `test_redirect_ssl_core_functionality_intact` (ssl_certificate + rewrite still present)
- Removed two orphaned directives from `redirect.py` TEMPLATE string:
  - `proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m ...`
  - `limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m ...`
- Same two directives removed from `redirect_ssl.py` TEMPLATE string
- upstream block, map block, server blocks, SSL config all preserved intact

**Task 2 — Interactive wizard cert_key prompt:**
- Added `cert_key = retrieve_valid_input("Path to certificate key file (leave empty for Let's Encrypt auto-generate)\n")` immediately after `cert_name` prompt in the interactive else-branch
- Updated `--cert_key` Click option help text to explicitly document both paths:
  - Self-signed/purchased: provide key file path
  - Let's Encrypt: leave empty (auto-generates)

## Verification

```
python -m pytest tests/test_templates.py::TestRedirectTemplateSlimDown -x -q
# 6 passed

python -m pytest -x -q
# 200 passed, 2 skipped, 2 xpassed — 72% coverage

python -c "
from nginx_set_conf.templates.all_templates import get_config_template
r = get_config_template('redirect')
rs = get_config_template('redirect_ssl')
assert 'proxy_cache_path' not in r
assert 'limit_req_zone' not in r
assert 'proxy_cache_path' not in rs
assert 'limit_req_zone' not in rs
print('All absence assertions pass')
"
# All absence assertions pass
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Removing orphaned nginx shared-memory zone declarations from redirect templates is a pure subtraction. Confirmed: no consumer directives (proxy_cache, limit_req) exist in the redirect server blocks — the removal is safe.

## Known Stubs

None.

## Self-Check: PASSED

- [x] tests/test_templates.py — TestRedirectTemplateSlimDown class with 6 methods present
- [x] nginx_set_conf/templates/redirect.py — proxy_cache_path and limit_req_zone absent
- [x] nginx_set_conf/templates/redirect_ssl.py — proxy_cache_path and limit_req_zone absent
- [x] nginx_set_conf/nginx_set_conf.py — cert_key retrieve_valid_input call at line 432
- [x] Commit 0d044a0 (RED), e73c7ce (GREEN), 43024ea (Task 2) — all exist in git log
