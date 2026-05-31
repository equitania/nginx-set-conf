# Phase 5: HTTP/3 opt-in support — Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `nginx_set_conf/nginx_set_conf.py` | CLI entry point | request-response | self (existing `--disable_domain_listen` flag) | exact |
| `nginx_set_conf/utils.py` | engine/service | transform | self (existing `disable_domain_listen` propagation + `setup_default_server`) | exact |
| `nginx_set_conf/validators.py` | validator/middleware | request-response | self (existing `VALID_TEMPLATES` + `validate_config_template`) | exact |
| `nginx_set_conf/templates/default_ssl_reject.py` | template | config-emit | self (existing catch-all block, extend for QUIC) | exact |
| `nginx_set_conf/templates/*.py` (12 SSL templates) | template | config-emit | `nginx_set_conf/templates/odoo_ssl.py` | exact |
| `nginx_set_conf/templates/all_templates.py` | registry | config-emit | self (existing `TEMPLATES` dict + `get_config_template`) | exact |
| `nginx_set_conf/config_verification.py` | embedded config | config-emit | self (existing `NGINX_CONF_TEMPLATE`) | exact |
| `tests/test_templates.py` | test | unit | self (existing `TestHttp2Enabled`, `TestDefaultSslReject`, `TestIpBoundListen`) | exact |
| `tests/test_validators.py` | test | unit | self (existing `TestValidateConfigTemplate`) | exact |

---

## Pattern Assignments

### `nginx_set_conf/nginx_set_conf.py` — new `--enable_http3` flag

**Analog:** existing `--disable_domain_listen` flag in the same file.

**Declaration pattern** (`nginx_set_conf.py` lines 197–209 — copy this shape):
```python
@click.option(
    "--disable_domain_listen",
    is_flag=True,
    help=(
        "Generate `listen 80;` / `listen 443 ssl;` instead of "
        "`listen <domain>:80;` / `listen <domain>:443 ssl;`. "
        "Avoids DNS resolution at nginx config-parse time (useful if "
        "upstream DNS is flaky) and intranet systems without public DNS. "
        "WARNING: mixing both styles on the same server causes SNI "
        "fallback to the first server block — migrate all configs in one "
        "go via `--migrate_to_wildcard`."
    ),
)
```

New flag to add in the same decorator chain (boolean, default False, positioned after `--backend_ip`):
```python
@click.option(
    "--enable_http3",
    is_flag=True,
    help=(
        "Emit QUIC/HTTP/3 listen directives and Alt-Svc header for "
        "browser-facing SSL templates. Requires nginx >= 1.25.0 and "
        "UDP/443 open in the host firewall. See README for full "
        "prerequisites. Excluded templates: fast_report, mailpit, "
        "redirect, redirect_ssl, default_ssl_reject, odoo_http."
    ),
)
```

**Function signature extension** (`nginx_set_conf.py` lines 270–294 — add `enable_http3` after `disable_domain_listen`):
```python
def start_nginx_set_conf(
    ...
    disable_domain_listen,
    enable_http3,          # new
    config_path,
    ...
):
```

**YAML read-through pattern** (`nginx_set_conf.py` lines 383–413 — copy `yaml_disable_domain_listen` pattern):
```python
yaml_disable_domain_listen = yaml_config.get("disable_domain_listen", False)
# add:
yaml_enable_http3 = yaml_config.get("enable_http3", False)
```

**Pass-through to `execute_commands`** — both call sites (lines 397–413 and 421–437):
```python
execute_commands(
    ...
    yaml_disable_domain_listen,
    backend_ip=yaml_backend_ip or None,
    # add:
    enable_http3=yaml_enable_http3,
)
```

**`click.ClickException` pattern for version gate** (`nginx_set_conf.py` lines 484–488 — reuse this shape):
```python
if test_result is not None and test_result.returncode != 0:
    raise click.ClickException(
        "nginx -t failed — refusing to reload. The running nginx process "
        "keeps the previous configuration. Fix the generated config and re-run."
    )
```

---

### `nginx_set_conf/utils.py` — flag propagation + nginx version gate

**Analog A:** existing `disable_domain_listen` branch in `execute_commands` (lines 601–602, 623–624, 736–748).

**Signature extension pattern** (lines 587–603 — add `enable_http3=False` after `backend_ip`):
```python
def execute_commands(
    config_template,
    domain,
    ip,
    cert_name,
    cert_key,
    port,
    pollport,
    redirect_domain,
    auth_file,
    allowed_ips,
    target_path=None,
    dry_run=False,
    grpcport=None,
    disable_domain_listen=False,
    backend_ip=None,
    enable_http3=False,    # new — must be last for backward compat
):
```

**Validation call-through** (lines 626–646 — add `enable_http3` after existing params):
```python
validate_all_inputs(
    ...
    backend_ip=backend_ip or "",
    enable_http3=enable_http3,    # new — validators.py will enforce exclusion list
)
```

**`disable_domain_listen` branch as template for `enable_http3` injection** (lines 741–748 — emit HTTP/3 directives AFTER the `disable_domain_listen` block, in the same section):
```python
if disable_domain_listen:
    logger.warning(
        "--disable_domain_listen is active: listen socket will be wildcard. "
        "Make sure default_ssl_reject is deployed (--setup_default) to "
        "prevent SNI fallback to the wrong certificate."
    )
    content = content.replace(f"listen {formatted_listen_ip}:80", "listen 80")
    content = content.replace(f"listen {formatted_listen_ip}:443", "listen 443")
# add after:
if enable_http3:
    content = _inject_http3_directives(content, formatted_listen_ip)
```

**Analog B:** `_run_service_command` in `nginx_set_conf.py` (lines 86–113) for the subprocess pattern used by `nginx -v` parsing:
```python
try:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result
except FileNotFoundError:
    logger.error("Command not found: %s", args[0])
    return None
```

**New helper `get_nginx_version()` — extract and test independently**:
```python
def get_nginx_version() -> tuple[int, int, int] | None:
    """Parse nginx version from `nginx -v` stderr output.

    Returns:
        (major, minor, patch) tuple, or None if nginx is not found or
        the version string cannot be parsed.
    """
    try:
        result = subprocess.run(
            ["nginx", "-v"],
            capture_output=True,
            text=True,
        )
        # nginx -v writes to stderr: "nginx version: nginx/1.27.2"
        match = re.search(r"nginx/(\d+)\.(\d+)\.(\d+)", result.stderr)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except FileNotFoundError:
        pass
    return None
```

**Version gate call site in `execute_commands`** (place before cache-path substitution, after validation):
```python
if enable_http3:
    version = get_nginx_version()
    if version is None or version < (1, 25, 0):
        ver_str = ".".join(str(v) for v in version) if version else "unknown"
        raise click.ClickException(
            f"HTTP/3 requires nginx >= 1.25.0 (you have {ver_str}). "
            "Either upgrade nginx (Debian: bookworm-backports; Ubuntu: 24.04+; "
            "RHEL: 9.4+) or omit --enable_http3 to ship HTTP/2-only configs."
        )
```

**`_insert_after_marker` helper** (lines 309–331) — reuse for injecting QUIC listen lines after the existing `listen ip.ip.ip.ip:443 ssl;` line in the template content string:
```python
def _insert_after_marker(content: str, marker: str, insert_lines: list, first_only: bool = True) -> str:
    lines = content.split("\n")
    new_lines = []
    found = False
    for line in lines:
        new_lines.append(line)
        if marker in line and (not found or not first_only):
            new_lines.extend(insert_lines)
            found = True
    return "\n".join(new_lines)
```

**New helper `_inject_http3_directives(content, formatted_listen_ip)`**: insert after the line containing `listen {formatted_listen_ip}:443 ssl;` using `_insert_after_marker`. The QUIC listen line must use the SAME `formatted_listen_ip` already substituted by the IP-placeholder pass — never re-derive the IP. This preserves the v1.11.0 IP-bound listen invariant (one IP, both TCP and QUIC sockets bound to the same interface).

**reuseport detect-at-deploy-time** — grep the target conf.d for an existing `quic reuseport` before emit:
```python
def _quic_reuseport_already_claimed(conf_dir: str, ip: str, port: int = 443) -> bool:
    """Return True if any conf in conf_dir already carries a `quic ... reuseport`
    listen on this port — either IP-bound (`listen <ip>:<port> quic reuseport;`)
    OR the wildcard form emitted by the default_ssl_reject catch-all
    (`listen <port> quic default_server reuseport;`).

    Only one listen directive per (IP, port) may carry reuseport across the
    entire nginx host. If already claimed, the new vhost must omit it.
    """
    # IP prefix is OPTIONAL — the default_ssl_reject QUIC catch-all uses a
    # wildcard `listen 443 quic ... reuseport;` with no IP prefix. The scanner
    # MUST match both forms or vhosts would double-claim reuseport on UDP/443
    # and break nginx reload (Phase 5 plan-checker BLOCKER 3).
    pattern = re.compile(
        rf"listen\s+(?:{re.escape(ip)}:)?{port}\s+quic\b.*\breuseport"
    )
    try:
        for fname in os.listdir(conf_dir):
            if not fname.endswith(".conf"):
                continue
            fpath = os.path.join(conf_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                if pattern.search(f.read()):
                    return True
    except (OSError, PermissionError):
        pass
    return False
```

---

### `nginx_set_conf/validators.py` — HTTP/3 exclusion list

**Analog:** existing `VALID_TEMPLATES` set (lines 38–57) + `validate_config_template` (lines 291–313) + COR-02 inline guard pattern (lines 358–362).

**Exclusion set constant** — add alongside `VALID_TEMPLATES`:
```python
# HTTP3_EXCLUDED_TEMPLATES: templates for which --enable_http3 is rejected.
# Rationale per template:
#   fast_report      — server-to-server PDF API, no browser traffic
#   mailpit          — dev SMTP test tool, internal-only
#   redirect         — HTTP-only, no TLS
#   redirect_ssl     — trivial 301, QUIC overhead not worth it
#   default_ssl_reject — SNI catch-all returns 444, no useful response
#   odoo_http        — HTTP-only, no TLS
HTTP3_EXCLUDED_TEMPLATES = frozenset({
    "fast_report",
    "mailpit",
    "redirect",
    "redirect_ssl",
    "default_ssl_reject",
    "odoo_http",
})
```

**Inline guard in `validate_all_inputs`** — copy the COR-02 pattern (lines 358–362):
```python
# COR-02 pattern:
if "redirect" in config_template and not redirect_domain.strip():
    raise ValidationError(
        f"'redirect_domain' is required for template '{config_template}'"
    )

# HTTP/3 exclusion (same shape):
if enable_http3 and config_template in HTTP3_EXCLUDED_TEMPLATES:
    raise ValidationError(
        f"--enable_http3 is not supported for template '{config_template}'. "
        f"Excluded because: this template does not serve browser/end-user "
        f"traffic where HTTP/3 provides benefit. "
        f"HTTP/3-capable templates: "
        + ", ".join(sorted(VALID_TEMPLATES - HTTP3_EXCLUDED_TEMPLATES))
    )
```

**`validate_all_inputs` signature** — add `enable_http3: bool = False` as the last parameter (after `backend_ip`).

---

### `nginx_set_conf/templates/default_ssl_reject.py` — QUIC catch-all extension

**Decision (planner discretion from CONTEXT.md):** Extend the existing template rather than add a sibling. The template already has two server blocks (port 80 and port 443 SSL); a third QUIC block follows the same pattern cleanly. This avoids registry fragmentation and keeps `setup_default_server` in utils.py as a single path.

**Existing structure** (full file, lines 35–55):
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate /etc/nginx/ssl/default.crt;
    ssl_certificate_key /etc/nginx/ssl/default.key;
    return 444;
}
```

**Extend with a QUIC catch-all block** (append after the SSL block):
```nginx
server {
    listen 443 quic default_server reuseport;
    listen [::]:443 quic default_server reuseport;
    server_name _;

    ssl_certificate /etc/nginx/ssl/default.crt;
    ssl_certificate_key /etc/nginx/ssl/default.key;

    # Drop QUIC connections for unknown SNI before any data is exchanged.
    return 444;
}
```

**CRITICAL (SKILL.md DANGER ZONE):** The QUIC catch-all block in `default_ssl_reject` uses wildcard `listen 443 quic ...;` (no IP prefix) — same as the existing TCP 443 SSL block. This is intentional and correct for `default_ssl_reject`: it is a catch-all `default_server` block, not a vhost. The `reuseport` on this block "claims" the QUIC socket; all subsequent HTTP/3-enabled vhost configs MUST omit `reuseport` (enforced via `_quic_reuseport_already_claimed` at deploy time). Service template QUIC listen lines remain IP-bound: `listen ip.ip.ip.ip:443 quic;` — no `reuseport` because the catch-all already owns it.

**`setup_default_server` in utils.py** — no signature change needed; it already writes the full `default_ssl_reject` template. When the template is extended to include the QUIC block, `--setup_default` automatically installs TCP + QUIC catch-alls together.

---

### `nginx_set_conf/templates/*.py` — 12 SSL templates (HTTP/3 directives)

**Analog:** `nginx_set_conf/templates/odoo_ssl.py` — canonical SSL service template.

**The 12 templates to modify:**
`odoo_ssl`, `flowise`, `n8n`, `nextcloud`, `guacamole`, `kasm`, `pgadmin`, `portainer`, `pwa`, `code_server`, `supabase`, `qdrant` (REST server block only).

**Template marker pattern** — templates do NOT embed `--enable_http3` logic in the static string. Instead, the `TEMPLATE` string gains a marker comment after the `listen ip.ip.ip.ip:443 ssl;` line:

```nginx
server {
    listen ip.ip.ip.ip:80;
    ...
}

server {
    listen ip.ip.ip.ip:443 ssl;
    #http3_listen_placeholder
    server_name server.domain.de;
    ...
    http2 on;    # already present from PROTO-01
    #http3_directives_placeholder
    ...
}
```

The `_inject_http3_directives` helper in utils.py replaces these markers when `enable_http3=True`. This keeps templates static/auditable and avoids conditional nginx syntax inside the template string.

**Alternative (simpler) approach — marker-free string replace:** Since `_insert_after_marker` already works by string-scanning for a marker in the content, just use the listen line itself as the marker:

```python
# In _inject_http3_directives(content, formatted_listen_ip):
QUIC_LISTEN_LINE = f"    listen {formatted_listen_ip}:443 quic;"
QUIC_DIRECTIVES = [
    "    http3 on;",
    "    quic_retry on;",
    "    ssl_protocols TLSv1.3;",
    "    add_header Alt-Svc 'h3=\":443\"; ma=86400' always;",
]
marker = f"listen {formatted_listen_ip}:443 ssl;"
content = _insert_after_marker(
    content,
    marker,
    [QUIC_LISTEN_LINE] + QUIC_DIRECTIVES,
)
```

This means no template file change is needed for the 12 templates — HTTP/3 directives are injected at substitution time. Only `default_ssl_reject.py` changes (QUIC catch-all block added statically).

**`qdrant` special case:** qdrant has two server blocks — REST (443 ssl) and gRPC (additional port). The `_inject_http3_directives` helper must only inject after the first `listen {ip}:443 ssl;` occurrence (`first_only=True` is the default in `_insert_after_marker`), leaving the gRPC server block untouched.

---

### `nginx_set_conf/templates/all_templates.py` — registry unchanged

No changes needed if HTTP/3 directives are injected at emit time. The `TEMPLATES` dict and `get_config_template` function stay as-is.

If a new `default_quic_reject` sibling were added (not the chosen path), it would follow the existing import + dict entry pattern exactly:
```python
from nginx_set_conf.templates.default_ssl_reject import TEMPLATE as DEFAULT_SSL_REJECT_TEMPLATE
# analogously:
from nginx_set_conf.templates.default_quic_reject import TEMPLATE as DEFAULT_QUIC_REJECT_TEMPLATE
TEMPLATES = {
    ...
    "default_quic_reject": DEFAULT_QUIC_REJECT_TEMPLATE,
}
```

---

### `nginx_set_conf/config_verification.py` — `NGINX_CONF_TEMPLATE`

**Analog:** existing `NGINX_CONF_TEMPLATE` constant usage and `TestHttp2Enabled` test pattern.

**Decision:** `http3 on;` does NOT belong at `http {}` scope in `nginx.conf`. HTTP/3 is per-vhost opt-in; the global http{} block must not force QUIC on every server block. The `http2 on;` directive in `NGINX_CONF_TEMPLATE` (PROTO-01) is appropriate because HTTP/2 is safe globally. HTTP/3 is not — it requires UDP/443 firewall, explicit operator opt-in, and version gate. No change to `config_verification.py` is required for Phase 5.

---

### `tests/test_templates.py` — new HTTP/3 tests

**Analog:** `TestHttp2Enabled` (lines 333–358), `TestDefaultSslReject` (lines 243–283), `TestIpBoundListen` (lines 181–241).

**Test class structure to add — copy `TestHttp2Enabled` shape for the version-gate helper, `TestDefaultSslReject` shape for the catch-all, and `TestIpBoundListen` shape for per-template invariants:**

```python
class TestHttp3DefaultCatchAll:
    """default_ssl_reject must carry a QUIC default_server block after Phase 5."""

    def test_quic_catch_all_block_present(self):
        content = TEMPLATES["default_ssl_reject"]
        assert "listen 443 quic default_server" in content

    def test_quic_ipv6_catch_all_present(self):
        content = TEMPLATES["default_ssl_reject"]
        assert "listen [::]:443 quic default_server" in content

    def test_quic_catch_all_returns_444(self):
        content = TEMPLATES["default_ssl_reject"]
        # At least 3 return 444; blocks (80, 443 ssl, 443 quic)
        assert content.count("return 444;") >= 3


class TestNginxVersionParsing:
    """Unit tests for the get_nginx_version() helper (no subprocess needed)."""
    # Use mock/monkeypatch to inject synthetic nginx -v output

    def test_parses_standard_version(self, monkeypatch):
        import subprocess
        import nginx_set_conf.utils as utils
        mock_result = subprocess.CompletedProcess(
            args=["nginx", "-v"],
            returncode=0,
            stdout="",
            stderr="nginx version: nginx/1.27.2",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        assert utils.get_nginx_version() == (1, 27, 2)

    def test_returns_none_when_nginx_missing(self, monkeypatch):
        import subprocess
        import nginx_set_conf.utils as utils
        def raise_fnf(*a, **kw):
            raise FileNotFoundError
        monkeypatch.setattr(subprocess, "run", raise_fnf)
        assert utils.get_nginx_version() is None

    def test_version_below_threshold(self, monkeypatch):
        import subprocess
        import nginx_set_conf.utils as utils
        mock_result = subprocess.CompletedProcess(
            args=["nginx", "-v"], returncode=0, stdout="",
            stderr="nginx version: nginx/1.24.0",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        ver = utils.get_nginx_version()
        assert ver is not None and ver < (1, 25, 0)
```

---

### `tests/test_validators.py` — new HTTP/3 exclusion tests

**Analog:** `TestValidateConfigTemplate` (lines 281–334) and `TestValidateRedirectDomain` (lines 366–408).

**Test class to add:**

```python
class TestHttp3Exclusion:
    """validate_all_inputs must reject --enable_http3 for excluded templates."""

    def test_excluded_template_raises(self):
        with pytest.raises(ValidationError, match="enable_http3"):
            validate_all_inputs(
                config_template="fast_report",
                domain="example.com",
                ip="1.2.3.4",
                port="8080",
                cert_name="example.com",
                enable_http3=True,
            )

    def test_included_template_passes(self):
        # odoo_ssl is in the HTTP/3-capable set — must not raise
        validate_all_inputs(
            config_template="odoo_ssl",
            domain="example.com",
            ip="1.2.3.4",
            port="8069",
            cert_name="example.com",
            enable_http3=True,
        )

    @pytest.mark.parametrize("template", [
        "fast_report", "mailpit", "redirect", "redirect_ssl", "odoo_http",
    ])
    def test_all_excluded_templates_reject_http3(self, template):
        with pytest.raises(ValidationError):
            validate_all_inputs(
                config_template=template,
                domain="example.com",
                ip="1.2.3.4",
                port="80",
                cert_name="example.com",
                redirect_domain="new.example.com" if "redirect" in template else "",
                enable_http3=True,
            )

    def test_http3_false_does_not_validate_exclusion(self):
        # enable_http3=False (default) must never trigger the exclusion check
        validate_all_inputs(
            config_template="fast_report",
            domain="example.com",
            ip="1.2.3.4",
            port="8080",
            cert_name="example.com",
            enable_http3=False,
        )
```

---

## Shared Patterns

### Boolean flag: CLI declaration → YAML read-through → execute_commands propagation

**Source:** `--disable_domain_listen` end-to-end in `nginx_set_conf.py` (lines 197–209, 284, 386, 411, 434) and `utils.py` (lines 601, 623, 741–748).

**Apply to:** `--enable_http3` everywhere. The pattern is: `@click.option is_flag=True` → function parameter → `yaml_config.get("...", False)` → keyword arg in every `execute_commands` call → last positional param in `execute_commands` signature → guarded block inside `execute_commands`.

### `click.ClickException` for hard stops

**Source:** `nginx_set_conf.py` lines 484–488.

**Apply to:** nginx version gate inside `execute_commands`. When `enable_http3=True` and nginx < 1.25.0 is detected, raise `click.ClickException` with the remediation message from CONTEXT.md.

### `subprocess.run(..., capture_output=True, text=True)` pattern

**Source:** `nginx_set_conf.py` lines 104–112 (`_run_service_command`) and `utils.py` line 240.

**Apply to:** `get_nginx_version()` helper in utils.py. Use `capture_output=True` so stderr (where nginx -v writes) is captured. Wrap in `try/except FileNotFoundError` returning None when nginx is not installed.

### `_insert_after_marker` for in-memory content injection

**Source:** `utils.py` lines 309–331.

**Apply to:** `_inject_http3_directives()` helper in utils.py. Find the `listen {ip}:443 ssl;` line in the already-substituted template content string and insert the QUIC listen line + HTTP/3 directives immediately after it. Use `first_only=True` (default) to avoid touching a second server block (e.g. qdrant's gRPC block).

### IP-bound listen invariant (SKILL.md DANGER ZONE)

**Source:** SKILL.md §DANGER ZONE + `test_ip_placeholder_restricted_to_listen` in `test_templates.py` (lines 149–167).

**Apply to:** every QUIC listen line emitted by `_inject_http3_directives`. The line MUST be:
```
listen {formatted_listen_ip}:443 quic;
```
NOT `listen 443 quic;` (wildcard) — that would reintroduce the v1.10.0 SNI-fallback risk for vhost configs. Only `default_ssl_reject.py` uses wildcard QUIC (it IS the catch-all; wildcard + `default_server` is correct there).

### Replace-order invariant (SKILL.md DANGER ZONE)

**Source:** SKILL.md line 125 + `utils.py` lines 722–755 comments.

**Apply to:** `_inject_http3_directives` must be called AFTER the IP-placeholder → Domain-placeholder → `disable_domain_listen` passes. The function receives the already-substituted `formatted_listen_ip` value, never the raw `ip.ip.ip.ip` literal.

### Exclusion set as `frozenset` constant

**Source:** `VALID_TEMPLATES` (validators.py lines 38–57) — `set` literal with inline comment block.

**Apply to:** `HTTP3_EXCLUDED_TEMPLATES` in validators.py. Use `frozenset` (immutable, signals "this is a configuration constant not a mutable collection") and place adjacent to `VALID_TEMPLATES` with a doc comment listing per-template rationale.

### Test class structure: one class per feature, explicit `TEMPLATE_NAME` or template list constant

**Source:** `TestDefaultSslReject` (lines 243–283) and `TestIpBoundListen` (lines 181–241).

**Apply to:** `TestHttp3DefaultCatchAll`, `TestNginxVersionParsing`, `TestHttp3Exclusion`. Each class is self-contained with a class-level constant for template names/lists.

---

## No Analog Found

None. All Phase 5 work touches existing files whose patterns are fully captured above.

---

## Metadata

**Analog search scope:** `nginx_set_conf/`, `nginx_set_conf/templates/`, `tests/`, `~/.claude/skills/nginx-set-conf/SKILL.md`
**Files read:** 10 source files
**Pattern extraction date:** 2026-05-31
