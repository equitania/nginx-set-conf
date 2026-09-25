<!--
  Capability Card — generated/maintained via the `cli-capability-card` skill.
  Audience: an LLM/agent that wants to USE this tool. Keep it dense and current.
  Regenerate the command table with scripts/introspect_cli.py after CLI changes.
-->
# nginx-set-conf — Agent Capability Card

> Generates nginx reverse-proxy vhosts for Docker services from built-in templates, obtains
> Let's Encrypt certificates, and keeps the three shared base configs (`nginx.conf`,
> `general.conf`, `security.conf`) in sync on the server.

- **Invoke:** `nginx-set-conf <command> [options]` (runs as root on the nginx host)
- **Install:** `uv tool install nginx-set-conf` (or `pip install nginx-set-conf`)
- **Version:** 1.19.2
- **Self-serve:** `nginx-set-conf capability-card` prints this card from the installed tool (live version injected)
- **Framework:** Python / Click  ·  **Human docs:** `README.md` (EN/DE), `RELEASE_NOTES.md`

## Capabilities at a glance
- Deploy one vhost per domain from a named template (Odoo, Flowise, Qdrant, n8n, Nextcloud, static sites, redirects, …).
- Batch-deploy every vhost defined in a folder of YAML files — the standard server run.
- Obtain a Let's Encrypt certificate automatically (certbot standalone) or use an own certificate.
- Protect a vhost with HTTP basic auth (htpasswd) and/or an IP allow-list.
- Enable HTTP/3 (QUIC) listeners and the `Alt-Svc` header per vhost.
- Verify and repair drift in the three base configs; every deploy does this automatically first.
- Install a catch-all `default_server` that drops unknown SNI/Host with HTTP 444.
- Migrate old hostname-bound `listen` lines to wildcard `listen <port>` with backup and rollback.
- Preview everything with `--dry_run`, or print a raw template with `show`.

## Command reference

| Command | Purpose | Args / Flags |
|---|---|---|
| `nginx-set-conf backup` | Back up the current nginx configuration | — |
| `nginx-set-conf capability-card` | Print this agent capability card | — |
| `nginx-set-conf deploy` | Generate vhost configs and reload nginx | --config_path TEXT, --config_template TEXT, --domain TEXT, --ip TEXT, --port TEXT, --pollport TEXT, --grpcport TEXT, --backend_ip TEXT, --root_path TEXT, --redirect_domain TEXT, --cert_name TEXT, --cert_key TEXT, --auth_file TEXT, --allowed_ips TEXT, --enable_http3, --disable_domain_listen, --target_path TEXT, --dry_run |
| `nginx-set-conf migrate` | Rewrite hostname-bound listen directives to wildcard | --target_path TEXT, --dry_run |
| `nginx-set-conf setup-default` | Install the catch-all for unknown SNI (00-default.conf) | --target_path TEXT, --dry_run |
| `nginx-set-conf show` | Print a template without applying it | TEMPLATE |
| `nginx-set-conf sync` | Write the embedded base configs to the server | --force |
| `nginx-set-conf templates` | List available templates | — |
| `nginx-set-conf verify` | Compare the base configs on the server with the embedded ones | — |

Notation: `[ARG]` optional positional · `ARG` required positional · `a|b` choice · `--flag` boolean.

Defaults: `--target_path` = `/etc/nginx/conf.d`, `--backend_ip` = `127.0.0.1`, `--root_path` = `/opt/www`.

### Templates (`--config_template` / YAML `config_template`)
`code_server`, `fast_report`, `flowise`, `guacamole`, `kasm`, `mailpit`, `n8n`, `nextcloud`,
`odoo_http`, `odoo_ssl`, `patchmon`, `pgadmin`, `portainer`, `pwa`, `qdrant`, `redirect`,
`redirect_ssl`, `static_public_ssl`, `static_ssl`, `supabase`. `default_ssl_reject` is listed
but installed only via `setup-default`. Authoritative list: `nginx-set-conf templates`.

| Need | Extra input |
|---|---|
| Proxy templates | `port` (container port); `odoo_*` also `pollport`; `qdrant` also `grpcport` |
| `static_ssl` (noindex) / `static_public_ssl` (indexable, markdown-aware) | `root_path` instead of `port` |
| `redirect`, `redirect_ssl` | `redirect_domain` |
| HTTP/3 not supported by | `fast_report`, `mailpit`, `redirect`, `redirect_ssl`, `default_ssl_reject`, `odoo_http` |

## Recipes

### Standard server run (deploy everything from YAML)
```bash
nginx-set-conf --config_path=/root/docker-builds/ngx-conf
```
Flag-only legacy form, identical to `nginx-set-conf deploy --config_path=…`. Reads every
`*.yaml`/`*.yml` in the folder; each top-level key is one vhost.

### YAML vhost entry
```yaml
erp.example.com:
  config_template: odoo_ssl
  ip: 203.0.113.10
  domain: erp.example.com
  port: 11000
  pollport: 12000
  cert_name: erp.example.com
  # optional: backend_ip, auth_file, allowed_ips, enable_http3: true,
  #           disable_domain_listen: true, root_path, redirect_domain, cert_key, target_path
```

### Preview before touching the server
```bash
nginx-set-conf deploy --config_path=/root/docker-builds/ngx-conf --dry_run
```
Logs which files would be written and which certificates requested; writes nothing, reloads nothing.

### Single vhost without YAML
```bash
nginx-set-conf deploy --config_template=odoo_ssl --domain=erp.example.com --ip=203.0.113.10 --port=8069 --pollport=8072 --cert_name=erp.example.com
```

### Static site behind a password
```bash
apt-get install -y apache2-utils
mkdir -p /etc/nginx/.htaccess
htpasswd -c /etc/nginx/.htaccess/.htpasswd-docs reviewer
chgrp "$(awk '/^user/{sub(";","",$2); print $2; exit}' /etc/nginx/nginx.conf)" /etc/nginx/.htaccess/.htpasswd-docs
chmod 640 /etc/nginx/.htaccess/.htpasswd-docs
nginx-set-conf deploy --config_template=static_public_ssl --domain=docs.example.com --ip=203.0.113.10 --root_path=/var/www/docs.example.com --cert_name=docs.example.com --auth_file=/etc/nginx/.htaccess/.htpasswd-docs
```
Expect `401` on every URL without credentials. Check direct file URLs too (`/page.html`, `/page.md`).

### Check and repair the base configs
```bash
nginx-set-conf verify
nginx-set-conf sync          # aborts on differences
nginx-set-conf sync --force  # overwrites differing files; backup is made first
```

### Close the default-vhost fallback, then go wildcard
```bash
nginx-set-conf setup-default
nginx-set-conf migrate --dry_run
nginx-set-conf migrate
```

## Guardrails & gotchas
- **Root on the nginx host only.** `deploy` (without `--dry_run`), `sync`, `backup`, `setup-default`, `migrate` write under `/etc/nginx` and call `systemctl`. Never run them from a workstation.
- **Overwrites without asking:** `deploy` writes `<target_path>/<domain>.conf` and silently replaces an existing file of that name, including hand edits. Keep customisations in the YAML, not in the generated file.
- **Downtime on new certificates:** if `/etc/letsencrypt/live/<cert_name>/` is missing, `deploy` **stops nginx** and runs `certbot certonly --standalone` (needs port 80 free and DNS pointing at the host), then continues. Existing certificates are reused.
- **Own certificate:** `--cert_name` = full path to the `.crt`, `--cert_key` = full path to the key. Omit `--cert_key` for Let's Encrypt.
- **Pre-flight on every deploy:** the three base configs are checked and auto-repaired before the first vhost is written; a failing repair aborts the deploy. Skipped with `--dry_run`.
- **Safe reload:** `nginx -t` runs before `systemctl reload`; on failure the running nginx keeps the old config and the command exits non-zero — but the new `.conf` file is already on disk. Fix or remove it before the next reload.
- **Interactive fallback:** `deploy` without `--config_path` and without the required single-vhost options (`config_template`, `ip`, `domain`, `cert_name`, and `port` or `root_path`) prompts for every value — it blocks an unattended agent. Always pass the flags or `--config_path`.
- **`--auth_file`:** absolute path must be under `/etc/nginx/` and not under `/etc/nginx/conf.d/`. The file must be readable by the nginx worker user (`user` in `nginx.conf`: `www-data` on Debian packages, `nginx` on nginx.org packages) — otherwise every request fails with **500** and the error log shows `(13: Permission denied)`. nginx ignores `.htaccess`; use htpasswd.
- **`static_public_ssl` + `auth_file` before 1.19.2:** auth was set in `location /` only, so direct `.html`/`.md`/`/pdf/`/`llms.txt` URLs stayed public. Upgrade and redeploy.
- **`--disable_domain_listen` / `migrate`:** wildcard listens let unknown SNI fall through to the first vhost. Run `setup-default` first.
- **`--enable_http3`:** needs nginx ≥ 1.25.0 and UDP/443 open in the firewall.
- **`sync --force`:** local customisations in the base configs are lost (backup under `/var/backups/nginx_set_conf/`).
- **Log file:** `/var/log/nginx_set_conf/nginx_set_conf.log` (mode 0600) records domains, IPs and executed commands.

## Machine-readable outputs
None. All commands log human-readable text; `show` and `capability-card` print raw text to stdout.
Exit code is non-zero when `sync`, `backup`, `setup-default`, `migrate` fail or `nginx -t` rejects a deploy.

## Deeper docs
- `README.md` — templates in detail, HTTP/3, own certificates, htpasswd setup (EN + DE).
- `RELEASE_NOTES.md` — behaviour changes per version.
- `yaml_examples/server_config/config.yaml` — one YAML example per template.
