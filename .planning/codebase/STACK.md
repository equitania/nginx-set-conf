# Technology Stack

**Analysis Date:** 2026-05-28

## Languages

**Primary:**
- Python 3.10+ - All application code (`nginx_set_conf/`)

**Secondary:**
- None

## Runtime

**Environment:**
- CPython `>=3.10` (declared); classifiers confirm 3.10, 3.11, 3.12, 3.13

**Package Manager:**
- uv (project toolchain; `uv build`, `uv pip install -e .`)
- Lockfile: `uv.lock` present and committed

## Frameworks

**Core:**
- Click `>=8.2.1` (resolved: `8.3.2`) — CLI entry point, option parsing, `@click.command` / `@click.option`
- PyYAML `>=6.0.2` (resolved: `6.0.3`) — parses `config.yaml` YAML input files

**Testing:**
- pytest `>=9.0` — test runner; config in `[tool.pytest.ini_options]`
- pytest-cov `>=7.0` — coverage reporting; gate at 60% (`--cov-fail-under=60`)
- pytest-mock `>=3.15` — mocking helpers
- mypy `>=1.20` — static type checking; target `python_version = "3.10"`
- types-PyYAML `>=6.0` — stubs for mypy

**Build/Dev:**
- hatchling — build backend (`pyproject.toml` line 2: `build-backend = "hatchling.build"`)
- ruff `>=0.15` (resolved: `0.15.1`/`0.15.11`) — linting + formatting; `line-length = 120`, `target-version = "py310"`
- bump-my-version `>=1.3` (resolved: `1.3.0`) — version bumping; updates `nginx_set_conf/__init__.py` and `pyproject.toml`
- pre-commit `>=4.0` — git hooks; config in `.pre-commit-config.yaml`
- bandit `>=1.8` (resolved: `1.9.4`) — security linting

## Key Dependencies

**Critical:**
- `click 8.3.2` — entire CLI surface is built on Click decorators; entry point defined as `nginx_set_conf.nginx_set_conf:start_nginx_set_conf`
- `PyYAML 6.0.3` — reads `config.yaml` / YAML folder; used in `nginx_set_conf/utils.py:parse_yaml()` and `parse_yaml_folder()`

**Infrastructure:**
- Standard library only beyond the two runtime deps: `os`, `re`, `shutil`, `subprocess`, `pathlib`, `hashlib`, `ipaddress`, `logging`, `datetime`

## Configuration

**Environment:**
- No `.env` file; all runtime configuration passed via CLI flags or YAML config files
- Key YAML keys: `template`, `domain`, `ip`, `port`, `poll_port`, `grpc_port`, `cert_name`, `cert_key`, `redirect_domain`, `auth_file`, `allowed_ips`, `target_path`, `backend_ip`

**Build:**
- `pyproject.toml` — single source of truth for deps, version, ruff, pytest, mypy, bump-my-version config
- `[tool.hatch.build.targets.wheel]` packages only `nginx_set_conf/` directory

## Distribution

**PyPI package name:** `nginx-set-conf`
**Current version:** `1.11.0` (`nginx_set_conf/__init__.py:9`)
**Console script:** `nginx-set-conf` → `nginx_set_conf.nginx_set_conf:start_nginx_set_conf`
**License:** AGPL-3.0-or-later
**Homepage:** https://github.com/equitania/nginx-set-conf

## CI

**GitHub Actions:** `.github/workflows/ci.yml` present
**Publish:** Local only — `uv build` + `uvpublish` run by maintainer; no publish step in CI

## Linting Rules

**ruff lint selects:** E, W, F, I (isort), B (bugbear), S (bandit), UP (pyupgrade)
**Notable ignores:**
- `S603`/`S607` — subprocess calls (inputs are validated via `nginx_set_conf/validators.py`)
- `W293`/`W291` — trailing whitespace inside template strings
- `S101` — assert in tests allowed

## Test Coverage

- `testpaths = ["tests"]`; 4 test files: `test_migration.py`, `test_templates.py`, `test_utils.py`, `test_validators.py`
- CLI entry point (`nginx_set_conf/nginx_set_conf.py`) excluded from coverage (`[tool.coverage.run] omit`)
- Minimum gate: 60% (v1.10.2 baseline: 64%)

---

*Stack analysis: 2026-05-28*
