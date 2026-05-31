---
phase: 05-http3-opt-in-support
reviewed: 2026-05-31T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - nginx_set_conf/__init__.py
  - nginx_set_conf/nginx_set_conf.py
  - nginx_set_conf/templates/default_ssl_reject.py
  - nginx_set_conf/utils.py
  - nginx_set_conf/validators.py
  - tests/test_templates.py
  - tests/test_validators.py
findings:
  critical: 2
  warning: 2
  info: 2
  total: 6
status: issues_found
---

# Phase 05: Code Review Report — HTTP/3 Opt-In Support

**Reviewed:** 2026-05-31
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

This review covers the HTTP/3 / QUIC opt-in implementation (`--enable_http3` flag): CLI plumbing in `nginx_set_conf.py`, the HTTP/3 exclusion validator in `validators.py`, nginx version gating and QUIC directive injection in `utils.py`, and the QUIC catch-all block in `templates/default_ssl_reject.py`.

The core mechanism is sound: version gating via `get_nginx_version()` is correct, the `_quic_reuseport_already_claimed` scanner correctly handles the IPv4 wildcard form emitted by the default_ssl_reject catch-all, and the Alt-Svc header value (`h3=":443"; ma=86400`) is syntactically correct nginx config.

Two blockers were found. First, combining `--disable_domain_listen` with `--enable_http3` silently produces a config that is missing all HTTP/3 directives — the injection marker is destroyed by the listen-stripping step, the injector logs only a WARNING, and the file is written with no QUIC directives and no user-visible error. Second, the injected `ssl_protocols TLSv1.3;` overrides the http-block `ssl_protocols TLSv1.2 TLSv1.3;` at the server scope, dropping TLSv1.2 support for the same vhost on TCP/443 — undocumented and likely unintentional breakage for TLSv1.2 clients.

---

## Critical Issues

### CR-01: `--disable_domain_listen` + `--enable_http3` silently drops all HTTP/3 directives

**File:** `nginx_set_conf/utils.py:873-889`

**Issue:** In `execute_commands`, the HTTP/3 injection step uses a marker string `f"listen {formatted_listen_ip}:443 ssl;"` to locate the injection point (line 423 in `_inject_http3_directives`). However, the `disable_domain_listen` pass (lines 873–881) runs **before** the HTTP/3 injection pass (lines 887–889) and rewrites `listen 1.2.3.4:443` to `listen 443`, leaving `listen 443 ssl;` in the content. When `_inject_http3_directives` subsequently searches for the IP-bound marker it finds nothing, logs only a `WARNING`-level message (`_inject_http3_directives: marker '...' not found`), and returns the content **unchanged**. The QUIC `listen` line, `http3 on;`, `quic_retry on;`, `ssl_protocols TLSv1.3;`, and `Alt-Svc` header are all absent from the written config. No error is raised, no `ClickException` is thrown, `nginx -t` passes silently (the config is valid — it just has no HTTP/3). The user believes HTTP/3 is active; it is not.

**Fix:** Add a mutual-exclusion guard in `execute_commands` before either flag takes effect, or adapt `_inject_http3_directives` to also match the wildcard form after stripping. The simplest safe fix is to raise early:

```python
# In execute_commands, after validate_all_inputs and before the disable_domain_listen block:
if enable_http3 and disable_domain_listen:
    raise click.ClickException(
        "--enable_http3 and --disable_domain_listen cannot be used together: "
        "--disable_domain_listen strips the IP prefix from listen 443 ssl;, "
        "destroying the injection marker needed to add QUIC directives. "
        "Use --enable_http3 without --disable_domain_listen, or migrate to "
        "--setup_default + --migrate_to_wildcard and use IP-bound listens."
    )
```

Alternatively, if silent combination must be supported, `_inject_http3_directives` must fall back to matching `listen 443 ssl;` when the IP-bound form is absent:

```python
marker = f"listen {formatted_listen_ip}:443 ssl;"
if marker not in content:
    # Fallback for wildcard-listen configs (disable_domain_listen path)
    marker = "listen 443 ssl;"
```

Either approach must be documented and a test added.

---

### CR-02: Injected `ssl_protocols TLSv1.3;` silently disables TLSv1.2 for TCP/443 on the vhost

**File:** `nginx_set_conf/utils.py:434`

**Issue:** `_inject_http3_directives` injects `ssl_protocols TLSv1.3;` inside the `server {}` block. nginx directive inheritance rules mean that a `server`-scope `ssl_protocols` directive **fully overrides** the `http`-scope `ssl_protocols TLSv1.2 TLSv1.3;` from `NGINX_CONF_TEMPLATE` / the operator's `nginx.conf`. The result is that **TCP/443 connections to that vhost from TLSv1.2 clients are refused** after an `--enable_http3` deployment, even though the operator has not explicitly requested TLSv1.2 removal and the CLI `--help` text makes no mention of this. QUIC does require TLSv1.3, but there is no reason the TCP listen path must be restricted in the same vhost config — QUIC support does not require restricting TCP to TLSv1.3.

The injected line was apparently intended as a "QUIC requires TLSv1.3" annotation, but its placement inside the shared server block means it affects the TCP stack as well. This will silently break connectivity for any client that does not support TLSv1.3 (older Android, Windows 7, some embedded systems) on every vhost that gets `--enable_http3` applied.

**Fix:** Remove `ssl_protocols TLSv1.3;` from the `insert_lines` list. nginx will still negotiate TLSv1.3 for QUIC automatically (QUIC mandates TLSv1.3 at the protocol level; an `ssl_protocols` directive adding TLSv1.2 does not re-enable it for QUIC). If TLSv1.2 restriction is desired as an opt-in, add a separate `--require_tls13` flag with explicit documentation.

```python
# utils.py _inject_http3_directives — remove the ssl_protocols line:
insert_lines = [
    f"    listen {formatted_listen_ip}:443 quic{reuseport_suffix};",
    "    http3 on;",
    "    quic_retry on;",
    # REMOVED: "    ssl_protocols TLSv1.3;",  — this overrides http-scope and blocks TLSv1.2 on TCP
    "    add_header Alt-Svc 'h3=\":443\"; ma=86400' always;",
]
```

---

## Warnings

### WR-01: `validate_all_inputs` discards the cleaned template name; HTTP3 exclusion check uses raw (un-stripped) name

**File:** `nginx_set_conf/validators.py:377-391`

**Issue:** `validate_config_template(config_template)` strips the `ngx_` backward-compat prefix and returns the clean name, but the return value is not captured or used. The HTTP3 exclusion guard on line 386 then tests the **original** `config_template` string against `HTTP3_EXCLUDED_TEMPLATES`:

```python
validate_config_template(config_template)          # return value discarded
if enable_http3 and config_template in HTTP3_EXCLUDED_TEMPLATES:   # uses original
```

`HTTP3_EXCLUDED_TEMPLATES` contains `"fast_report"`, not `"ngx_fast_report"`. Passing `config_template="ngx_fast_report"` with `enable_http3=True` bypasses the HTTP3 exclusion guard entirely. In practice, `execute_commands` subsequently calls `get_config_template("ngx_fast_report")` which returns `""`, causing a silent early return with the message "No valid config template" — so no QUIC directives are emitted, but the error the user receives is wrong and misleading.

**Fix:** Capture the return value from `validate_config_template` and use it for the rest of the checks:

```python
# validators.py validate_all_inputs
clean_template = validate_config_template(config_template)
if enable_http3 and clean_template in HTTP3_EXCLUDED_TEMPLATES:
    ...
```

The same cleaned name should then be passed through `execute_commands` (currently the caller passes the original name).

---

### WR-02: `_quic_reuseport_already_claimed` regex does not match the IPv6 `[::]` wildcard form

**File:** `nginx_set_conf/utils.py:373-374`

**Issue:** The reuseport-detection pattern is:

```python
pattern = re.compile(
    rf"listen\s+(?:{re.escape(ip)}:)?{port}\s+quic\b.*\breuseport"
)
```

With `ip="1.2.3.4"` this matches both `listen 1.2.3.4:443 quic reuseport;` (IP-bound) and `listen 443 quic reuseport;` (IPv4 wildcard, no prefix). However it does **not** match `listen [::]:443 quic default_server reuseport;` — the IPv6 wildcard form emitted by `default_ssl_reject`. In the current deployment (where `default_ssl_reject` always emits **both** the IPv4 wildcard form `listen 443 quic ...` **and** the IPv6 `[::]:443 quic ...` form), the IPv4 form is matched and the function returns `True` correctly.

The risk materialises in a hypothetical future where: (a) only the IPv6 form is present in `conf.d`, or (b) a custom catch-all is written with only IPv6. In that scenario the scanner returns `False`, the new vhost emits `reuseport`, and nginx fails to reload with `bind() to ... quic ... failed (98: address already in use)`.

**Fix:** Extend the pattern to also match the IPv6 wildcard prefix:

```python
pattern = re.compile(
    rf"listen\s+(?:{re.escape(ip)}:|\[::\]:)?{port}\s+quic\b.*\breuseport"
)
```

And add a test case for the `[::]:443 quic default_server reuseport;` line.

---

## Info

### IN-01: `test_http3_false_leaves_output_unchanged` does not test what its docstring claims

**File:** `tests/test_templates.py:432-455`

**Issue:** The test method's docstring states: _"When enable_http3=False, execute_commands output must contain no quic/http3."_ However the test body does not call `execute_commands` at all. It only verifies that the raw template strings (before any substitution) do not already contain `"quic"` or `"http3"`. The stated invariant — that `execute_commands` with `enable_http3=False` produces QUIC-free output — is not exercised. A future template incorrectly containing a `quic` directive would not be caught by this test at all, because the only guard is the raw template scan.

**Fix:** Add a real integration test using `dry_run=True` and capturing `execute_commands` behavior, or rename the test to accurately reflect what it checks:

```python
def test_raw_templates_contain_no_quic_directives(self):
    """Raw templates must not embed quic/http3 directives — injection is runtime-only."""
    for tmpl_name in (...):
        content = TEMPLATES[tmpl_name]
        assert "quic" not in content, ...
        assert "http3" not in content, ...
```

---

### IN-02: Module-level side effect: directory creation and file handler setup at import time

**File:** `nginx_set_conf/nginx_set_conf.py:46-73`

**Issue:** Lines 46–48 call `os.getuid()` and conditionally call `os.makedirs("/var/log/nginx_set_conf", ...)` during **module import**, before any CLI command is invoked. This means that importing `nginx_set_conf.nginx_set_conf` as root (e.g., in tests, or when Python inspects the package) creates a system directory as a side effect. The `RotatingFileHandler` setup on lines 52–64 also opens or creates a log file during import.

`os.getuid()` does not exist on Windows (raises `AttributeError`); while this tool targets Linux servers, it makes the module non-importable on Windows development machines.

**Fix:** Move the log directory creation and handler setup inside `start_nginx_set_conf()` or inside a `main()` guard, so they only execute when the CLI is actually invoked:

```python
def _setup_logging():
    """Configure file logging. Called once from the CLI entry point."""
    log_dir = "/var/log/nginx_set_conf"
    if hasattr(os, "getuid") and os.getuid() == 0:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "nginx_set_conf.log")
    else:
        log_path = "nginx_set_conf.log"
    ...
```

---

_Reviewed: 2026-05-31_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
