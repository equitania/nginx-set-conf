# External Integrations

**Analysis Date:** 2026-05-28

## Target System: nginx

**Role:** Primary output consumer — the tool generates and deploys nginx config files.

**Version assumption:** nginx 1.24.1 (embedded `NGINX_CONF_TEMPLATE` header in `nginx_set_conf/config_verification.py:17`)

**Config directories read/written:**
- `/etc/nginx/conf.d/` — domain config files written as `<domain>.conf` (`utils.py:731`)
- `/etc/nginx/conf.d/00-default.conf` — default catch-all written by `setup_default_server()` (`utils.py:456`)
- `/etc/nginx/nginx.conf` — verified/synced by `ConfigVerification` (`config_verification.py:132`)
- `/etc/nginx/nginxconfig.io/general.conf` — verified/synced (`config_verification.py:133`)
- `/etc/nginx/nginxconfig.io/security.conf` — verified/synced (`config_verification.py:134`)
- `/etc/nginx/ssl/` — self-signed default cert stored here (`utils.py:428`)

**nginx service control (via `subprocess` + `systemctl`):**

| Call | Trigger | File:line |
|------|---------|-----------|
| `systemctl stop nginx.service` | Before certbot standalone run | `utils.py:284` |
| `nginx -t` | After `migrate_configs_to_wildcard()` to validate | `utils.py:414` |
| `systemctl reload nginx.service` | After `--verify_config` / `--sync_config` success | `nginx_set_conf.py:278,291` |
| `systemctl start nginx.service` | After cert creation (if nginx was stopped) | `nginx_set_conf.py:344` |
| `systemctl restart nginx.service` | After `--setup_default` | `nginx_set_conf.py:453` |
| `systemctl status nginx.service` | Status check post-restart | `nginx_set_conf.py:455` |

## SSL Certificate Handling

**Let's Encrypt / certbot:**
- Tool calls `certbot certonly --standalone --agree-tos --register-unsafely-without-email -d <domain>` via subprocess (`utils.py:285-296`)
- Certificate presence checked at `/etc/letsencrypt/live/<cert_name>/fullchain.pem` and `/etc/letsencrypt/live/<cert_name>/privkey.pem` (`utils.py:279-281`)
- nginx is stopped before certbot runs (port 80 required for standalone challenge)
- Template placeholders for LE certs: `zertifikat.crt` / `zertifikat.key` → resolved to `/etc/letsencrypt/live/<cert_name>/fullchain.pem` and `privkey.pem`

**Self-signed / purchased certificates:**
- Paths supplied via `--cert_name` / `--cert_key` flags; templates use `zertifikat.crt` / `zertifikat.key` placeholders
- Default reject cert generated with `openssl req -x509 ...` (`utils.py:476-496`); stored at `/etc/nginx/ssl/default.crt` and `/etc/nginx/ssl/default.key`

**openssl:** Called via subprocess for self-signed cert generation only (`utils.py:476`).

## File System Touchpoints

| Path | Operation | Purpose |
|------|-----------|---------|
| `/etc/nginx/conf.d/<domain>.conf` | Write | Generated reverse-proxy config |
| `/etc/nginx/conf.d/00-default.conf` | Write | Default SSL-reject catch-all |
| `/etc/nginx/nginx.conf` | Read + optional Write | Main nginx config verify/sync |
| `/etc/nginx/nginxconfig.io/*.conf` | Read + optional Write | Shared nginx settings verify/sync |
| `/etc/nginx/ssl/` | Write | Self-signed default cert directory |
| `/etc/letsencrypt/live/<name>/` | Read (existence check) | LE cert detection |
| `/var/cache/nginx/<service>_<domain>/` | Create (mkdir) | Per-domain proxy cache |
| `/var/backups/nginx_set_conf/` | Write | Timestamped config backups (mode 0o700) |
| YAML config path (user-supplied) | Read | Input configuration |

## Docker (Assumed Backend)

The tool does **not** call Docker APIs or CLI directly. It assumes Docker containers are already running on the host. Backend services are addressed via `proxy_pass http://<backend_ip>:<port>` inside generated configs. Default backend IP is `127.0.0.1` (loopback), consistent with Docker port-binding to loopback for UFW security (`utils.py:671`).

A warning is logged if a public IP is used as backend (`utils.py:206-223`).

## Services the Generated Configs Reverse-Proxy

All templates registered in `nginx_set_conf/templates/all_templates.py`:

| Template key | Service | Notes |
|---|---|---|
| `odoo_ssl` | Odoo (HTTPS) | HTTP + WebSocket longpolling via `{{POLL_PORT}}`; `map $http_upgrade` block |
| `odoo_http` | Odoo (HTTP only) | Plain HTTP reverse proxy |
| `flowise` | Flowise (AI workflow UI) | Standard HTTPS proxy |
| `qdrant` | Qdrant vector DB | HTTP `{{PORT}}` + gRPC `{{GRPC_PORT}}` (grpc_pass) |
| `n8n` | n8n workflow automation | Standard HTTPS proxy |
| `mailpit` | Mailpit SMTP tester | Standard HTTPS proxy |
| `pgadmin` | pgAdmin web UI | Standard HTTPS proxy |
| `nextcloud` | Nextcloud | Standard HTTPS proxy |
| `portainer` | Portainer Docker UI | Standard HTTPS proxy |
| `guacamole` | Apache Guacamole (remote desktop) | Standard HTTPS proxy |
| `kasm` | Kasm Workspaces | Standard HTTPS proxy |
| `supabase` | Supabase backend | Standard HTTPS proxy |
| `pwa` | Generic PWA | Standard HTTPS proxy |
| `fast_report` | FastReport API | Standard HTTPS proxy |
| `code_server` | VS Code Server | Standard HTTPS proxy |
| `redirect` | HTTP redirect | Redirects to `{{REDIRECT_DOMAIN}}` |
| `redirect_ssl` | HTTPS redirect + LE cert | Redirects + triggers cert creation for `redirect_domain` |
| `default_ssl_reject` | Catch-all reject | Returns 444 for unmatched SNI; no cache/rate-limit zones |

## Network Calls

The tool itself makes **no HTTP/API calls**. All network activity is indirect:
- certbot reaches Let's Encrypt ACME servers during cert issuance (port 80, standalone)
- nginx service reloads are local systemctl calls

## Subprocess Summary

All external programs called via `_run_command()` (`utils.py:154`) using `subprocess.run(..., capture_output=True)`:

| Program | Purpose |
|---------|---------|
| `systemctl` | nginx service lifecycle (stop/start/reload/restart/status) |
| `certbot` | Let's Encrypt certificate issuance |
| `nginx` | Config validation (`nginx -t`) |
| `openssl` | Self-signed default cert generation |
| `chown` / `chmod` | Set ownership/permissions on cache dir and key file |

## Authentication (Generated Configs)

Optional htpasswd basic auth injected into configs via `--auth_file` flag. Tool writes `auth_basic` and `auth_basic_user_file <path>` directives after `#authentication` marker in templates. The htpasswd file itself is managed externally.

---

*Integration audit: 2026-05-28*
