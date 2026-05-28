# Codebase Structure

**Analysis Date:** 2026-05-28

## Directory Layout

```
nginx-set-conf/
├── nginx_set_conf/           # Installable Python package
│   ├── __init__.py           # Version constant (1.11.0), public re-exports
│   ├── nginx_set_conf.py     # CLI entry point (Click command)
│   ├── utils.py              # Config engine: substitution, deploy, SSL, migration
│   ├── config_templates.py   # DEPRECATED shim — backward-compat ngx_ prefix aliases
│   ├── config_verification.py# Embedded nginx.conf/general.conf/security.conf + sync/backup
│   ├── validators.py         # Input validation: domain, IP, port, cert, path-traversal
│   └── templates/            # Per-service nginx config template modules
│       ├── __init__.py       # Empty init
│       ├── all_templates.py  # TEMPLATES dict, replace_cache_path(), get_config_template()
│       ├── code_server.py    # code-server with SSL
│       ├── default_ssl_reject.py # SNI catch-all (deploys as 00-default.conf)
│       ├── fast_report.py    # FastReport API with SSL
│       ├── flowise.py        # Flowise AI with SSL/HTTP2
│       ├── guacamole.py      # Apache Guacamole with SSL/HTTP2 + WebSocket
│       ├── kasm.py           # Kasm Workspaces with SSL/HTTP2
│       ├── mailpit.py        # Mailpit with SSL/HTTP2
│       ├── n8n.py            # n8n workflow automation with SSL/HTTP2
│       ├── nextcloud.py      # Nextcloud with SSL
│       ├── odoo_http.py      # Odoo HTTP-only (no SSL)
│       ├── odoo_ssl.py       # Odoo with SSL/HTTP2 + longpolling port
│       ├── pgadmin.py        # pgAdmin4 with SSL
│       ├── portainer.py      # Portainer with SSL
│       ├── pwa.py            # Progressive Web App with SSL
│       ├── qdrant.py         # Qdrant vector DB with SSL/HTTP2 + gRPC port
│       ├── redirect.py       # Domain redirect (HTTP, no SSL)
│       ├── redirect_ssl.py   # Domain redirect with SSL
│       └── supabase.py       # Supabase with SSL/HTTP2
├── tests/                    # pytest test suite
│   ├── __init__.py
│   ├── test_migration.py     # migrate_configs_to_wildcard, setup_default_server, _rewrite_listen_directives
│   ├── test_templates.py     # Template registry completeness, cache-path replacement logic
│   ├── test_utils.py         # execute_commands, parse_yaml, get_default_vars, helpers
│   └── test_validators.py    # All validators: domain, IP, port, cert, path, allowed_ips
├── yaml_examples/            # Dev-only example configs (NOT deployed with package)
│   ├── nginx.conf            # Reference nginx.conf (same content as NGINX_CONF_TEMPLATE)
│   ├── nginxconfig.io/
│   │   ├── general.conf      # Reference general.conf
│   │   └── security.conf     # Reference security.conf
│   └── server_config/
│       └── config.yaml       # Example multi-domain YAML config for --config_path
├── dist/                     # Build output — whl + tar.gz for current version
│   ├── nginx_set_conf-1.11.0-py3-none-any.whl
│   └── nginx_set_conf-1.11.0.tar.gz
├── build/                    # Hatchling build artefacts (multiple platform bdist dirs)
├── nginx_set_conf.egg-info/  # Editable-install egg-info (uv pip install -e .)
├── nginx_set_conf_equitania.egg-info/ # STALE — from an older package name (see below)
├── temp/                     # One-off dev file (nginx_hostname_fix.pdf) — gitignored
├── .github/workflows/
│   └── ci.yml                # GitHub Actions CI (lint + test)
├── .pre-commit-config.yaml   # Pre-commit hooks (ruff, mypy, bandit)
├── pyproject.toml            # Single source of truth: deps, entry points, tool config
├── uv.lock                   # UV lockfile
├── README.md                 # Usage documentation
├── RELEASE_NOTES.md          # Changelog / version history
├── CLAUDE.md                 # Claude Code project context
└── LICENSE.txt               # AGPL-3.0
```

## Key File Locations

**Entry Point:**
- `nginx_set_conf/nginx_set_conf.py`: Click command `start_nginx_set_conf`, registered as
  `nginx-set-conf` script in `pyproject.toml:50`

**Configuration Engine:**
- `nginx_set_conf/utils.py`: `execute_commands()` is the central function called for every
  config generation; also contains migration helpers

**Template System:**
- `nginx_set_conf/templates/all_templates.py`: Authoritative template registry — add new
  templates here
- `nginx_set_conf/templates/<service>.py`: One file per proxied service, exports `TEMPLATE`

**Validation:**
- `nginx_set_conf/validators.py`: `validate_all_inputs()` is called before any I/O in
  `execute_commands()`; `VALID_TEMPLATES` whitelist must be kept in sync with the registry

**Embedded base configs:**
- `nginx_set_conf/config_verification.py`: Contains `NGINX_CONF_TEMPLATE`,
  `GENERAL_CONF_TEMPLATE`, `SECURITY_CONF_TEMPLATE` as Python string constants —
  the authoritative source for `/etc/nginx/nginx.conf`,
  `/etc/nginx/nginxconfig.io/general.conf`, and
  `/etc/nginx/nginxconfig.io/security.conf`

**Testing:**
- `tests/test_utils.py`: Unit tests for `execute_commands`, YAML parsing, placeholder helpers
- `tests/test_templates.py`: Asserts all 18 templates are registered and non-trivially long
- `tests/test_migration.py`: Tests `_rewrite_listen_directives`, `migrate_configs_to_wildcard`,
  `setup_default_server` using `tmp_path` fixtures
- `tests/test_validators.py`: Parameterised tests for every validator function

## Naming Conventions

**Files:**
- Template modules: `<service_name>.py` (snake_case matching the CLI template key)
- Test files: `test_<module>.py`

**Directories:**
- Package directory matches PyPI name with underscores: `nginx_set_conf/`

**Placeholders inside templates:**
- Runtime string literals (not `{{...}}`): `ip.ip.ip.ip`, `server.domain.de`,
  `zertifikat.crt`, `zertifikat.key`
- Double-brace `{{...}}` style used for ports: `{{PORT}}`, `{{POLL_PORT}}`, `{{GRPC_PORT}}`,
  `{{BACKEND_IP}}`
- Marker comments for injected blocks: `#authentication`, `#ip_restrictions`

## Where to Add New Code

**New proxied service template:**
1. `nginx_set_conf/templates/<service>.py` — create with `TEMPLATE = "..."`, using
   `ip.ip.ip.ip` and `server.domain.de` as listen/server_name placeholders
2. `nginx_set_conf/templates/all_templates.py` — import + add to `TEMPLATES` dict with
   `replace_cache_path(...)`
3. `nginx_set_conf/validators.py` — add name to `VALID_TEMPLATES` set

**New CLI flag:**
- Add `@click.option(...)` in `nginx_set_conf/nginx_set_conf.py`
- Add corresponding parameter to `execute_commands()` signature in `utils.py`
- Add validator in `validators.py` if the value is user-supplied and written to a file

**New validation rule:**
- `nginx_set_conf/validators.py` — add standalone `validate_<thing>()` function,
  call from `validate_all_inputs()`

**New base nginx config template:**
- Add string constant to `nginx_set_conf/config_verification.py`
- Add entry to `self.required_files` and `self.templates` in `ConfigVerification.__init__`

## Special Directories

**`dist/`:**
- Purpose: `uv build` output (wheel + sdist)
- Generated: Yes
- Committed: Yes — `.gitignore` only excludes `/dist/` via a `/dist/` entry that is absent
  from the actual `.gitignore`; the current `.gitignore` lists `dist/` without a leading `/`,
  so it would suppress tracking, but the files appear in the working tree. Verify with
  `git ls-files dist/` before publishing.

**`build/`:**
- Purpose: Hatchling intermediate build artefacts (platform-specific bdist dirs)
- Generated: Yes
- Committed: Covered by `build/` in `.gitignore` — should not be tracked

**`nginx_set_conf.egg-info/`:**
- Purpose: Created by `uv pip install -e .`
- Generated: Yes
- Committed: Covered by `*.egg-info/` in `.gitignore` — should not be tracked

**`nginx_set_conf_equitania.egg-info/`:**
- Purpose: STALE artefact from an older package name (`nginx-set-conf-equitania` or similar).
  Contains duplicate `entry_points.txt` and `top_level.txt`. Safe to delete.
- Generated: Yes (legacy)
- Committed: Should NOT be tracked; verify with `git ls-files nginx_set_conf_equitania.egg-info/`

**`temp/`:**
- Purpose: One-off developer reference file (`nginx_hostname_fix.pdf`)
- Generated: Manual
- Committed: Listed in `.gitignore` — not tracked

**`yaml_examples/`:**
- Purpose: Development reference only. The `nginx.conf` / `general.conf` / `security.conf`
  here match the embedded constants in `config_verification.py`. Not packaged (not listed in
  `[tool.hatch.build.targets.wheel] packages`).
- Generated: Manual
- Committed: Yes (dev convenience)

---

*Structure analysis: 2026-05-28*
