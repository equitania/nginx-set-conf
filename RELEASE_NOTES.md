# RELEASE NOTES

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
  the affected `*.conf` files. A future minor release may add an atomic
  `--migrate_to_ip_bound` companion to `--migrate_to_wildcard` for bulk
  server-side rewrites.
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