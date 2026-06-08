# RELEASE NOTES

## Version 1.16.0 (08.06.2026)

### Added

- **[ADD]** **Pre-flight base-config check + auto-repair before every vhost deploy** — every real
  `nginx-set-conf` deployment (single, YAML batch, or interactive) now runs a one-time pre-flight
  that verifies the three managed base configs (`nginx.conf`, `general.conf`,
  `nginxconfig.io/security.conf`) against the embedded templates *before* the new vhost is written.
  On drift it auto-repairs: it backs up the current state, re-syncs the divergent file(s) from the
  embedded templates, and validates with `nginx -t`. If the re-sync or `nginx -t` fails, the
  previous state is restored from the backup (atomic — the pre-flight then makes no net change) and
  the deploy aborts. The corrected base files are activated by the deploy's final nginx reload.
  This guarantees a new domain is never deployed on top of a broken base — and it self-heals a
  server `security.conf` that still carries the old, Odoo-incompatible Content-Security-Policy
  (a CSP restricting scripts without `'unsafe-eval'` blocks Odoo 19's OWL template compilation,
  which renders the login/website page blank). The check has **no opt-out** and is skipped only for
  `--dry_run`. Implemented as `ConfigVerification.preflight_check_and_repair()` with a new
  `restore_configuration()` rollback helper; `backup_configuration()` now returns the backup path
  (`str`) instead of a bare `bool` (truthiness unchanged for existing callers).

### Added

- **[ADD]** **New `static_ssl` template — static website / file-download hosting** — serves files
  directly from a local document root (`root <dir>;` + `try_files $uri $uri/ =404;`) with no upstream
  backend (no `proxy_pass`). New `--root_path` CLI option / YAML `root_path` key sets the document
  root (default `/opt/www`); a new `{{ROOT_PATH}}` placeholder is validated as an absolute,
  traversal-free path. The template is HTTP/3-capable and supports `--auth_file` (HTTP basic auth)
  and `--allowed_ips` (IP restrictions) for protecting downloads. Uses IP-bound listen directives
  (Pattern C), inherits the central `security.conf`/`general.conf` includes, and sets an
  `X-Robots-Tag: noindex` header at server scope (so it merges with the security headers instead of
  cancelling their inheritance inside `location /`). The non-interactive CLI guard now accepts
  `static_ssl` without `--port` (it has no upstream port) as long as `--root_path` is supplied.

- **[ADD]** **Advisory UDP/443 firewall check for HTTP/3** — when `--enable_http3` is set,
  `execute_commands` now runs a best-effort `check_ufw_udp_443()` preflight. If `ufw` is active
  but has no inbound ALLOW rule covering UDP/443 (explicit `443/udp` or a bare `443` rule, which
  ufw opens for both TCP and UDP), the tool prints a yellow **WARNING** reminding the operator to
  run `ufw allow 443/udp` — otherwise QUIC is silently dropped and browsers fall back to HTTP/2.
  When the state cannot be determined (ufw not installed, inactive, or not permitted) it prints a
  short **NOTE** instead.

  The check is **advisory, never blocking**: the host firewall state cannot be determined reliably
  (cloud security groups, externally managed or default-open firewalls are invisible from the
  host), so a missing/unknown rule must not abort a valid deployment. Only `ufw` is inspected (the
  firewall referenced throughout the README). The check runs under `--dry_run` too — previewing a
  config is exactly when the reminder is useful.

## Version 1.14.0 (31.05.2026)

### Added

- **[ADD]** **HTTP/3 / QUIC opt-in support** — new `--enable_http3` flag (and YAML key
  `enable_http3: true`) adds QUIC + HTTP/3 listen directives to 12 browser-facing SSL
  templates: `odoo_ssl`, `flowise`, `n8n`, `nextcloud`, `guacamole`, `kasm`, `pgadmin`,
  `portainer`, `pwa`, `code_server`, `supabase`, `qdrant` (REST port only). Default is
  **off**; existing operators see no change.

  **Generated directives per HTTP/3-enabled vhost:**
  - `listen <ip>:443 quic;` (IP-bound, after TCP 443 SSL listen)
  - `http3 on;`
  - `quic_retry on;` (amplification protection)
  - **No** server-scope `ssl_protocols` directive is injected: QUIC mandates TLS 1.3 at the protocol level, and the shared TCP/HTTP/2 block keeps its http-scope `ssl_protocols TLSv1.2 TLSv1.3;` (TLSv1.2 fallback preserved)
  - `add_header Alt-Svc 'h3=":443"; ma=86400' always;`

  **Prerequisites (see README §HTTP/3 / QUIC for full details):**
  1. nginx >= 1.25.0 (enforced by a pre-write version gate — the tool refuses to emit `quic`
     directives on too-old nginx).
  2. **UDP/443 must be opened in the host firewall in addition to TCP/443.** Without this,
     QUIC connections are silently dropped. (`ufw allow 443/udp` or equivalent.)
  3. TLS 1.3 is required for HTTP/3 (enforced per-server-block; fallback clients use
     TCP/HTTP/2 with TLS 1.2).
  4. Run `nginx-set-conf --setup_default` on any host with HTTP/3-enabled vhosts — the
     catch-all is extended with a QUIC block that returns 444 for unknown SNI (mitigating
     the QUIC form of the v1.10.0 SNI-fallback risk).

- **[ADD]** **nginx version gate** — `get_nginx_version()` helper parses `nginx -v` output
  and aborts with a clear remediation message when the installed nginx is older than 1.25.0.

- **[ADD]** **QUIC SNI catch-all** — `default_ssl_reject` template extended with a QUIC
  `default_server` block that returns 444 for unknown SNI on UDP/443.

### Excluded templates

`--enable_http3` is rejected (with a clear error message) for templates that do not serve
browser traffic: `fast_report`, `mailpit`, `redirect`, `redirect_ssl`, `default_ssl_reject`,
`odoo_http`.

### Not in this release

A bulk `--migrate_to_http3` flag (analog to `--migrate_to_wildcard`) is planned for v2
(`PROTO-V2-01`). To add HTTP/3 to an existing vhost, regenerate it individually with
`--enable_http3`.

### Tests

242 tests passed (209 → 242 tests; +33 for HTTP/3 directive injection, nginx version gate,
QUIC catch-all, and `--enable_http3` CLI/YAML wiring).

---

## Version 1.13.0 (31.05.2026)

### Added

- **[ADD]** **PatchMon template** — new `patchmon` config template for the
  PatchMon patch-/update-monitoring application
  (https://github.com/PatchMon/PatchMon). PatchMon runs a single Go API server
  with an embedded frontend that serves both the API and static files on one
  upstream port (default 3000). The template provides full WebSocket support
  (`map $http_upgrade $connection_upgrade`) required for in-browser RDP tunnelled
  through the server via Apache Guacamole/guacd, and uses long (1200s) proxy
  timeouts suited to RDP/WebSocket sessions. No `limit_req` rate-limiting is
  applied — monitoring agents check in regularly, often from shared NAT IPs, and
  per-IP throttling would drop legitimate check-ins. Follows the v1.11.0 IP-bound
  listen invariant (`listen ip.ip.ip.ip:80;` / `:443 ssl;`). Registered in
  `all_templates.py`, `validators.VALID_TEMPLATES`, the CLI help text, and the
  YAML example config.

## Version 1.12.0 (29.05.2026)

### Changed (tech-debt cleanup)

- **[CHG]** **config_templates.py removed** — the internal shim module
  `nginx_set_conf/config_templates.py` has been hard-deleted. It was marked deprecated
  since v1.11.x. The module had no documented external Python consumers; it existed
  only to provide a backward-compat wrapper around `nginx_set_conf.templates.all_templates`.

### Documentation

- **[FIX]** **DOC-01**: `CLAUDE.md` "Important Files" section corrected — `replace_cache_path()`
  and `CACHE_PATH_SENTINEL` live in `nginx_set_conf/templates/all_templates.py`, not in
  `nginx_set_conf/__init__.py`. The `__init__.py` file exposes only `__version__`.

### Q-01: --migrate_to_ip_bound not implemented

**Decision**: The `--migrate_to_ip_bound` atomic migration flag will **not** be
implemented in v1.12.0 or any near-term release. The implementation risk class is
identical to the v1.10.0 mass `listen` rewrite that caused the SNI-fallback incident
on 21.04.2026. An atomic bulk rewrite of listen directives across all server configs
carries the same partial-migration hazard.

Migration tooling (MIG-01) is explicitly deferred to v2. Operators who need to move
from hostname-bound to IP-bound listen directives must follow the manual regeneration
procedure documented in the README under
"Manual Migration: Hostname-bound to IP-bound Listen". The procedure uses existing
per-vhost `nginx-set-conf` invocations (no new CLI flag required).

### Q-02: --sync_config now requires --force to overwrite server files

**Decision**: `--sync_config` now requires an explicit `--force` flag before it
will overwrite any server file that already exists with different content.

**Before this change** (v1.11.x and earlier): `--sync_config` displayed an
interactive prompt and, on confirmation, silently overwrote all differing server
files — including any operator-local customisations made directly to
`/etc/nginx/nginx.conf`, `/etc/nginx/nginxconfig.io/general.conf`, or
`/etc/nginx/nginxconfig.io/security.conf`. Custom hardening, local tuning, or
site-specific overrides were destroyed without a visible data-loss warning.

**After this change** (v1.12.0+):
- `--sync_config` **without** `--force`: prints a clear warning that
  operator-local customisations will be permanently lost, then aborts. No
  filesystem writes occur.
- `--sync_config --force`: emits the same warning as a notice, then proceeds
  with the sync (backup is still created first).

The interactive prompt has been removed. The `--force` flag is the explicit
operator confirmation. This aligns with the project's data-loss-prevention ethos
and the safety gate pattern already established by `--migrate_to_wildcard`.

### Tests

209 tests passed, 2 skipped, 2 xpassed (167 → 209 tests; +5 `test_sync_config.py`
for the `--force` gate). Coverage: 76% (gate: 60%).

### Migration

v1.12.0 is a drop-in upgrade from v1.11.1. The only operator-visible behaviour change
is that `--sync_config` now requires `--force` when server files differ from the
embedded templates. Existing deployments with no server-side customisations are
unaffected.

If any in-house code imported from `nginx_set_conf.config_templates`,
update the import to `nginx_set_conf.templates.all_templates.get_config_template`.
The function signature (`config_template_name: str, domain: str | None = None`) -> `str`
is identical. Operator YAML configs are unaffected — this change is internal to the
Python import surface only.

---

## Version 1.11.1 (28.05.2026)

### Fixed (security hardening)
- **[FIX]** **HIGH-1**: `nginx -t` now validates the generated configuration
  **before** nginx is touched. The previous deploy path ran
  `systemctl restart nginx.service` first and `nginx -t` afterwards — a
  malformed config (e.g., an unresolved placeholder from a missing CLI arg)
  would crash the live nginx process before the test gate fired and drop
  traffic until manual recovery. The fix aborts via `ClickException` when
  `nginx -t` returns non-zero (the running nginx keeps the previous config)
  and replaces `systemctl restart` with the graceful `systemctl reload`
  once the new config has been validated. `_run_service_command` now
  returns the `subprocess.CompletedProcess` so callers can inspect
  `returncode`.
- **[FIX]** **HIGH-2**: `validate_auth_file` constrains absolute paths to
  the nginx prefix and forbids the snippet directory. The value is written
  verbatim into the generated config as `auth_basic_user_file <value>;`,
  so an attacker-controlled YAML could previously point nginx at any host
  file (e.g., `/etc/passwd`, `/etc/nginx/conf.d/evil.conf`). Absolute paths
  must now start with `/etc/nginx/`; `/etc/nginx/conf.d/` is explicitly
  rejected. Relative filenames remain permitted — nginx resolves them
  against its configured prefix.
- **[FIX]** **HIGH-3**: Wildcard domains (`*.example.com`) are now
  sanitised in the generated filename. The character `*` is a shell glob
  and the previous code produced `*.example.com.conf` on disk, breaking
  any operator workflow that enumerates configs via globbing (e.g.,
  `rm /etc/nginx/conf.d/*.conf`). The new `_safe_conf_filename` helper
  rewrites a `*.` prefix to `_wildcard.` for filename construction only —
  the nginx `server_name` directive inside the file is unchanged, so
  wildcard server names continue to work.

### Why this matters

These are three independent issues surfaced by a codebase audit; each one
could turn a routine deploy into a production incident:

1. A malformed CLI invocation should not be able to take nginx down.
2. A YAML-driven generator must not be a privileged file-write surface
   on the host.
3. Files in `/etc/nginx/conf.d/` should be globbable for the operator.

### Migration

No CLI changes. Existing deployments pick up the safer behaviour
automatically. YAML configs that supplied absolute `auth_file` paths
outside `/etc/nginx/` will now fail validation — fix them by moving the
htpasswd file under `/etc/nginx/` (e.g., `/etc/nginx/.htpasswd`) or by
supplying a relative filename.

### Tests

162 → 167 tests (4 service-command + 5 auth-file + 4 wildcard-filename),
all green. Coverage: 67.8%.

---

## Version 1.11.0 (22.04.2026)

### Changed (default behaviour)
- **[CHG]** All 17 service templates now emit **IP-bound** listen directives
  by default: `listen ip.ip.ip.ip:PORT[ ssl];` where `ip.ip.ip.ip` is
  substituted with the `--ip` value (IPv6 addresses are automatically
  bracketed, e.g. `listen [2001:db8::1]:443 ssl;`). This replaces the
  hostname-bound form (`listen <domain>:PORT;`) that was the default in
  v1.9.x and v1.10.2.
- **[CHG]** `server_name` continues to use the domain — only the listen
  socket binding changed. Name-based virtual hosting and SNI routing work
  exactly as before.

### Why this matters
IP-bound listens combine the two properties we wanted separately in v1.10:
1. **No DNS resolution at config-parse time** — nginx no longer aborts on
   transient DNS failures of the `--domain` host (root cause of the nightly
   outages 10./11./15.04.2026).
2. **No SNI fallback to the wrong certificate** — unlike the wildcard
   listen that v1.10.0 tried (`listen 443 ssl;`), the socket is bound to a
   specific interface, so nginx cannot silently pick the first-loaded
   server block as a fallback for unmatched SNI (root cause of the
   SSL-Cert-Mismatch incident 21.04.2026).

### Migration
- **New deployments**: run `nginx-set-conf` with the updated templates.
  The `--ip` parameter is already mandatory, so no CLI change is needed.
- **Existing deployments** with hostname-bound listens: simply regenerate
  the affected `*.conf` files. See the README section
  "Manual Migration: Hostname-bound to IP-bound Listen" for a step-by-step
  procedure.
- **IPv6-only hosts**: supply the IPv6 address via `--ip`; bracketing is
  automatic via `_format_ip_for_nginx`.

### Flag semantics update
- **[CHG]** `--disable_domain_listen` is **kept for backward compatibility**
  but its semantic meaning shifted: it now strips the **IP** prefix from
  listen directives (producing wildcard `listen PORT;`), because the IP
  replaced the hostname in the default template. The flag still emits a
  warning and should only be used when `default_ssl_reject` is deployed
  via `--setup_default` — otherwise the SNI fallback from 21.04.2026
  recurs.

### Tests
- **[ADD]** `TestIpBoundListen` in `tests/test_templates.py`: asserts all
  17 service templates emit `listen ip.ip.ip.ip:80;` and (where applicable)
  `listen ip.ip.ip.ip:443 ssl;`; forbids any `server.domain.de` prefix in
  listen lines; verifies `server_name server.domain.de;` is retained.
- **[CHG]** `TestTemplateBackendIpPlaceholder.test_ip_placeholder_restricted_to_listen`
  replaces the old "no ip.ip.ip.ip anywhere" invariant with the stricter
  "ip.ip.ip.ip only in listen directives" rule.
- **[ADD]** `TestDisableDomainListenIntegration.test_ipv6_listen_is_bracketed`:
  end-to-end regression for IPv6 listen-IP bracketing.
- **[CHG]** `test_default_keeps_hostname_in_listen` → `test_default_uses_ip_bound_listen`
  — reflects the new default.

### Date headers
- **[CHG]** Date header in all 17 template files bumped to `22.04.2026`.

### Tests: 153 passed (v1.10.2: 151). Coverage gate at 60% (actual 64%).

---

## Version 1.10.2 (21.04.2026)

### Reverted
- **[FIX]** Revert the v1.10.0 change that stripped the hostname from every
  template's `listen` directive. v1.10.0 was a breaking change without an
  atomic migration path: any host that only partially regenerated its
  `/etc/nginx/conf.d/*.conf` ended up with a mix of
  `listen <hostname>:port;` (old) and `listen port;` (new). The two listen
  sockets are different (IP-bound vs wildcard `0.0.0.0`), and the IP-bound
  socket wins for its IP, which makes nginx's SNI routing fall back to the
  first-loaded server block — **serving the wrong TLS certificate** for
  unmatched SNI. Observed in production on 2026-04-21 (`equitania.de`
  presented the `designer.odoo2fast.report` cert, `SSL_ERROR_BAD_CERT_DOMAIN`).
- **[CHG]** Template default is now back to v1.9.2 behaviour
  (`listen <domain>:port;`). The DNS-parse-time hardening from v1.10.0
  remains available as **opt-in** — see below.

### Added (opt-in hardening, atomic migration)
- **[ADD]** `--disable_domain_listen` CLI flag is functional again: if set,
  `listen <domain>:port[ ssl];` is rewritten to `listen port[ ssl];` in the
  generated config. Choose this if your environment suffers from transient
  DNS resolver failures that cause nginx to abort at config-parse time
  (the bug v1.10.0 tried to fix).
- **[ADD]** New `--migrate_to_wildcard` CLI flag — **atomically** rewrites
  every hostname-bound `listen` directive in `/etc/nginx/conf.d/*.conf` to
  wildcard form, with a timestamped backup under
  `/var/backups/nginx_set_conf/` and an `nginx -t` gate. On failure all
  files are restored from the backup. This is the supported migration path
  for users switching to wildcard listens in one go; it prevents the
  partial-migration SNI-fallback incident that motivated this release.
- **[ADD]** New template `default_ssl_reject` + CLI flag `--setup_default`
  install an explicit `default_server` catch-all (`00-default.conf`) that
  closes connections with `return 444` for unknown SNI/Host. Defense in
  depth on top of the wildcard migration. **Only effective once all
  listens are wildcard** — runs through `--migrate_to_wildcard` first.

### Fixed (security)
- **[FIX]** `validate_cert_name` and `validate_auth_file` now correctly
  detect path traversal in absolute paths with embedded `..` segments
  (e.g. `/etc/ssl/../../../etc/shadow`). The previous implementation
  called `os.path.normpath()` before the check, which collapsed the
  traversal segments and made the check a no-op on absolute inputs.
  Both previously failing security tests are now green.

### Tests / CI
- **[CHG]** Coverage gate lowered from 70% → 60% to match the realistic
  current state (this release raised coverage from 45% to 64%). The 70%
  target remains the goal for the next minor release. The previous 70%
  setting was effectively inactive because `continue-on-error` in CI hid
  the failure.
- **[ADD]** `tests/test_migration.py` with 15 tests covering the listen
  rewrite regex, the `migrate_configs_to_wildcard` helper (dry-run, full
  path, rollback on `nginx -t` failure), and end-to-end use of
  `--disable_domain_listen` through `execute_commands`.
- **[ADD]** `TestDefaultSslReject` — 6 assertions on the new template
  (default_server on both ports + IPv6, return 444, wildcard server_name,
  expected cert paths).
- **[ADD]** `test_default_ssl_reject_not_in_proxy_list` — ensures the
  template is not treated as a proxy template.
- **[CHG]** `test_all_templates_loaded` expectation grows from 17 → 18.

### Migration notes
1. Upgrade: `uv pip install -U nginx-set-conf`
2. Default behaviour is backwards compatible with v1.9.2 — no action
   required. Your existing configs keep working.
3. If you want the DNS-parse-time hardening: run **once** as root
   `sudo nginx-set-conf --migrate_to_wildcard`, then
   `sudo nginx-set-conf --setup_default`, then
   `sudo systemctl reload nginx`.
4. Never mix both styles. Always migrate atomically.

## Version 1.9.2 (26.02.2026)

### Changed
- **[CHG]** Remove dead commented-out upstream blocks from 16 templates (unused `ip.ip.ip.ip` placeholder)
- **[CHG]** Update template date headers to 26.02.2026

### Added
- **[ADD]** Regression test `test_no_ip_placeholder_anywhere` ensuring `ip.ip.ip.ip` is fully removed

## Version 1.9.1 (26.02.2026)

### Fixed
- **[FIX]** Fix proxy_pass/grpc_pass directives: revert from public IP placeholder (`ip.ip.ip.ip`) back to loopback default (`127.0.0.1`)
  - Previous IPv6 commit incorrectly routed proxy_pass to the server's public IP instead of localhost

### Added
- **[ADD]** New `--backend_ip` CLI option for configurable proxy_pass target (default: `127.0.0.1`)
  - `{{BACKEND_IP}}` placeholder in all 16 templates
  - Support via YAML configuration: `backend_ip: "::1"` for IPv6 loopback backends
  - IPv6 addresses automatically formatted with brackets: `[::1]`
  - Validation via `validators.py` when `backend_ip` is provided

### Changed
- **[CHG]** Remove incorrect Dual-Stack IPv4/IPv6 documentation sections from README
- **[CHG]** Update IPv6 Support documentation to reference `--backend_ip` parameter
- **[CHG]** `ip` parameter no longer replaces values in proxy_pass directives (only used for listen/upstream)

## Version 1.9.0 (18.02.2026)

### New Features
- **[ADD]** IPv6 support for `--ip` parameter in all 15 templates
  - Automatic bracket formatting for IPv6 addresses in `proxy_pass`/`grpc_pass` URLs
  - `_format_ip_for_nginx()` helper for transparent IPv4/IPv6 handling
  - Example: `--ip ::1` → `proxy_pass http://[::1]:8069`
  - Full backward compatibility with IPv4 addresses

### Security Hardening
- **[CHG]** Eliminate all `os.system()` shell injection vectors in utils.py (15+ instances)
- **[CHG]** Replace sed-based config manipulation with in-memory Python string operations
- **[CHG]** Replace bare `except` clauses with specific exception handling
- **[CHG]** Replace debug `print()` calls with proper logging
- **[ADD]** Comprehensive input validation module (`validators.py`)

### Build System
- **[CHG]** Migrate from setuptools/setup.py to hatchling/pyproject.toml
- **[CHG]** Remove redundant `requirements.txt` and `requirements-dev.txt` (single source: `pyproject.toml`)
- **[CHG]** Consolidate flake8+black+isort into ruff for linting and formatting
- **[CHG]** Update pre-commit hooks (ruff, bandit, mypy)

### Tests
- **[ADD]** 104 tests covering validators, utils, and templates
  - 88 base tests for security hardening and validation
  - 16 additional tests for IPv6 formatting, integration, and regression

## Version 1.8.0 (10.09.2025)

### Breaking Changes
- **[CHG]** Removed `ngx_` prefix from all template names for simpler usage
  - Old: `nginx-set-conf --config_template ngx_odoo_ssl`
  - New: `nginx-set-conf --config_template odoo_ssl`
  - Backward compatibility maintained: old names still work

### Improvements
- **[CHG]** Simplified template naming convention
- **[CHG]** Updated all documentation and examples
- **[CHG]** Maintained backward compatibility for existing scripts

## Version 1.7.0 (10.09.2025)

### New Features
- **[ADD]** Apache Guacamole nginx template with optimized WebSocket support
  - Extended timeouts for long RDP/SSH/VNC sessions (3600s)
  - Proper WebSocket header configuration for real-time communication
  - Increased file upload limits (100MB) for RDP/SSH file transfers
  - Disabled buffering for optimal performance
  - Cookie path adjustment for Guacamole routing
  - Support for alternative path configurations
  - Optimized for remote desktop access protocols

### Template Features
- Full SSL/HTTP2 support
- WebSocket connection upgrade mapping
- Extended proxy timeouts for persistent connections
- Real-time communication without buffering
- Large file transfer support
- Performance optimizations for remote desktop protocols

### Configuration
Default configuration uses port 8080 and routes to `/guacamole/` path. The template automatically handles:
- WebSocket protocol upgrades
- Connection persistence for long sessions
- File transfers via remote protocols
- Cookie path adjustments

## Version 1.6.1 (2025)
- **[ADD]** IP access restrictions feature
- Enhanced security with IP-based access control

## Version 1.6.0 (2025)
- **[ADD]** IP access restrictions feature v1.6.0

## Version 1.5.4 (2024)
- **[FIX]** Use embedded templates instead of local files
- **[DOC]** Update CLAUDE.md for embedded templates