# nginx-set-conf

[🇬🇧 English Version](#english-version) | [🇩🇪 Deutsche Version](#deutsche-version)

---

## 🇬🇧 English Version

A simple Python library that helps you create nginx configurations for different Docker-based applications with nginx as reverse proxy, including configuration verification features.

### Features

- **Template-based configuration**: Support for 15+ pre-built templates
- **SSL/TLS support**: Automatic Let's Encrypt integration
- **IPv6 support**: `--ip` and `--backend_ip` parameters accept both IPv4 and IPv6 addresses with automatic bracket formatting
- **Backend IP configuration**: Optional `--backend_ip` parameter for non-localhost backends (default: 127.0.0.1)
- **IP access restrictions**: Optional IP whitelist/blacklist functionality
- **Input validation**: Comprehensive validation for IP, domain, port, certificate, and template parameters
- **Security hardening**: Shell injection prevention, specific exception handling, structured logging
- **Configuration verification**: Check consistency between local and server files
- **Configuration verification**: Check if required nginx files exist
- **Backup functionality**: Automatic backup of server configurations
- **Dry run mode**: Test configurations without applying changes
- **PDF MIME-Type optimization**: Enhanced PDF handling for Odoo applications
- **IP-bound listen directives** (v1.11.0+): templates bind `listen` to the `--ip` value, which avoids both DNS-parse-time failures (hostname-bound listens) and SNI fallback leaks (wildcard listens)
- **Intranet support**: Optional wildcard listen via `--disable_domain_listen` for internal networks without a stable public IP

### Installation

#### Requirements

- Python (>= 3.10)
- click (>= 8.2.1)
- PyYAML (>= 6.0.2)

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install nginx-set-conf:

```bash
pip install nginx-set-conf

# Or using uv
uv pip install nginx-set-conf
```

### Usage

#### Basic Usage

```bash
$ nginx-set-conf --help
```

#### Supported Templates

- `code_server` - Code-server with SSL
- `default_ssl_reject` - Default `server_name _` catch-all that closes unknown SNI (installed via `--setup_default`)
- `fast_report` - FastReport with SSL
- `flowise` - Flowise AI with SSL/HTTP2
- `guacamole` - Apache Guacamole with SSL/HTTP2 and WebSocket
- `kasm` - Kasm Workspaces with SSL/HTTP2
- `mailpit` - Mailpit with SSL/HTTP2
- `n8n` - n8n with SSL/HTTP2
- `nextcloud` - NextCloud with SSL
- `odoo_http` - Odoo HTTP only
- `odoo_ssl` - Odoo with SSL
- `patchmon` - Patch monitoring with SSL/HTTP2
- `pgadmin` - pgAdmin4 with SSL
- `portainer` - Portainer with SSL
- `pwa` - Progressive Web App with SSL
- `qdrant` - Qdrant vector database with SSL/HTTP2 and gRPC
- `redirect` - Domain redirect without SSL
- `redirect_ssl` - Domain redirect with SSL
- `static_ssl` - Static website / file-download hosting with SSL/HTTP2 (serves files from a local document root, no upstream backend; configure the root with `--root_path`, default `/opt/www`)
- `supabase` - Supabase database server with SSL/HTTP2

#### Configuration Management Options

- `--verify_config` - Check consistency between local and server config files
- `--create_dirs` - Create missing nginx configuration directories
- `--backup_config` - Create backup of current server configuration
- `--migrate_to_wildcard` - Atomically rewrite hostname-bound listen directives (see below)
- `--setup_default` - Install default_server catch-all for unknown SNI (see below)

### IP-bound Listen Directives (v1.11.0)

**Default behaviour** (since v1.11.0): templates generate
`listen <ip>:80;` / `listen <ip>:443 ssl;` where `<ip>` is the value
passed via `--ip`. IPv6 addresses are automatically wrapped in brackets
(`listen [2001:db8::1]:443 ssl;`). `server_name` still uses the domain
for SNI routing — only the listen socket binding changed.

**Why this is the default**:
1. **No DNS resolution at config-parse time** — nginx does not abort on
   transient DNS failures of the `--domain` host. This was the root cause
   of v1.9.x/v1.10.2 nightly outages.
2. **No SNI fallback to the wrong certificate** — because the socket is
   bound to a specific interface, nginx cannot silently pick the
   first-loaded server block as a fallback for unmatched SNI. This was
   the root cause of the SSL-Cert-Mismatch incident on 21.04.2026.

#### Optional: wildcard listen via `--disable_domain_listen`

For intranet systems without a stable public IP, or when you explicitly
want a wildcard listen socket (`0.0.0.0:443`), set the flag on the
affected invocation:

```bash
nginx-set-conf --config_template odoo_ssl --domain ... --disable_domain_listen
```

**Warning**: wildcard listens without an explicit `default_server` leak
certificates via SNI fallback. Always deploy `default_ssl_reject` first
via `--setup_default` when using wildcards.

#### Optional: bulk migration from old hostname-bound installs

Installations still running the v1.9.x / v1.10.2 hostname-bound default
(`listen <domain>:443 ssl;`) can be migrated to wildcard form atomically
(regenerating with v1.11.0 templates is the preferred path — this
migration tool is for bulk server-side rewrites):

```bash
# 1. Backup the whole /etc/nginx first (optional but recommended)
sudo nginx-set-conf --backup_config

# 2. Atomic rewrite of every hostname-bound listen directive in /etc/nginx/conf.d
#    Creates a timestamped backup, runs `nginx -t`, rolls back on failure.
sudo nginx-set-conf --migrate_to_wildcard

# 3. Install the default_server catch-all (needs wildcard listens to be effective)
sudo nginx-set-conf --setup_default

# 4. Reload
sudo systemctl reload nginx
```

**Never mix styles.** A half-migrated host — some configs on
`listen <domain>:443 ssl;`, others on `listen 443 ssl;` — causes
nginx's SNI routing to serve the wrong TLS certificate for unmatched
names. This is exactly the production incident that motivated v1.10.2.
Either migrate atomically, or stay on the v1.11.0 IP-bound default.

## Manual Migration: Hostname-bound to IP-bound Listen

**Context**: Starting from v1.11.0, all templates use IP-bound listen directives
(`listen <ip>:443 ssl;`) instead of the old hostname-bound form
(`listen <domain>:443 ssl;`). If you have servers still running configs generated
with v1.9.x or v1.10.2, this section describes the safe migration path.

**Why no `--migrate_to_ip_bound` flag?** An atomic bulk rewrite of listen
directives across all server configs carries the same partial-migration risk
that caused the SNI-fallback incident on 21.04.2026 (see v1.10.2 release notes).
The implementation is deferred to v2. The conceptual analog for the wildcard
migration (`--migrate_to_wildcard`) exists, but IP-bound migration requires
knowing each vhost's `--ip` value at rewrite time — that information is not
stored in the generated config file and cannot be reliably extracted.

**Procedure: manual per-vhost regeneration** (the safe path):

```bash
# 1. Identify which configs still use hostname-bound listen directives
grep -l "listen [a-z].*:" /etc/nginx/conf.d/*.conf

# 2. For each affected file, regenerate it with the same parameters you
#    originally used, now adding or confirming the --ip argument.
#    Example — regenerate an Odoo vhost:
sudo nginx-set-conf \
  --config_template odoo_ssl \
  --ip 1.2.3.4 \
  --domain www.example.com \
  --port 8069 \
  --cert_name www.example.com \
  --pollport 8072

# 3. After all vhosts have been regenerated, validate the configuration
sudo nginx -t

# 4. If validation passes, reload nginx
sudo systemctl reload nginx
```

**Key points**:

- Regenerate configs one at a time, not all at once. After each regeneration
  run `nginx -t` to catch any issue early.
- The `--ip` parameter must match the actual IP address of the server
  interface you want nginx to bind to. Do not use the domain name as the IP.
- `server_name` in the generated config still uses the domain — only the
  listen socket binding changes. Name-based virtual hosting and SNI routing
  continue to work as before.
- If you have multiple vhosts on the same server, they all use the same `--ip`
  value (the server's public IP). Regenerate them all before reloading.
- This is a safe operation: regenerating a config replaces only the specific
  `*.conf` file. The running nginx keeps the old config until you reload.

**Tip**: Check your deployment scripts or Ansible playbooks for the original
parameter values (`--domain`, `--port`, `--cert_name`, etc.) so you can
reproduce the exact invocation for each vhost.

### Examples

#### Basic Configuration

```bash
# Using configuration file
nginx-set-conf --config_path server_config

# Direct configuration
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --pollport 8072

# Custom target path
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --target_path /tmp/nginx-test

# Dry run mode
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --dry_run

# With IP access restrictions
nginx-set-conf --config_template flowise --ip 192.168.1.10 --domain secure-flowise.example.com --port 3000 --cert_name secure-flowise.example.com --allowed_ips "192.168.1.0/24,10.0.0.50,203.0.113.100"

# For intranet systems without domain prefix in listen directives
nginx-set-conf --config_template odoo_ssl --ip 192.168.1.100 --domain dev01-a.intra.company.local --port 8069 --cert_name dev01-a.intra.company.local --disable_domain_listen
```

#### Template Preview

```bash
# Show template configuration
nginx-set-conf --config_template odoo_ssl --show_template

# Show Qdrant template
nginx-set-conf --config_template qdrant --show_template
```

#### Advanced Examples

```bash
# Qdrant with gRPC support
nginx-set-conf --config_template qdrant --ip 1.2.3.4 --domain vector.example.com --port 6333 --grpcport 6334 --cert_name vector.example.com

# Flowise AI server
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com

# Supabase database server
nginx-set-conf --config_template supabase --ip 1.2.3.4 --domain supabase.example.com --port 8000 --cert_name supabase.example.com

# Static website / file-download hosting (no --port; serves files from --root_path)
nginx-set-conf --config_template static_ssl --ip 1.2.3.4 --domain dl.example.com --cert_name dl.example.com --root_path /opt/www
```

#### IPv6 Support

The `--ip` and `--backend_ip` parameters accept both IPv4 and IPv6 addresses. IPv6 addresses are automatically formatted with brackets in the generated nginx configuration:

```bash
# IPv6 loopback as backend
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --backend_ip ::1

# Full IPv6 backend address
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com --backend_ip 2001:db8::1
```

Generated nginx configuration with IPv6:

```nginx
proxy_pass http://[::1]:8069;
```

#### Backend IP Configuration

The `backend_ip` parameter controls the IP address used in `proxy_pass` directives. By default, it is `127.0.0.1` (localhost), which is correct for Docker containers binding to loopback.

```bash
# Default: proxy_pass uses 127.0.0.1 (no --backend_ip needed)
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com

# IPv6 loopback backend
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --backend_ip ::1

# Remote backend
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com --backend_ip 192.168.1.50
```

YAML configuration:

```yaml
# Default: no backend_ip needed (uses 127.0.0.1)
My Odoo Server:
  config_template: odoo_ssl
  ip: 1.2.3.4
  domain: app.example.com
  port: 11000
  cert_name: app.example.com

# IPv6 loopback backend
My IPv6 Service:
  config_template: flowise
  ip: 1.2.3.4
  domain: app.example.com
  port: 3000
  cert_name: app.example.com
  backend_ip: "::1"
```

> **Note:** The `ip` parameter is the public server IP (used in commented upstream blocks). The `backend_ip` parameter is the address where the application actually listens (used in `proxy_pass`).

### Configuration Verification

#### 1. Configuration File Check (`--verify_config`)

Check if required nginx configuration files exist on the server:

```bash
nginx-set-conf --verify_config
```

**Checked Files:**
- `/etc/nginx/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf`

**Output:**
- ✓ EXISTS: File is present on the server
- ✗ MISSING: File not found
- Shows file path and size for existing files

#### 2. Create Missing Directories (`--create_dirs`)

Create missing nginx configuration directories if needed:

```bash
nginx-set-conf --create_dirs
```

**What it does:**
- Checks for missing files
- Creates `/etc/nginx/nginxconfig.io/` directory if missing
- Useful after fresh nginx installation

**Security Features:**
- Confirmation before overwriting files
- Automatic directory creation
- Error handling for access problems

#### 3. Configuration Backup (`--backup_config`)

Create automatic backups of current server configuration:

```bash
nginx-set-conf --backup_config
```

**Backup Features:**
- Timestamp-based backup folders: `/tmp/nginx_backup/nginx_config_backup_YYYYMMDD_HHMMSS`
- Complete backup of `/etc/nginx/nginx.conf`
- Recursive backup of `nginxconfig.io/` directory
- Logging of all backup operations

### Intranet Configuration (disable_domain_listen)

For intranet systems that need a wildcard listen socket instead of the
v1.11.0 default IP-bound form:

#### When to Use

Switch to wildcard listens when:
- The host does not have a stable public IP but must serve a specific
  `server_name` (unusual — prefer IP-bound with the actual intranet IP)
- You are explicitly deploying `default_ssl_reject` via `--setup_default`
  and want every vhost on `0.0.0.0`

Variants:
- **Default (v1.11.0)**: `listen 192.168.1.100:443 ssl;` (IP-bound)
- **Wildcard (opt-in)**: `listen 443 ssl;`

#### Configuration Example

```yaml
intranet-odoo:
  config_template: odoo_ssl
  ip: 192.168.1.100
  domain: dev01-a.intra.company.local
  port: 8069
  cert_name: dev01-a.intra.company.local
  pollport: 8072
  disable_domain_listen: true  # Strip the IP prefix (wildcard listen)
```

#### Command Line Usage

```bash
nginx-set-conf --config_template odoo_ssl \
  --ip 192.168.1.100 \
  --domain dev01-a.intra.company.local \
  --port 8069 \
  --cert_name dev01-a.intra.company.local \
  --disable_domain_listen
```

#### Effect on Configuration

**Without `disable_domain_listen` (v1.11.0 default, IP-bound):**
```nginx
server {
    listen 192.168.1.100:80;
    server_name dev01-a.intra.company.local;
}

server {
    listen 192.168.1.100:443 ssl;
    server_name dev01-a.intra.company.local;
}
```

**With `disable_domain_listen` (wildcard):**
```nginx
server {
    listen 80;
    server_name dev01-a.intra.company.local;
}

server {
    listen 443 ssl;
    server_name dev01-a.intra.company.local;
}
```

**Warning**: wildcard listens without `default_ssl_reject` leak
certificates via SNI fallback. Deploy `--setup_default` first.

## HTTP/3 / QUIC (--enable_http3)

HTTP/3 opt-in support is available since v1.14.0. The `--enable_http3` flag adds QUIC + HTTP/3
listen directives to 14 browser-facing SSL templates. By default the flag is **off** — existing
operators see no change until they explicitly set it. When HTTP/3 is unavailable (wrong nginx
version, firewall closed), browsers automatically fall back to HTTP/2 over TCP and the feature
degrades silently.

### Prerequisites

Before enabling HTTP/3 on any vhost, verify all five of the following:

1. **nginx >= 1.25.0** — QUIC/HTTP/3 was stabilised in nginx 1.25.0 (May 2023). Upgrade paths:
   Debian bookworm-backports, Ubuntu 24.04+, RHEL 9.4+. The tool enforces this requirement:
   it runs `nginx -v` before writing any HTTP/3-emitting config and aborts with a clear
   remediation message if the installed nginx is older than 1.25.0.

2. **Open UDP port 443 in the host firewall**

   > **WARNING — Firewall action required:** HTTP/3 uses UDP/443 in addition to TCP/443. You
   > must open UDP port 443 in your host firewall (`ufw allow 443/udp` or equivalent) separately
   > from TCP/443. Without this, QUIC connections are silently dropped and browsers fall back to
   > HTTP/2 — the Alt-Svc header is effectively dead.

   Since v1.15.0 the tool performs a best-effort advisory check when `--enable_http3` is set:
   if `ufw` is active but carries no inbound rule for UDP/443, it prints a yellow warning (it
   does **not** abort — the firewall may be managed externally, e.g. a cloud security group, so
   the check cannot be authoritative). Only `ufw` is inspected; on other firewalls the check is
   skipped with a short note and you must verify UDP/443 yourself.

- **TLS 1.3 for QUIC** — QUIC negotiates TLS 1.3 at the protocol level, so **no** server-scope `ssl_protocols` directive is injected. The shared TCP/443 (HTTP/2) listener keeps its http-scope `ssl_protocols TLSv1.2 TLSv1.3;`, preserving TLSv1.2 fallback (ROADMAP SC-1)
   block. Clients that cannot negotiate TLS 1.3 fall back to the TCP/HTTP/2 block which keeps
   TLS 1.2 + 1.3 support. No clients are denied — the fallback is seamless.

4. **ECDSA certificate (recommended)** — RSA certificates work, but ECDSA certificates produce
   smaller TLS handshakes which improve QUIC connection setup latency. Use your CA's ECDSA
   endpoint if available (e.g. `certbot --key-type ecdsa`).

5. **Explicit opt-in** — the flag must be set on every invocation; no existing operator sees any
   change without adding `--enable_http3` to their command or `enable_http3: true` to their
   YAML config.

### Usage

```bash
# CLI flag
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain erp.example.com \
  --port 8069 --cert_name erp.example.com --enable_http3
```

YAML configuration:

```yaml
My Odoo Server:
  config_template: odoo_ssl
  ip: 1.2.3.4
  domain: erp.example.com
  port: 8069
  cert_name: erp.example.com
  enable_http3: true
```

Both the CLI flag and the YAML key produce identical output.

### Supported templates

The following 14 browser-facing templates support `--enable_http3`:

| Template | Rationale |
|----------|-----------|
| `odoo_ssl` | ERP web UI, longpoll, mobile workforce |
| `flowise` | AI workflow UI, streaming responses |
| `n8n` | Workflow automation web UI |
| `nextcloud` | File sync clients + browser UI, large transfers |
| `guacamole` | Browser RDP/VNC — latency-sensitive |
| `kasm` | Browser VDI — latency-sensitive |
| `pgadmin` | Postgres admin UI (low traffic, harmless inclusion) |
| `portainer` | Docker management UI |
| `pwa` | Generic PWA shell (HTTP/3 is ideal for PWAs) |
| `code_server` | VSCode in browser, developer UX |
| `supabase` | Backend-as-a-service, mixed API + browser |
| `patchmon` | Patch-monitoring web UI |
| `static_ssl` | Static sites / file downloads — HTTP/3 lowers latency |
| `qdrant` | REST port only — gRPC port stays HTTP/2 |

### Excluded templates

The following 6 templates do not support `--enable_http3`. The tool rejects them with a clear
error message:

- `fast_report` — server-to-server PDF API, no browser traffic
- `mailpit` — dev SMTP test tool, internal-only
- `redirect` — HTTP-only, no TLS, no HTTP/3
- `redirect_ssl` — trivial 301 redirect, UDP/QUIC overhead not worth it
- `default_ssl_reject` — SNI catch-all that returns 444, no useful response body
- `odoo_http` — HTTP-only, no TLS

### Catch-all requirement

Any host running at least one HTTP/3-enabled vhost must also have the QUIC catch-all deployed.
Run `--setup_default` to install it:

```bash
sudo nginx-set-conf --setup_default
```

This extends the existing TCP SNI catch-all (`default_ssl_reject`) with a QUIC catch-all that
returns 444 for unknown SNI on UDP/443 — mirroring the lesson from the v1.10.0 incident for the
UDP surface. See [IP-bound Listen Directives](#ip-bound-listen-directives-v1110) for context on
why the catch-all matters.

### Manual migration (no bulk flag)

A bulk `--migrate_to_http3` flag is **not available** in this version. It is planned for v2
(`PROTO-V2-01`). To add HTTP/3 to an existing vhost, regenerate it individually:

```bash
sudo nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain erp.example.com \
  --port 8069 --cert_name erp.example.com --enable_http3
```

Regenerate each vhost one at a time, running `nginx -t` after each to catch issues early.

### IP Access Restrictions

nginx-set-conf supports optional IP-based access control to restrict access to your applications to specific IP addresses or CIDR blocks.

#### CLI Usage

```bash
# Restrict access to specific IPs
nginx-set-conf --config_template flowise \
  --ip 192.168.1.10 --domain secure.example.com --port 3000 \
  --cert_name secure.example.com \
  --allowed_ips "192.168.1.0/24,10.0.0.50,203.0.113.100"

# Multiple IP formats supported
nginx-set-conf --config_template odoo_ssl \
  --ip 10.0.0.5 --domain erp.company.com --port 8069 \
  --cert_name erp.company.com --pollport 8072 \
  --allowed_ips "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
```

#### YAML Configuration

```yaml
# Example with IP restrictions
Secure Flowise:
  config_template: flowise
  ip: 192.168.1.10
  domain: secure-flowise.example.com
  port: 3000
  cert_name: secure-flowise.example.com
  allowed_ips: "192.168.1.0/24,10.0.0.50,203.0.113.100"

# Mixed authentication (IP + htaccess)
Odoo Production:
  config_template: odoo_ssl
  ip: 10.0.0.5
  domain: erp.company.com
  port: 8069
  cert_name: erp.company.com
  pollport: 8072
  auth_file: /etc/nginx/.htpasswd
  allowed_ips: "192.168.0.0/16,10.0.0.0/8"
```

#### Generated nginx Configuration

When `allowed_ips` is specified, the following directives are automatically added to your nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name secure.example.com;
    
    # IP restrictions
    allow 192.168.1.0/24;
    allow 10.0.0.50;
    allow 203.0.113.100;
    deny all;
    
    # ... rest of configuration
}
```

#### Supported IP Formats

- **Single IP**: `192.168.1.100`
- **CIDR notation**: `192.168.1.0/24`, `10.0.0.0/8`
- **IPv6**: `2001:db8::/32` (if supported by nginx)
- **Multiple entries**: Comma-separated list

#### Security Notes

- IP restrictions are applied at the server block level
- Restrictions work with both SSL and non-SSL templates
- Compatible with existing authentication (`auth_file`)
- Applied before location-specific rules
- Use `deny all` as final rule for security

### Practical Usage Scenarios

#### Scenario 1: Consistency Check Before Deployment

```bash
# Check before deployment
nginx-set-conf --verify_config

# If inconsistencies found: Create backup
nginx-set-conf --backup_config

# If directories missing, create them
nginx-set-conf --create_dirs
```

#### Scenario 2: Server Setup Adoption

```bash
# Backup current server configuration
nginx-set-conf --backup_config

# Create missing directories if needed
nginx-set-conf --create_dirs

# Verify result
nginx-set-conf --verify_config
```

#### Scenario 3: Fresh nginx Installation

```bash
# Check if all required files exist
nginx-set-conf --verify_config

# If directories are missing, create them
nginx-set-conf --create_dirs
```

### SSL Certificate Management

#### Create Let's Encrypt Certificate

```bash
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.example.com
```

#### Install certbot on Debian/Ubuntu

```bash
apt-get install certbot
```

#### Create Authentication File

```bash
# Install htpasswd on Debian/Ubuntu
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htaccess/.htpasswd-user USER
```

### Nginx Template Settings

You can download our optimized settings:
- [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)
- [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)

Based on [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)

### Technical Details

#### Hash-based Verification
- SHA256 hashes for precise file comparisons
- Detection of content, size, and modification time
- Robust error handling for access problems

#### Secure Synchronization
- Explicit user confirmation before overwrites
- Automatic directory creation
- Detailed logging information
- Rollback possibility through backup system

#### Flexible Path Configuration
- Customizable local paths (default: `yaml_examples/`)
- Configurable server paths (default: `/etc/nginx/`)
- Support for different nginx installations

### Advanced Usage

#### Combined Commands
```bash
# Backup + Verification in one workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config
```

#### Combining with Other Options
```bash
# Verification with Dry-Run
nginx-set-conf --verify_config --dry_run
```

### Troubleshooting

#### Common Issues

1. **Permission denied**: Ensure user has write permissions for `/etc/nginx/`
2. **Missing directories**: Tool automatically creates missing directories
3. **Backup storage full**: Remove old backups from `/tmp/nginx_backup/`

#### Logging
All operations are logged to:
- Console: INFO level
- File: `nginx_set_conf.log` (with rotation)

### Development & Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=nginx_set_conf
```

The test suite includes 104 tests covering validators, utils, and templates.

### Security Aspects

- **No automatic changes**: All changes require explicit confirmation
- **Backup-first approach**: Backup recommended before configuration changes
- **Granular control**: Individual files can be identified and handled
- **Error handling**: Robust handling of permission and access problems
- **Input validation**: All parameters (IP, domain, port, paths) are validated before use
- **Shell injection prevention**: No `os.system` calls, safe subprocess handling
- **Structured logging**: Consistent logging instead of debug prints

### License

This project is licensed under the terms of the **AGPLv3** license.

---

## 🇩🇪 Deutsche Version

Eine einfache Python-Bibliothek, die bei der Erstellung von nginx-Konfigurationen für verschiedene Docker-basierte Anwendungen mit nginx als Reverse-Proxy hilft, einschließlich erweiterten Konfigurationsverifikations- und Synchronisationsfunktionen.

### Funktionen

- **Template-basierte Konfiguration**: Unterstützung für 15+ vorgefertigte Templates
- **SSL/TLS-Unterstützung**: Automatische Let's Encrypt Integration
- **IPv6-Unterstützung**: `--ip` und `--backend_ip` Parameter akzeptieren sowohl IPv4- als auch IPv6-Adressen mit automatischer Bracket-Formatierung
- **Backend-IP-Konfiguration**: Optionaler `--backend_ip` Parameter für Nicht-Localhost-Backends (Standard: 127.0.0.1)
- **IP-Zugriffsbeschränkungen**: Optionale IP-Whitelist/Blacklist Funktionalität
- **Eingabevalidierung**: Umfassende Validierung für IP, Domain, Port, Zertifikat und Template-Parameter
- **Sicherheitshärtung**: Shell-Injection-Prävention, spezifische Ausnahmebehandlung, strukturiertes Logging
- **Konfigurationsverifikation**: Konsistenzprüfung zwischen lokalen und Server-Dateien
- **Interaktive Synchronisation**: Synchronisation von Konfigurationen zwischen lokal und Server
- **Backup-Funktionalität**: Automatische Sicherung von Server-Konfigurationen
- **Dry-Run-Modus**: Konfigurationen testen ohne Änderungen anzuwenden
- **PDF MIME-Type-Optimierung**: Verbesserte PDF-Behandlung für Odoo-Anwendungen
- **IP-gebundene listen-Direktiven** (v1.11.0+): Templates binden `listen` an den `--ip`-Wert, was sowohl DNS-Parse-Fehler (Hostname-bound) als auch SNI-Fallback-Leaks (Wildcard) vermeidet
- **Intranet-Unterstützung**: Optional Wildcard-Listen via `--disable_domain_listen` für interne Netzwerke ohne stabile öffentliche IP

### Installation

#### Anforderungen

- Python (>= 3.10)
- click (>= 8.2.1)
- PyYAML (>= 6.0.2)

Verwenden Sie den Paketmanager [pip](https://pip.pypa.io/en/stable/) zur Installation von nginx-set-conf:

```bash
pip install nginx-set-conf

# Oder mit uv
uv pip install nginx-set-conf
```

### Verwendung

#### Grundlegende Verwendung

```bash
$ nginx-set-conf --help
```

#### Unterstützte Templates

- `code_server` - Code-Server mit SSL
- `default_ssl_reject` - Default-`server_name _` Catch-all, das unbekannte SNI schließt (Installation via `--setup_default`)
- `fast_report` - FastReport mit SSL
- `flowise` - Flowise AI mit SSL/HTTP2
- `guacamole` - Apache Guacamole mit SSL/HTTP2 und WebSocket
- `kasm` - Kasm Workspaces mit SSL/HTTP2
- `mailpit` - Mailpit mit SSL/HTTP2
- `n8n` - n8n mit SSL/HTTP2
- `nextcloud` - NextCloud mit SSL
- `odoo_http` - Odoo nur HTTP
- `odoo_ssl` - Odoo mit SSL
- `pgadmin` - pgAdmin4 mit SSL
- `portainer` - Portainer mit SSL
- `pwa` - Progressive Web App mit SSL
- `qdrant` - Qdrant Vektordatenbank mit SSL/HTTP2 und gRPC
- `redirect` - Domain-Weiterleitung ohne SSL
- `redirect_ssl` - Domain-Weiterleitung mit SSL
- `supabase` - Supabase Datenbankserver mit SSL/HTTP2

#### Konfigurationsverwaltungsoptionen

- `--verify_config` - Prüfen ob benötigte nginx Konfigurationsdateien existieren
- `--create_dirs` - Fehlende nginx Konfigurationsverzeichnisse erstellen
- `--backup_config` - Backup der aktuellen Server-Konfiguration erstellen
- `--migrate_to_wildcard` - Atomische Umschreibung hostname-gebundener listen-Direktiven (siehe unten)
- `--setup_default` - Default_server-Catch-all für unbekannte SNI installieren (siehe unten)

### IP-gebundene listen-Direktiven (v1.11.0)

**Default-Verhalten** (seit v1.11.0): Templates erzeugen
`listen <ip>:80;` / `listen <ip>:443 ssl;`, wobei `<ip>` der über `--ip`
übergebene Wert ist. IPv6-Adressen werden automatisch in eckige Klammern
gesetzt (`listen [2001:db8::1]:443 ssl;`). Der `server_name` nutzt weiterhin
die Domain für SNI-Routing — geändert wurde ausschließlich das Listen-Binding.

**Warum das der Default ist**:
1. **Keine DNS-Auflösung beim Config-Parse** — nginx bricht nicht mehr bei
   transienten DNS-Fehlern der `--domain` ab. Das war die Ursache der
   nächtlichen Ausfälle in v1.9.x/v1.10.2.
2. **Kein SNI-Fallback auf das falsche Zertifikat** — da der Socket an eine
   spezifische Schnittstelle gebunden ist, kann nginx nicht mehr stillschweigend
   den ersten geladenen server-Block als Fallback für unbekannte SNI wählen.
   Das war die Ursache des SSL-Cert-Mismatch-Incidents am 21.04.2026.

#### Optional: Wildcard-Listen via `--disable_domain_listen`

Für Intranet-Systeme ohne stabile öffentliche IP oder wenn explizit ein
Wildcard-Listen-Socket (`0.0.0.0:443`) gewünscht ist, den Flag pro Aufruf
setzen:

```bash
nginx-set-conf --config_template odoo_ssl --domain ... --disable_domain_listen
```

**Warnung**: Wildcard-Listens ohne expliziten `default_server` liefern
falsche Zertifikate über SNI-Fallback aus. Immer zuerst `default_ssl_reject`
via `--setup_default` deployen.

#### Optional: Bulk-Migration alter hostname-gebundener Installationen

Bestehende Systeme mit dem v1.9.x / v1.10.2 Default
(`listen <domain>:443 ssl;`) lassen sich atomisch auf Wildcard umstellen
(empfohlener Pfad: einfach mit v1.11.0-Templates neu generieren — dieses
Tool ist für Massen-Rewrites serverseitig):

```bash
# 1. Backup von /etc/nginx (optional, aber empfohlen)
sudo nginx-set-conf --backup_config

# 2. Atomische Umschreibung aller hostname-gebundenen listen-Direktiven in
#    /etc/nginx/conf.d — mit Zeitstempel-Backup, nginx -t und Rollback bei Fehler.
sudo nginx-set-conf --migrate_to_wildcard

# 3. Default_server-Catch-all installieren (funktioniert nur auf Wildcard-Listens)
sudo nginx-set-conf --setup_default

# 4. Reload
sudo systemctl reload nginx
```

**Nicht mischen!** Ein halb-migrierter Host — einige Configs auf
`listen <domain>:443 ssl;`, andere auf `listen 443 ssl;` — führt dazu,
dass nginx beim SNI-Routing für unbekannte server_names das falsche
TLS-Zertifikat ausliefert. Genau dieser Produktions-Incident war der Anlass
für v1.10.2. Entweder atomisch migrieren oder auf dem v1.11.0-IP-bound-Default
bleiben.

### Beispiele

#### Grundkonfiguration

```bash
# Verwendung von Konfigurationsdatei
nginx-set-conf --config_path server_config

# Direkte Konfiguration
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --pollport 8072

# Benutzerdefinierter Zielpfad
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --target_path /tmp/nginx-test

# Dry-Run-Modus
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --dry_run
```

#### Template-Vorschau

```bash
# Template-Konfiguration anzeigen
nginx-set-conf --config_template odoo_ssl --show_template

# Qdrant-Template anzeigen
nginx-set-conf --config_template qdrant --show_template
```

#### Erweiterte Beispiele

```bash
# Qdrant mit gRPC-Unterstützung
nginx-set-conf --config_template qdrant --ip 1.2.3.4 --domain vector.example.com --port 6333 --grpcport 6334 --cert_name vector.example.com

# Flowise AI Server
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com

# Supabase Datenbankserver
nginx-set-conf --config_template supabase --ip 1.2.3.4 --domain supabase.example.com --port 8000 --cert_name supabase.example.com
```

#### IPv6-Unterstützung

Die Parameter `--ip` und `--backend_ip` akzeptieren sowohl IPv4- als auch IPv6-Adressen. IPv6-Adressen werden automatisch mit Klammern in der generierten nginx-Konfiguration formatiert:

```bash
# IPv6-Loopback als Backend
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --backend_ip ::1

# Vollständige IPv6-Backend-Adresse
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com --backend_ip 2001:db8::1
```

Generierte nginx-Konfiguration mit IPv6:

```nginx
proxy_pass http://[::1]:8069;
```

#### Backend-IP-Konfiguration

Der `backend_ip` Parameter steuert die IP-Adresse in den `proxy_pass`-Direktiven. Standardmäßig ist er `127.0.0.1` (localhost), was für Docker-Container auf Loopback korrekt ist.

```bash
# Standard: proxy_pass nutzt 127.0.0.1 (kein --backend_ip nötig)
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com

# IPv6-Loopback-Backend
nginx-set-conf --config_template odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --backend_ip ::1

# Remote-Backend
nginx-set-conf --config_template flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com --backend_ip 192.168.1.50
```

YAML-Konfiguration:

```yaml
# Standard: kein backend_ip nötig (nutzt 127.0.0.1)
Mein Odoo Server:
  config_template: odoo_ssl
  ip: 1.2.3.4
  domain: app.example.com
  port: 11000
  cert_name: app.example.com

# IPv6-Loopback-Backend
Mein IPv6 Service:
  config_template: flowise
  ip: 1.2.3.4
  domain: app.example.com
  port: 3000
  cert_name: app.example.com
  backend_ip: "::1"
```

> **Hinweis:** Der `ip`-Parameter ist die öffentliche Server-IP (in auskommentierten Upstream-Blöcken). Der `backend_ip`-Parameter ist die Adresse, auf der die Anwendung tatsächlich lauscht (in `proxy_pass`).

### Konfigurationsverifikation

#### 1. Konfigurationsdatei-Prüfung (`--verify_config`)

Prüfen ob benötigte nginx Konfigurationsdateien auf dem Server existieren:

```bash
nginx-set-conf --verify_config
```

**Geprüfte Dateien:**
- `/etc/nginx/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf`

**Ausgabe:**
- ✓ EXISTS: Datei ist auf dem Server vorhanden
- ✗ MISSING: Datei nicht gefunden
- Zeigt Dateipfad und Größe für existierende Dateien

#### 2. Fehlende Verzeichnisse erstellen (`--create_dirs`)

Fehlende nginx Konfigurationsverzeichnisse bei Bedarf erstellen:

```bash
nginx-set-conf --create_dirs
```

**Was es tut:**
- Prüft auf fehlende Dateien
- Erstellt `/etc/nginx/nginxconfig.io/` Verzeichnis falls fehlend
- Nützlich nach frischer nginx Installation

#### 3. Konfigurationsbackup (`--backup_config`)

Automatische Backups der aktuellen Server-Konfiguration erstellen:

```bash
nginx-set-conf --backup_config
```

**Backup-Funktionen:**
- Zeitstempel-basierte Backup-Ordner: `/tmp/nginx_backup/nginx_config_backup_YYYYMMDD_HHMMSS`
- Vollständige Sicherung von `/etc/nginx/nginx.conf`
- Rekursive Sicherung des `nginxconfig.io/` Verzeichnisses
- Logging aller Backup-Operationen

### Praktische Anwendungsszenarien

#### Szenario 1: Konsistenzprüfung vor Deployment

```bash
# Vor dem Deployment prüfen
nginx-set-conf --verify_config

# Bei Inconsistenzen: Backup erstellen
nginx-set-conf --backup_config

# Bei fehlenden Verzeichnissen erstellen
nginx-set-conf --create_dirs
```

#### Szenario 2: Server-Setup übernehmen

```bash
# Aktuelle Server-Konfiguration sichern
nginx-set-conf --backup_config

# Fehlende Verzeichnisse erstellen falls nötig
nginx-set-conf --create_dirs
# Option 1 wählen: Local → Server

# Ergebnis überprüfen
nginx-set-conf --verify_config
```

#### Szenario 3: Neue nginx Installation prüfen

```bash
# Prüfen ob alle Dateien vorhanden sind
nginx-set-conf --verify_config

# Falls Verzeichnisse fehlen, diese erstellen
nginx-set-conf --create_dirs
```

### SSL-Zertifikatsverwaltung

#### Let's Encrypt Zertifikat erstellen

```bash
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.example.com
```

#### certbot auf Debian/Ubuntu installieren

```bash
apt-get install certbot
```

#### Authentifizierungsdatei erstellen

```bash
# htpasswd auf Debian/Ubuntu installieren
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htaccess/.htpasswd-user USER
```

### Nginx-Template-Einstellungen

Sie können unsere optimierten Einstellungen herunterladen:
- [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)
- [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)

Basierend auf [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)

### Technische Details

#### Hash-basierte Verifikation
- SHA256-Hashes für präzise Dateivergleiche
- Erkennung von Inhalt, Größe und Änderungszeit
- Robuste Fehlerbehandlung bei Zugriffsproblemen

#### Sichere Synchronisation
- Explizite Benutzerbestätigung vor Überschreibungen
- Automatische Verzeichniserstellung
- Detaillierte Logging-Informationen
- Rollback-Möglichkeit durch Backup-System

#### Flexible Pfad-Konfiguration
- Anpassbare lokale Pfade (Standard: `yaml_examples/`)
- Konfigurierbare Server-Pfade (Standard: `/etc/nginx/`)
- Unterstützung für verschiedene nginx-Installationen

### Erweiterte Nutzung

#### Kombinierte Befehle
```bash
# Backup + Verifikation in einem Workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config
```

#### Mit anderen Optionen kombinieren
```bash
# Verifikation mit Dry-Run
nginx-set-conf --verify_config --dry_run
```

### Fehlerbehebung

#### Häufige Probleme

1. **Berechtigung verweigert**: Sicherstellen, dass der Benutzer Schreibrechte für `/etc/nginx/` hat
2. **Verzeichnisse fehlen**: Tool erstellt automatisch fehlende Verzeichnisse
3. **Backup-Speicher voll**: Alte Backups aus `/tmp/nginx_backup/` entfernen

#### Logging
Alle Operationen werden geloggt in:
- Konsole: INFO-Level
- Datei: `nginx_set_conf.log` (mit Rotation)

### Entwicklung & Tests

```bash
# Tests ausführen
pytest

# Mit Coverage ausführen
pytest --cov=nginx_set_conf
```

Die Test-Suite umfasst 104 Tests für Validatoren, Utils und Templates.

### Sicherheitsaspekte

- **Keine automatischen Änderungen**: Alle Änderungen erfordern explizite Bestätigung
- **Backup-First-Ansatz**: Backup vor jeder Synchronisation empfohlen
- **Granulare Kontrolle**: Einzelne Dateien können identifiziert und behandelt werden
- **Fehlerbehandlung**: Robuste Behandlung von Permissions- und Zugriffsproblemen
- **Eingabevalidierung**: Alle Parameter (IP, Domain, Port, Pfade) werden vor Verwendung validiert
- **Shell-Injection-Prävention**: Keine `os.system`-Aufrufe, sichere Subprocess-Behandlung
- **Strukturiertes Logging**: Konsistentes Logging statt Debug-Prints

### Lizenz

Dieses Projekt ist unter den Bedingungen der **AGPLv3**-Lizenz lizenziert.