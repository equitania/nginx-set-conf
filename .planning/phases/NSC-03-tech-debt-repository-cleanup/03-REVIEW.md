---
phase: NSC-03-tech-debt-repository-cleanup
reviewed: 2026-05-29T10:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - nginx_set_conf/__init__.py
  - nginx_set_conf/nginx_set_conf.py
  - nginx_set_conf/templates/redirect.py
  - nginx_set_conf/templates/redirect_ssl.py
  - nginx_set_conf/utils.py
  - nginx_set_conf/config_templates.py (DELETED)
  - tests/test_config_templates_removed.py
  - tests/test_templates.py
findings:
  critical: 1
  warning: 2
  info: 3
  total: 6
status: issues_found
---

# Phase NSC-03: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 03 retired the deprecated `config_templates.py` shim, repointed all imports to
`nginx_set_conf.templates.all_templates`, stripped orphaned `proxy_cache_path` /
`limit_req_zone` directives from the redirect templates, and added a `cert_key` prompt
to the interactive wizard.

The import repointing is correct and clean. The shim deletion is verified by the new
regression guard in `test_config_templates_removed.py`. The directive stripping from
redirect templates is correct and the absence tests lock the invariant in.

One **critical bug** was introduced by the `cert_key` wizard prompt: it uses
`retrieve_valid_input()`, which loops until the user provides a non-empty string, making
it impossible for the interactive user to accept the default empty value (Let's Encrypt
auto-generate). This directly contradicts the prompt text that says "leave empty for
Let's Encrypt auto-generate." Two additional warnings relate to the `redirect.py` template
retaining an `upstream` block with a `{{BACKEND_IP}}` placeholder that is never used by
the redirect server block, and a silent no-op when `redirect_domain` is omitted in the
interactive path.

---

## Critical Issues

### CR-01: cert_key interactive prompt loops forever on empty input — Let's Encrypt path is unreachable

**File:** `nginx_set_conf/nginx_set_conf.py:432`

**Issue:**
The new cert_key prompt uses `retrieve_valid_input()`, which only returns when the user
types a non-empty string:

```python
# utils.py lines 180-188 — the contract
while True:
    user_input = input(message)
    user_input = user_input[:_MAX_INPUT_LENGTH]
    if user_input:          # empty string → loop again, never returns
        return user_input
```

The wizard prompt is:

```python
cert_key = retrieve_valid_input(
    "Path to certificate key file (leave empty for Let's Encrypt auto-generate)\n"
)
```

A user who presses Enter to accept the LE default will be prompted again and again,
with no way to exit the loop other than Ctrl+C (SIGINT), which the tool does not
handle — resulting in an unhandled `KeyboardInterrupt` traceback. The only path that
previously used an empty `cert_key` (Let's Encrypt) is now permanently blocked in
interactive mode.

The bug is a correctness regression: `execute_commands()` relies on `cert_key == ""`
to take the LE branch (lines 736–746 of utils.py):

```python
if cert_key:
    # Self-signed / purchased — uses cert_key as the key path
    ...
else:
    # Let's Encrypt — cert_key is derived from cert_name
    cert_key = cert_name
```

After this change the LE branch is unreachable from the interactive wizard.

**Fix:** Replace `retrieve_valid_input` (which enforces non-empty) with a plain
`input()` call and strip the result:

```python
cert_key = input(
    "Path to certificate key file (leave empty for Let's Encrypt auto-generate)\n"
).strip()[:4096]
```

Alternatively, extract a new helper `retrieve_optional_input(prompt: str) -> str`
that returns the empty string immediately on Enter, and use it for all optional
fields in the wizard (cert_key, pollport, grpcport, redirect_domain, auth_file,
allowed_ips, disable_domain_listen, custom_target_path).

---

## Warnings

### WR-01: redirect.py retains an upstream block with {{BACKEND_IP}} that no server block uses

**File:** `nginx_set_conf/templates/redirect.py:7-9`

**Issue:**
The `redirect` template has an `upstream` block that survived the directive removal:

```nginx
upstream server.domain.de {
    server {{BACKEND_IP}} weight=1 fail_timeout=0;
}
```

The HTTP server block in the same template contains only a `rewrite` directive —
it does not `proxy_pass` to this upstream. The `{{BACKEND_IP}}` placeholder will
be substituted by `execute_commands()` (line 733 of utils.py) with the effective
backend IP, resulting in a live nginx config that declares an unreferenced upstream
block. Nginx does not error on an unused upstream, but it wastes memory and is
misleading: operators reading the generated config will expect proxy_pass semantics
that are absent. The `upstream` block is carried forward from a prior template
version that did proxy. The plan's acceptance criteria assert `upstream` is still
present (test `test_redirect_core_functionality_intact`) which means this test will
incorrectly pass while the upstream block serves no purpose.

**Fix:** Remove the `upstream server.domain.de { ... }` block from `redirect.py`
(not `redirect_ssl.py`, which has no such block). Update the corresponding test
assertion to check for `rewrite` only, not `upstream`:

```python
def test_redirect_core_functionality_intact(self):
    content = get_config_template("redirect")
    assert "rewrite" in content
    # upstream removed — redirect vhost does not proxy
```

**Severity rationale:** Not a crash or security issue, but results in a generated
nginx config that declares an unreferenced upstream block, wastes shared memory,
and leaves an unresolvable `{{BACKEND_IP}}` placeholder in the emitted config if
the operator does not supply `--backend_ip`. Classified as Warning rather than
Critical because nginx silently ignores an unreferenced upstream.

---

### WR-02: Interactive wizard prompts for redirect_domain unconditionally but redirect_domain substitution is gated on config_template

**File:** `nginx_set_conf/nginx_set_conf.py:435`

**Issue:**
In the interactive else-branch the wizard always asks for `redirect_domain`:

```python
redirect_domain = retrieve_valid_input("Redirect domain\n")
```

Because `retrieve_valid_input` loops on empty input, any user selecting a
non-redirect template (e.g., `odoo_ssl`) must type some value for redirect_domain
before the wizard proceeds. That value is then silently discarded by
`execute_commands()` whose guard reads:

```python
if "redirect" in config_template and redirect_domain:
    content = _replace_placeholder(...)
```

The user is forced to supply a nonsensical value that has no effect. This was a
pre-existing issue, but it is now materially worsened by the addition of
`cert_key` using the same function with the same looping behavior.

**Fix:** Use `retrieve_optional_input()` (see CR-01 fix) for all wizard fields
that are optional by design: `cert_key`, `pollport`, `grpcport`, `redirect_domain`,
`auth_file`, `allowed_ips`, `disable_domain_listen`, and `custom_target_path`.
Fields that are truly required (`config_template`, `ip`, `domain`, `port`,
`cert_name`) can keep `retrieve_valid_input`.

---

## Info

### IN-01: `__version__` self-assignment is a no-op

**File:** `nginx_set_conf/nginx_set_conf.py:74`

**Issue:**
```python
from . import __version__
...
__version__ = __version__   # line 74
```
The assignment overwrites the module attribute with itself. It was presumably
intended to re-export the version, but the `from . import __version__` already
makes it available in module scope. The line is harmless but confusing.

**Fix:** Delete line 74. The `from . import __version__` on line 25 is sufficient.

---

### IN-02: `redirect_ssl` template rewrite in the HTTP block uses `http://` not `https://`

**File:** `nginx_set_conf/templates/redirect_ssl.py:16`

**Issue:**
The HTTP server block (port 80) rewrites to `http://target.domain.de$request_uri?`:

```nginx
server {
    listen ip.ip.ip.ip:80;
    ...
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
}
```

This sends the client to the plain-HTTP URL of the redirect target, not to its HTTPS
equivalent. When the intent is to redirect to an HTTPS destination, the 301 from
port 80 should point at `https://`. The port-443 block correctly uses `https://`.

This is a pre-existing issue in the template, not introduced by this phase. It is
raised here because it is visible in the changed file and may affect operators.

**Fix:** Change line 16 to:

```nginx
    rewrite ^/.*$ https://target.domain.de$request_uri? permanent;
```

---

### IN-03: `test_config_templates_removed.py` imports the module under test at function body scope, bypassing pytest collection isolation

**File:** `tests/test_config_templates_removed.py:26`

**Issue:**
```python
def test_nginx_set_conf_module_imports_successfully(self):
    import nginx_set_conf.nginx_set_conf  # noqa: F401
```

If `nginx_set_conf.nginx_set_conf` was already imported by a previous test (Python
caches it in `sys.modules`), this test trivially passes even if the module is broken
after the import cache is cleared in an isolated subprocess. The test will not catch
a regression where a new import error is introduced after initial import. This is a
test-quality concern, not a production bug.

**Fix:** Use `importlib.import_module` consistently (as done in
`test_config_templates_module_not_importable`) for deterministic behavior, or add a
`importlib.reload()` guard. For the ModuleNotFoundError test, the current approach
is fine because `importlib.import_module` bypasses cache on error; the success test
could similarly be written:

```python
import sys
import importlib

def test_nginx_set_conf_module_imports_successfully(self):
    mod_name = "nginx_set_conf.nginx_set_conf"
    sys.modules.pop(mod_name, None)
    importlib.import_module(mod_name)  # must not raise
```

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
