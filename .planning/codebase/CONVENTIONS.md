# Coding Conventions

**Analysis Date:** 2026-05-28

## Naming Patterns

**Files:**
- Module files: `snake_case.py` (e.g., `config_templates.py`, `config_verification.py`)
- Test files: `test_<module>.py` (e.g., `test_utils.py`, `test_validators.py`)
- Template modules: `snake_case.py` matching template name (e.g., `odoo_ssl.py`, `fast_report.py`)
- Config files: pyproject.toml is single source of truth — no `requirements.txt`, no `setup.py`

**Functions:**
- Public API: `snake_case` (e.g., `execute_commands`, `parse_yaml_folder`, `validate_domain`)
- Private/internal: leading underscore `_snake_case` (e.g., `_format_ip_for_nginx`, `_run_command`, `_replace_placeholder`)
- Click entry point: `start_nginx_set_conf` in `nginx_set_conf/nginx_set_conf.py`

**Variables:**
- All `snake_case`
- Constants: `UPPER_SNAKE_CASE` for module-level (e.g., `TEMPLATES`, `VALID_TEMPLATES`, `TEMPLATE` in each template file)
- Regex patterns: `_UPPERCASE_PATTERN` prefix convention (e.g., `_DOMAIN_RE`, `_CERT_PATH_RE`, `_HOSTNAME_LISTEN_PATTERN`)

**Types:**
- Type hints used consistently on all public and private function signatures (introduced in v1.9.0)
- Return type annotations present on all functions in `utils.py` and `validators.py`
- `validators.py` uses `str` return type uniformly; `utils.py` uses `bool`, `dict`, `list`, `str`
- mypy configured in pyproject.toml with `warn_return_any = true` but runs with `continue-on-error: true` in CI — mypy failures do **not** break the build

## Code Style

**Formatter:**
- ruff-format (via `[tool.ruff.format]` in `pyproject.toml`)
- `quote-style = "double"` (enforced)
- Line length: **120** (matches CLAUDE.md target) — `E501` is ignored so the formatter governs long lines, not the linter

**Linter:**
- ruff ≥0.15, configured at `[tool.ruff.lint]`
- Rule sets: `E, W, F, I, B, S, UP` (pycodestyle, pyflakes, isort, bugbear, bandit, pyupgrade)
- Ignored: `E501` (line-too-long), `S603`/`S607` (subprocess validation — inputs validated elsewhere), `W293`/`W291` (trailing whitespace inside template strings)
- Per-file ignores: `tests/*` allows `S101` (assert) and `S108` (/tmp paths in string assertions)

**Pre-commit hooks** (`.pre-commit-config.yaml`):
- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `debug-statements`
- ruff (lint + format), mypy, bandit

**Security scanner:**
- bandit ≥1.8, runs as separate CI job via `uv run bandit -r nginx_set_conf -ll`

## Module Header Pattern

**Documented convention (CLAUDE.md):** Version + date header in each source file.

**Actual state — DRIFT detected:**
- Template files follow the convention: each has a date comment inside the TEMPLATE string (e.g., `# 22.04.2026` on line 2 of `odoo_ssl.py`). Date headers are bumped in lock-step with each version (RELEASE_NOTES.md v1.11.0: "Date header in all 17 template files bumped to 22.04.2026").
- Python module files (`.py`) use a module-level docstring instead: `"""nginx-set-conf - A tool for managing Nginx configurations"""` — **no version/date header in the Python source itself**.
- `nginx_set_conf.py` and `utils.py` carry a copyright comment block (`# Copyright 2014-now Equitania Software GmbH`) *after* the docstring, but **no version number inline**.
- The canonical version lives exclusively in `nginx_set_conf/__init__.py`: `__version__ = "1.11.0"` and in `pyproject.toml` version field.

**In practice:** Version is never duplicated inline in `.py` files; bump-my-version manages the two canonical locations (`__init__.py` and `pyproject.toml`).

## Docstring Style

- Module-level: triple-quoted with a short one-line summary, then optional longer description and `Typical usage example:` section
- Function-level: Google-style with `Args:`, `Returns:`, `Raises:` sections
- Example from `utils.py`:
  ```python
  def parse_yaml(yaml_file: str) -> dict:
      """Parses a YAML file into a Python dictionary.

      Args:
          yaml_file: Path to the YAML file to parse.

      Returns:
          Dictionary containing the parsed YAML data.
          Returns False if parsing fails.

      Raises:
          yaml.YAMLError: If the YAML file is malformed.
      """
  ```
- Short internal helpers (`_replace_placeholder`, `_format_ip_for_nginx`) have full Google-style docstrings

## Comment Language

- All inline comments and docstrings: **English** (consistent with CLAUDE.md)
- One German comment slipped into `all_templates.py` line 85: `# Weitere Templates hier hinzufügen, wenn sie erstellt wurden` — minor drift
- RELEASE_NOTES.md and README.md: English

## Click Conventions

**Option naming:**
- Underscores in Python parameter names: `config_template`, `dry_run`, `target_path`
- CLI flags use underscores too (not hyphens): `--config_template`, `--dry_run`, `--target_path`
- Boolean flags use `is_flag=True`: `--show_template`, `--dry_run`, `--verify_config`, `--sync_config`, `--backup_config`, `--disable_domain_listen`, `--setup_default`, `--migrate_to_wildcard`

**Help text style:**
- Inline multi-line help uses parenthesized string concatenation for long options (e.g., `--disable_domain_listen`)
- Dedicated help block for `--config_template` uses a module-level `eq_config_support` string with `\b` and `\f` for formatting

**Dispatch pattern:**
- Cascading `if` blocks inside `start_nginx_set_conf` — early-return for special operations (migrate_to_wildcard → setup_default → verify/sync/backup → show_template)
- Main path: YAML config file OR direct CLI args OR interactive fallback
- All dispatching delegates to `execute_commands()` in `utils.py`

## Template Conventions

**Module structure:** Each template is a single-file module exporting one module-level string:
```python
"""Template for <Service> NGINX configuration with SSL/HTTP2 support."""

TEMPLATE = """# Template for <Service> configuration nginx incl. SSL/HTTP2 support
# DD.MM.YYYY
...nginx config...
"""
```

**Placeholder syntax (two coexisting systems):**
- Sentinel strings (replaced by `get_default_vars()` values in `utils.py`):
  - `server.domain.de` → domain
  - `ip.ip.ip.ip` → listen-directive IP (v1.11.0+: IP-bound listens only)
  - `zertifikat.crt` → certificate name
  - `zertifikat.key` → certificate key name
- Double-brace placeholders (also replaced via `get_default_vars()`):
  - `{{PORT}}`, `{{POLL_PORT}}`, `{{GRPC_PORT}}` — port numbers
  - `{{BACKEND_IP}}` — proxy_pass target (default: `127.0.0.1`)
  - `{{AUTH_FILE}}` — htpasswd file path (inserted via `_insert_after_marker`)
  - `{{REDIRECT_DOMAIN}}` — redirect target

**Structural rules (enforced by tests):**
- `ip.ip.ip.ip` must appear **only** in `listen` directives (not `proxy_pass`)
- `{{BACKEND_IP}}` must appear in all proxy templates' `proxy_pass`/`grpc_pass` directives
- `server_name server.domain.de;` must be present in every service template
- `listen ip.ip.ip.ip:80;` must be present in all 17 service templates
- `default_ssl_reject` template intentionally has no `{{BACKEND_IP}}` and uses wildcard `default_server` listens

**Cache path convention:**
- All templates use `/tmp` as the literal cache path — `replace_cache_path()` in `all_templates.py` rewrites this to `/var/cache/nginx/<service>` at registration time

## Versioning

**Canonical locations:**
- `nginx_set_conf/__init__.py`: `__version__ = "1.11.0"`
- `pyproject.toml`: `version = "1.11.0"` and `[tool.bump-my-version] current_version = "1.11.0"`

**Bump tool:** bump-my-version (`[tool.bump-my-version]` in `pyproject.toml`), configured to commit + tag automatically. Tag pattern: `v{new_version}`.

**RELEASE_NOTES.md format:**
- `## Version X.Y.Z (DD.MM.YYYY)` heading
- Change items use `**[CHG]**`, `**[ADD]**`, `**[FIX]**` prefixes (same as git commit prefixes)
- Sections: `### Changed`, `### Added`, `### Fixed`, `### Tests`, `### Migration`
- Test count and coverage gate are documented in each release entry

## Git / Commit Conventions

**Prefix discipline (verified from last 25 commits):**
- `[ADD]` — new features, new templates, new tests: consistent
- `[CHG]` — modifications to existing code: consistent
- `[FIX]` — bug fixes: consistent
- `[DOC]` — documentation-only: used once (`9f417b1`)
- One outlier commit without prefix: `0d3a0da  🎯 Zusammenfassung der Implementierung` (emoji-only German message — not following convention)
- **Overall discipline: ~95% adherence**

**Branch model:**
- Active development branch: `2025`
- Integration/default branch: `develop`
- CI triggers on: `main`, `develop`, `2025` (see `.github/workflows/ci.yml`)
- No feature-branch naming convention enforced

## Dependency Management

**Runtime dependencies** (`[project.dependencies]`):
- `click>=8.2.1`
- `PyYAML>=6.0.2`

**Dev dependencies** (`[project.optional-dependencies] dev`):
- pytest, pytest-cov, pytest-mock, ruff, mypy, types-PyYAML, pre-commit, bump-my-version, bandit

**Lock file:** `uv.lock` present and committed — `uv sync --extra dev` is the install command used in CI.

**Build backend:** hatchling (`[build-system]` in `pyproject.toml`), wheel targets `nginx_set_conf/` package only.

**No `requirements.txt`** — pyproject.toml is the single source of truth (consistent with CLAUDE.md).

---

*Convention analysis: 2026-05-28*
