<!-- refreshed: 2026-05-28 -->
# Architecture

**Analysis Date:** 2026-05-28

## System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                           CLI Entry Point                              │
│           nginx_set_conf/nginx_set_conf.py  (Click command)            │
│  --config_template  --config_path  --verify_config  --sync_config      │
│  --backup_config    --migrate_to_wildcard   --setup_default            │
└──────┬──────────────┬─────────────────┬────────────────────────────────┘
       │              │                 │
       ▼              ▼                 ▼
┌────────────┐  ┌──────────────┐  ┌────────────────────────────────────┐
│  Template  │  │  Config      │  │  Migration / Hardening helpers     │
│  Lookup    │  │  Verifier    │  │  (utils.py)                        │
│            │  │              │  │  migrate_configs_to_wildcard()     │
│ config_    │  │ config_      │  │  setup_default_server()            │
│ templates  │  │ verification │  └──────────────┬─────────────────────┘
│ .py        │  │ .py          │                 │
└──────┬─────┘  └──────┬───────┘                 │
       │               │                         │
       ▼               │                         │
┌────────────────────┐ │                         │
│  Template Registry │ │                         │
│  templates/        │ │                         │
│  all_templates.py  │ │                         │
│                    │ │                         │
│  TEMPLATES dict +  │ │                         │
│  replace_cache_    │ │                         │
│  path()            │ │                         │
└──────┬─────────────┘ │                         │
       │               │                         │
       ▼               ▼                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Config Engine (utils.py)                      │
│   validate_all_inputs()  →  get_config_template()  →                  │
│   placeholder substitution (regex + str.replace)  →                   │
│   write <domain>.conf  →  _create_cert_if_needed()                    │
└────────────────────────────────────────────────────────────────────────┘
       │                         │
       ▼                         ▼
┌───────────────┐       ┌──────────────────────────────┐
│  /etc/nginx/  │       │  certbot / openssl            │
│  conf.d/      │       │  (subprocess, optional)       │
│  <domain>.conf│       └──────────────────────────────┘
└───────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI entry point | Flag parsing, dispatch, nginx service lifecycle | `nginx_set_conf/nginx_set_conf.py` |
| Config engine | Input validation, placeholder substitution, file write, SSL | `nginx_set_conf/utils.py` |
| Template registry | Per-service TEMPLATE strings, cache-path uniqueness | `nginx_set_conf/templates/all_templates.py` |
| Backward-compat shim | Legacy `ngx_` prefix aliases, thin wrapper over registry | `nginx_set_conf/config_templates.py` |
| Embedded base templates | nginx.conf / general.conf / security.conf as Python strings | `nginx_set_conf/config_verification.py` |
| Config verifier | SHA256 diff, interactive sync, backup | `nginx_set_conf/config_verification.py` |
| Input validators | RFC 1123 domain, IP, port, path-traversal guards | `nginx_set_conf/validators.py` |
| Package init | Version constant, public re-exports | `nginx_set_conf/__init__.py` |

## Configuration Flow

### YAML batch path (`--config_path`)

1. `parse_yaml_folder(config_path)` reads `*.yaml` / `*.yml` files → list of dicts
   (`utils.py:93`)
2. Each dict entry's fields are extracted and fed to `execute_commands()`
3. `execute_commands()` calls `validate_all_inputs()` — raises `ValidationError` on any bad input
   (`utils.py:558-577`)
4. `get_config_template(config_template, domain)` is called from `utils.py` which delegates to
   `templates/all_templates.py:get_config_template()`. The registry applies
   `replace_cache_path()` at dict-build time (module load), then a second domain-specific
   pass is applied inside `execute_commands()` via inline regex (`utils.py:621-635`).
5. Placeholder substitutions happen in-memory in a fixed order:
   - Listen IP (`ip.ip.ip.ip` → actual IP, IPv6 bracketed)
   - Domain (`server.domain.de` → actual domain)
   - `--disable_domain_listen` strip: `listen <ip>:80` → `listen 80`
   - Backend IP (`{{BACKEND_IP}}` → `127.0.0.1` or supplied value)
   - Certificate paths (Let's Encrypt vs. self-signed branch)
   - Port / pollport / grpcport
   - Auth file injection after `#authentication` marker
   - IP restriction block after `#ip_restrictions` marker
   - Redirect domain (only for `redirect*` templates)
6. Output written to `<target_path>/<domain>.conf` (`utils.py:731-737`)
7. `_create_cert_if_needed()` runs certbot if no Let's Encrypt cert exists (`utils.py:265-296`)

### Direct CLI path (`--config_template --ip --domain --port --cert_name`)

Same as above from step 3, skipping YAML parsing.

### Interactive fallback

When none of the required flags are present, `retrieve_valid_input()` prompts for each field
(`nginx_set_conf.py:415-448`), then calls `execute_commands()`.

### Verification / sync path (`--verify_config`, `--sync_config`, `--backup_config`)

```
start_nginx_set_conf()
  └─ ConfigVerification()
       ├─ backup_configuration()   → /var/backups/nginx_set_conf/<timestamp>/
       ├─ verify_configuration_consistency()
       │    └─ SHA256(server file) vs SHA256(embedded template string)
       ├─ show_verification_results()
       └─ sync_configurations()
            └─ _perform_sync()   → writes embedded template to /etc/nginx/...
```

### Migration path (`--migrate_to_wildcard`)

```
start_nginx_set_conf()
  └─ migrate_configs_to_wildcard(conf_dir)
       ├─ scan *.conf for _HOSTNAME_LISTEN_PATTERN
       ├─ backup all affected files to /var/backups/nginx_set_conf/
       ├─ rewrite listen directives
       ├─ nginx -t → on failure, restore from backup
       └─ return True/False
```

### Default-server hardening path (`--setup_default`)

```
start_nginx_set_conf()
  └─ setup_default_server(target_path)
       ├─ openssl req → /etc/nginx/ssl/default.{crt,key}  (if missing)
       ├─ get_config_template("default_ssl_reject")
       └─ write to <target_path>/00-default.conf
```

## Key Design Principles (verified against code)

**Domain isolation** — HOLDS. Two mechanisms combine:
- `replace_cache_path()` in `all_templates.py:29-82` uses `<service>_<domain_id>` as unique
  identifier for `proxy_cache_path`, `keys_zone`, and `limit_req_zone`.
- A second regex pass in `execute_commands()` (`utils.py:621-635`) re-stamps the unique IDs
  using the actual domain, so concurrent instances never share a cache zone.

**Template modularity** — HOLDS. Each service is a single `*.py` file in `templates/` with one
exported `TEMPLATE` string. Registration is a one-line addition in `all_templates.py` and a
one-line addition in `validators.py:VALID_TEMPLATES`.

**Placeholder system** — HOLDS but split across two layers:
- Static cache-path placeholders: replaced by `replace_cache_path()` at registry load time.
- Runtime placeholders (`ip.ip.ip.ip`, `server.domain.de`, `{{PORT}}`, etc.): replaced in
  `execute_commands()` using `str.replace` or `_insert_after_marker()`.
  Default placeholder values are returned by `get_default_vars()` (`utils.py:114-135`).

**SSL integration** — HOLDS. Two branches:
- Let's Encrypt: no `cert_key` supplied → certbot standalone mode (`utils.py:284-295`).
- Self-signed / purchased: `cert_key` supplied → direct path substitution.

## Extension Points — Adding a New Template

1. Create `nginx_set_conf/templates/<service>.py` exporting `TEMPLATE = "..."`. Use the
   standard placeholders: `ip.ip.ip.ip`, `server.domain.de`, `{{PORT}}`, `zertifikat.crt`,
   `zertifikat.key`, etc. Include `#authentication` and `#ip_restrictions` markers if needed.
2. In `nginx_set_conf/templates/all_templates.py`:
   - Add `from nginx_set_conf.templates.<service> import TEMPLATE as <SERVICE>_TEMPLATE`
   - Add `"<service>": replace_cache_path(<SERVICE>_TEMPLATE, "<service>")` to `TEMPLATES`
   - Add `get_config_template()` call — no change needed (dict lookup is generic).
3. In `nginx_set_conf/validators.py`: add `"<service>"` to `VALID_TEMPLATES` set (line 43).
4. No change needed in `nginx_set_conf.py` (help text is cosmetic only).
5. No change needed in `config_templates.py` (backward-compat shim auto-extends via dict).

## Anti-Patterns

### Double cache-path patching

**What happens:** `replace_cache_path()` runs at module import time inside `all_templates.py`
and bakes a service-only unique ID (e.g., `odoo_ssl_cache`) into the `TEMPLATES` dict.
Then `get_config_template(name, domain)` in `all_templates.py:127-132` calls
`replace_cache_path()` a second time on the already-patched string. Then `execute_commands()`
in `utils.py:621-635` applies a third regex pass on the returned content.
**Why it's wrong:** The chain is fragile — a change in one layer can leave stale zone names in
the rendered config or silently no-op if the first pass already removed the sentinel string.
**Do this instead:** Apply `replace_cache_path()` exactly once, inside `execute_commands()`,
after retrieving the raw template (before any other substitution).

### `config_templates.py` is a deprecated shim that still gets used

**What happens:** `nginx_set_conf.py` imports `get_config_template` from
`nginx_set_conf.config_templates` (`nginx_set_conf.py:27`). That module is marked
"deprecated" in its own docstring (`config_templates.py:28`) but is the live import path
for all CLI operations.
**Why it's wrong:** The shim contains a `print()` side-effect on every domain-specific call
(`config_templates.py:94`) and duplicates every template key twice (once with `ngx_` prefix,
once without). Any new template added to `all_templates.py` must also appear in the shim's
dict or the CLI will reject it.
**Do this instead:** Change `nginx_set_conf.py:27` to import from
`nginx_set_conf.templates.all_templates` directly and delete `config_templates.py`.

## Error Handling

**Strategy:** Log-and-return. `execute_commands()` catches `ValidationError` and prints a
user-friendly message before returning without writing any file (`utils.py:558-577`).
Subprocess failures (certbot, nginx -t) are caught per-call in `_run_command()` and logged;
the caller checks the boolean return value.

**Patterns:**
- `ValidationError(ValueError)` raised by `validators.py`, caught in `execute_commands()`.
- `OSError` caught locally in migration and backup functions with rollback logic.
- `FileNotFoundError` caught in `_run_command()` when a system binary is absent.

## Cross-Cutting Concerns

**Logging:** `logging.getLogger("nginx_set_conf")` with rotating file handler
(1 MB, 3 backups). Path is `/var/log/nginx_set_conf/nginx_set_conf.log` when running as root,
falls back to `./nginx_set_conf.log` otherwise (`nginx_set_conf.py:43-63`).

**Validation:** All user-supplied inputs validated in `validators.py` before any file I/O.
Path-traversal explicitly blocked by `_reject_path_traversal()` (`validators.py:172-185`).

**IPv6 support:** `_format_ip_for_nginx()` wraps IPv6 addresses in brackets for nginx URL
contexts; `_warn_public_backend_ip()` warns when a non-private, non-loopback IP is used as
backend (`utils.py:185-223`).

---

*Architecture analysis: 2026-05-28*
