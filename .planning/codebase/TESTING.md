# Testing Patterns

**Analysis Date:** 2026-05-28

## Test Framework

**Runner:**
- pytest ≥9.0
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest native assertions (no unittest.TestCase)

**Coverage:**
- pytest-cov ≥7.0
- Gate: `--cov-fail-under=60` (actual coverage ~64% as of v1.11.0)
- `nginx_set_conf/nginx_set_conf.py` (Click entry point) excluded from coverage measurement via `[tool.coverage.run] omit`

**Mocking:**
- pytest-mock ≥3.15 (available as dev dep); actual tests use `monkeypatch` (built-in pytest fixture)

**Run Commands:**
```bash
uv run pytest                                  # Run all tests with coverage
uv run pytest tests/test_utils.py             # Single file
uv run pytest -k TestExecuteCommands          # Single class
uv run pytest --no-cov                        # Skip coverage
uv run pytest -v --tb=long                    # Verbose with full tracebacks
```

**CI command:** `uv run --python ${{ matrix.python-version }} pytest` (addopts from pyproject.toml are applied automatically)

## Test File Inventory

| File | Lines | What it covers |
|------|-------|----------------|
| `tests/test_utils.py` | 503 | `self_clean`, `parse_yaml`, `parse_yaml_folder`, `get_default_vars`, `_replace_placeholder`, `_insert_after_marker`, `execute_commands` (dry-run, file generation, validation rejection, IP restrictions, auth, disable_domain_listen, cache paths), `_format_ip_for_nginx`, `_warn_public_backend_ip`, IPv6 proxy_pass/grpc_pass end-to-end |
| `tests/test_validators.py` | 306 | All functions in `validators.py`: `validate_domain`, `validate_ip`, `validate_port`, `validate_allowed_ips`, `validate_target_path`, `validate_cert_name`, `validate_cert_key`, `validate_auth_file`, `validate_config_template`, `validate_all_inputs` — injection attacks, path traversal, IPv6, CIDR, backward-compat `ngx_` prefix |
| `tests/test_templates.py` | 273 | Template registry completeness (18 templates), cache path replacement, `get_config_template` API, `{{BACKEND_IP}}` invariant across all proxy templates, `ip.ip.ip.ip` restricted to listen directives, `TestIpBoundListen` (all 17 service templates), `TestDefaultSslReject` (6 assertions), `--disable_domain_listen` end-to-end, IPv6 listen bracketing |
| `tests/test_migration.py` | 361 | `_rewrite_listen_directives` regex (7 cases), `migrate_configs_to_wildcard` (dry-run, backup, rewrite, nginx-t gate, rollback on failure, write-failure rollback), `setup_default_server` (dry-run, cert generation, cert-already-exists skip, openssl failure) |

**Total test lines:** ~1 443

**Last known count:** 153 tests (v1.11.0, per RELEASE_NOTES.md)

## Test File Organization

**Location:** Co-located in `tests/` directory (separate from source, not next to modules)

**Naming:**
- File: `test_<source_module>.py`
- Class: `Test<FeatureName>` (PascalCase)
- Function: `test_<what_it_checks>` (snake_case, descriptive)

**Structure:**
```
tests/
├── __init__.py          # empty
├── test_migration.py    # migration helpers
├── test_templates.py    # template registry + invariants
├── test_utils.py        # utils + execute_commands
└── test_validators.py   # input validation
```

No `conftest.py` — shared setup is handled by pytest's built-in `tmp_path` and `monkeypatch` fixtures only.

## Test Structure Pattern

Classes group related tests without shared setup (no `setup_method`/teardown):

```python
class TestExecuteCommands:
    def test_dry_run_creates_no_files(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        execute_commands(config_template="odoo_ssl", domain="test.example.com", ...)
        assert not os.path.exists(os.path.join(target, "test.example.com.conf"))

    def test_generates_config_file(self, tmp_path):
        os.makedirs(target, exist_ok=True)
        execute_commands(...)
        content = open(config_file).read()
        assert "test.example.com" in content
        assert "{{PORT}}" not in content  # placeholders fully replaced
```

Key patterns:
- **`tmp_path`** fixture used for all file I/O tests (never writes to real system paths)
- **`monkeypatch.setattr`** to stub `_run_command` so tests do not invoke `nginx`, `systemctl`, `certbot`, or `openssl`
- **`caplog`** with `at_level(logging.WARNING, logger="nginx_set_conf")` for warning assertions
- **String content assertions** on generated nginx config files (no snapshots)

## Mocking

**Framework:** pytest's built-in `monkeypatch` (not `unittest.mock` directly)

**What is mocked:**
- `nginx_set_conf.utils._run_command` — stubs out all subprocess calls (nginx -t, systemctl, certbot, openssl)
- `pathlib.Path.write_text` — used in one rollback test to simulate a disk-full write failure

**What is NOT mocked:**
- File system (real `tmp_path` directories used)
- Template loading (real `TEMPLATES` dict)
- YAML parsing (real PyYAML)
- Input validation (real `validators.py`)

**Pattern:**
```python
from nginx_set_conf import utils as utils_module
monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)
```

## Coverage Analysis

**Gate:** 60% minimum (pyproject.toml `--cov-fail-under=60`), actual ~64% (v1.11.0)

**Well-covered modules:**
- `nginx_set_conf/validators.py` — high coverage via `test_validators.py` (all functions, all error paths)
- `nginx_set_conf/utils.py` — good coverage for `execute_commands`, `_format_ip_for_nginx`, `_warn_public_backend_ip`, migration helpers
- `nginx_set_conf/templates/*.py` — structural invariants covered via `test_templates.py`
- `nginx_set_conf/templates/all_templates.py` — `replace_cache_path`, `get_config_template` covered

**Coverage gaps (untested paths):**
- `nginx_set_conf/nginx_set_conf.py` — **explicitly excluded** from coverage measurement; the Click entry point (`start_nginx_set_conf`) and its dispatch logic are not unit-tested. Behavior is covered only indirectly via `execute_commands` tests.
- `nginx_set_conf/config_verification.py` — `ConfigVerification` class (`verify_configuration_consistency`, `sync_configurations`, `backup_configuration`, `show_verification_results`) has **no dedicated test file**. The `--verify_config`, `--sync_config`, and `--backup_config` paths are not exercised by the test suite.
- Interactive mode fallback in `start_nginx_set_conf` (the `else` branch calling `retrieve_valid_input` in a loop) — untested.
- `parse_yaml` error path returning `False` is tested; the logging path in `parse_yaml_folder` for skipped non-YAML files is not.

## CI/CD

**Workflow:** `.github/workflows/ci.yml` (GitHub Actions)

**Jobs:**
1. **`lint-and-test`** — matrix over Python 3.10, 3.11, 3.12, 3.13 on `ubuntu-latest`
   - ruff lint + format check
   - mypy (`continue-on-error: true` — type failures do not block the build)
   - pytest with coverage (gate at 60%)
2. **`security`** — bandit scan on Python 3.12 only (`uv run bandit -r nginx_set_conf -ll`)

**Trigger:** push and pull_request to `main`, `develop`, `2025`

**No publish step in CI** — build (`uv build`) and publish (`uvpublish`) run locally only (per project memory note).

## Manual Testing Constraint

Per `CLAUDE.md`: "Claude cannot test anything locally. Building and deployment is handled by the user." This means:
- No integration tests against a live nginx installation
- No end-to-end tests for SSL certificate generation (certbot/Let's Encrypt paths)
- No tests for systemctl service management
- The `dry_run=True` mode plus `monkeypatch` is the substitute for system-level testing

## Test Gaps Summary

| Gap | Risk | Priority |
|-----|------|----------|
| `config_verification.py` — entire `ConfigVerification` class untested | Medium: verify/sync/backup commands could regress silently | High |
| `nginx_set_conf.py` Click entry point — dispatch logic excluded from coverage | Low: logic is thin; real work in `execute_commands` | Low |
| `--setup_default` / `setup_default_server` cert path when `openssl` binary absent | Low: guarded by `_run_command` returning False | Medium |
| Interactive input loop (`retrieve_valid_input` calls) | Low: rarely used code path | Low |

---

*Testing analysis: 2026-05-28*
