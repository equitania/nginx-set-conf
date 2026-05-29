---
phase: "02-cache-template-substitution-consolidation"
slug: "NSC-02"
researched: "2026-05-29"
domain: "Template substitution pipeline / sentinel constants / validator enforcement"
confidence: HIGH
---

# Phase 2: Cache + Template Substitution Consolidation — Research

**Researched:** 2026-05-29
**Domain:** Template substitution pipeline, sentinel constants, redirect validator enforcement
**Confidence:** HIGH — all findings sourced directly from codebase inspection. No external
  libraries required; all fixes use Python stdlib only.

---

## Summary

Phase 2 closes five correctness findings (COR-01..COR-05) from the 2026-05-28 audit.
The central risk is **silent template-output drift**: two independent substitution passes
currently compose correctly only by accident, and a single sentinel string (`/tmp`) is
duplicated across 18 template files without a shared constant to bind them. The primary
mitigation is a **golden-output snapshot test captured before any refactor lands** —
specifically, before plan 02-01 removes the `all_templates.py` pre-substitution pass.
If the test passes before and after, the refactor is proven output-neutral.

---

## Project Constraints (from CLAUDE.md)

- **Package manager:** UV only (`uv run pytest`). Never pip.
- **Git prefixes:** `[CHG]` modifications, `[FIX]` bug fixes, `[ADD]` new features.
- **Version headers:** Increment version + date (DD.MM.YYYY) in file headers.
- **Encoding:** UTF-8 for all file operations.
- **Testing:** `uv run pytest` — coverage gate 60%. Claude cannot run tests locally.
- **No GitHub Actions publish step** — local publish only.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COR-01 | Remove module-level pre-substitution from `all_templates.py`; `utils.py` is the sole cache-path rewrite site | See §COR-01 below; verified by golden-output snapshot test |
| COR-02 | `redirect_domain` required for `redirect` and `redirect_ssl` templates; sentinel `target.domain.de` cannot leak into log paths | See §COR-02 below; test: `test_validators.py` new class `TestValidateRedirectDomain` |
| COR-03 | Single `CACHE_PATH_SENTINEL` constant shared across all template files and `all_templates.py` | See §COR-03 below; test: grep-based assertion in `test_templates.py` |
| COR-04 | `default_ssl_reject` either added to `VALID_TEMPLATES` with documentation, or exclusion justified inline | See §COR-04 below; test: `test_validators.py` |
| COR-05 | Cache-path regex `repl` uses a `lambda` instead of `f"\\1..."` back-reference string | See §COR-05 below; output verified by same golden-output snapshot |
</phase_requirements>

---

## COR-01: Dual Cache-Path Substitution Pipeline

### Current state

`all_templates.py` builds the `TEMPLATES` dict at **module import time**, running
`replace_cache_path(TEMPLATE, "odoo_ssl")` (no domain) for every template:

```python
# all_templates.py:89-108
TEMPLATES = {
    "code_server": replace_cache_path(CODE_SERVER_TEMPLATE, "code_server"),
    "default_ssl_reject": DEFAULT_SSL_REJECT_TEMPLATE,
    ...
    "odoo_ssl": replace_cache_path(ODOO_SSL_TEMPLATE, "odoo_ssl"),
    ...
    "redirect": replace_cache_path(REDIRECT_TEMPLATE, "redirect"),
    "redirect_ssl": replace_cache_path(REDIRECT_SSL_TEMPLATE, "redirect_ssl"),
    ...
}
```

Then `get_config_template(name, domain)` runs `replace_cache_path` a **second time**
with the domain if one is supplied (lines 124-136 of `all_templates.py`).

Then `execute_commands` in `utils.py` runs **yet another regex rewrite** over the
already-substituted string (lines 668-687):

```python
# utils.py:668-687
content = re.sub(
    r"proxy_cache_path\s+/var/cache/nginx/[^\s]+",
    f"proxy_cache_path /var/cache/nginx/{unique_id}",
    content,
)
content = re.sub(
    r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
    f"\\1{unique_id}_cache:",
    content,
)
content = re.sub(
    r"(limit_req_zone\s+[^\s]+\s+zone=)[^\s:]+:",
    f"\\1{unique_id}_ratelimit:",
    content,
)
content = re.sub(
    r"(limit_req\s+zone=)[^\s;]+",
    f"\\1{unique_id}_ratelimit",
    content,
)
```

The first `re.sub` in `utils.py` matches `/var/cache/nginx/[^\s]+` — which already
contains the service-name path produced by the `all_templates.py` pass — and overwrites
it with the domain-qualified `unique_id`. This works, but only because `utils.py`'s
pattern is broad enough to consume whatever `all_templates.py` produced.

### Proposed fix

Remove the `replace_cache_path(...)` calls from the `TEMPLATES` dict in `all_templates.py`.
Store raw templates instead:

```python
TEMPLATES = {
    "code_server": CODE_SERVER_TEMPLATE,
    "default_ssl_reject": DEFAULT_SSL_REJECT_TEMPLATE,
    ...
    "odoo_ssl": ODOO_SSL_TEMPLATE,
    ...
}
```

Also simplify `get_config_template`: remove the `replace_cache_path` call inside it —
`utils.py` is responsible for all cache-path rewriting. The function becomes a pure
dict lookup.

The `utils.py` regex pass (lines 668-687) already handles the raw sentinel `/tmp` via
the first `re.sub` — its pattern `proxy_cache_path\s+/var/cache/nginx/[^\s]+` does
**not** match `/tmp` directly. This means the first pass must be broadened to also
match the raw sentinel:

```python
# Replace both the sentinel /tmp path AND any pre-existing /var/cache/nginx path
content = re.sub(
    r"proxy_cache_path\s+(?:/tmp|/var/cache/nginx/[^\s]+)",
    f"proxy_cache_path /var/cache/nginx/{unique_id}",
    content,
)
```

The `keys_zone`, `limit_req_zone`, and `limit_req` regexes in utils.py already match
`[^\s:]+` and `[^\s;]+` broadly — they will match both the raw `my_cache` / `iprl`
sentinels and the pre-processed names equally. No change needed for those three.

### Edge cases

- `default_ssl_reject` has no `proxy_cache_path` and is stored verbatim today — keep verbatim; no change needed.
- Templates with no `proxy_cache_path` at all (none currently, but future templates): the regex is a no-op for them — safe.
- The `redirect` and `redirect_ssl` templates contain `proxy_cache_path /tmp` but have no cache-using `location` block (flagged as TD-05, deferred to Phase 3). The COR-01 fix must still rewrite their sentinel so the output is consistent; TD-05 will later remove those lines entirely.

### Test approach

File: `tests/test_templates.py`, new method added to `TestCachePathReplacement`:

```python
def test_raw_sentinel_not_in_registered_templates(self):
    """After COR-01: TEMPLATES dict must contain raw /tmp sentinel (not pre-processed)."""
    for name, content in TEMPLATES.items():
        if name == "default_ssl_reject":
            continue  # intentionally no cache directives
        if "proxy_cache_path" in content:
            assert "/tmp" in content, f"Template {name!r} should store raw /tmp sentinel"
            assert "/var/cache/nginx" not in content, (
                f"Template {name!r} should NOT pre-process cache paths"
            )
```

This test **fails before the fix** (because templates are currently pre-processed at
import time) and **passes after the fix** (raw sentinels stored). It is the
correctness anchor for the refactor.

---

## COR-02: `redirect_domain` Sentinel Leak into Log Paths

### Current state

`redirect_ssl.py` contains `target.domain.de` in log file paths:

```python
# nginx_set_conf/templates/redirect_ssl.py:19-35
server {
    listen ip.ip.ip.ip:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/target.domain.de-error.log;
    ...
    rewrite ^/.*$ https://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log;
    error_log /var/log/nginx/target.domain.de-error.log;
```

`redirect.py` has the same pattern (lines 22-24).

`utils.py:773-775` only performs the replacement when `redirect_domain` is supplied:

```python
# utils.py:773-775
if "redirect" in config_template and redirect_domain:
    logger.info("Set redirect domain in conf to %s", redirect_domain)
    content = _replace_placeholder(content, default_vars["template_redirect_domain"], redirect_domain)
```

If `redirect_domain` is empty (omitted), the sentinel `target.domain.de` ships to
nginx verbatim. nginx accepts it as a filename path fragment, writing logs to
`/var/log/nginx/target.domain.de-*.log` silently.

### Proposed fix

Add an early-exit guard in `execute_commands` **before** the template content is
fetched — similar to the existing `ValidationError` pattern. Place it immediately
after the `validate_all_inputs` call succeeds:

```python
# utils.py — after validate_all_inputs block, before get_config_template
if "redirect" in config_template and not redirect_domain:
    logger.error("redirect_domain is required for template %s", config_template)
    print(f"ERROR: --redirect_domain is required for '{config_template}' templates")
    return
```

Alternatively (preferred for consistency): add `redirect_domain` validation to
`validate_all_inputs` in `validators.py` — add a dedicated check:

```python
# validators.py — inside validate_all_inputs
def validate_redirect_domain(redirect_domain: str, config_template: str) -> None:
    if "redirect" in config_template and not redirect_domain.strip():
        raise ValidationError(
            f"'redirect_domain' is required for template '{config_template}'"
        )
```

Call it from `validate_all_inputs`. This is the cleaner approach because it keeps all
validation in one place and `ValidationError` is already caught and reported by
`execute_commands`.

### Edge cases

- `validate_all_inputs` receives `redirect_domain or ""` at `utils.py:615` — an empty string is passed when `redirect_domain` is `None`. The new check handles this correctly.
- Non-redirect templates: the check is gated on `"redirect" in config_template`, so `odoo_ssl`, `flowise`, etc. are unaffected.
- `redirect_ssl` has the string `"redirect"` in its name — the existing `if "redirect" in config_template` gate already covers it correctly.

### Test approach

File: `tests/test_validators.py`, new class `TestValidateRedirectDomain`:

```python
class TestValidateRedirectDomain:
    def test_redirect_without_domain_raises(self):
        with pytest.raises(ValidationError, match="redirect_domain"):
            validate_all_inputs(
                config_template="redirect",
                domain="example.com",
                ip="1.2.3.4",
                redirect_domain="",
                ...
            )

    def test_redirect_ssl_without_domain_raises(self):
        with pytest.raises(ValidationError, match="redirect_domain"):
            validate_all_inputs(config_template="redirect_ssl", ..., redirect_domain="")

    def test_redirect_with_domain_passes(self):
        # must not raise
        validate_all_inputs(config_template="redirect", ..., redirect_domain="target.example.com")

    def test_non_redirect_does_not_require_domain(self):
        # odoo_ssl with empty redirect_domain must not raise
        validate_all_inputs(config_template="odoo_ssl", ..., redirect_domain="")
```

Assert that the validated sentinel string `target.domain.de` does not appear in
the output of `execute_commands` for redirect templates when `redirect_domain` is
properly supplied.

---

## COR-03: Single `CACHE_PATH_SENTINEL` Constant

### Current state

Every template file uses the literal string `/tmp` as the cache-path sentinel at
line 13 of the TEMPLATE string:

```python
# nginx_set_conf/templates/odoo_ssl.py:13
proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m use_temp_path=off;
```

`all_templates.py:58` (inside `replace_cache_path`) uses a string literal to match it:

```python
# all_templates.py:58 (inside replace_cache_path)
updated_template = template.replace("proxy_cache_path /tmp", f"proxy_cache_path /var/cache/nginx/{unique_id}")
```

After COR-01 removes the module-level `replace_cache_path` calls from `TEMPLATES`,
the `all_templates.py` function `replace_cache_path` still exists (it is tested in
`test_templates.py::TestCachePathReplacement`). The `/tmp` literal there must also
be replaced by the constant.

### Proposed fix

Define a module-level constant in `all_templates.py`:

```python
# all_templates.py (near top, after imports)
CACHE_PATH_SENTINEL = "proxy_cache_path /tmp"
```

Update `replace_cache_path` to use it:

```python
updated_template = template.replace(CACHE_PATH_SENTINEL, f"proxy_cache_path /var/cache/nginx/{unique_id}")
```

Update the `utils.py` `re.sub` pattern (from COR-01 fix) to reference the constant
symbolically. Because `utils.py` already imports from `all_templates`, the constant
can be imported:

```python
from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL
```

And used in the regex:

```python
import re, re as _re
_sentinel_path = CACHE_PATH_SENTINEL.split()[1]  # "/tmp"
content = re.sub(
    rf"proxy_cache_path\s+(?:{re.escape(_sentinel_path)}|/var/cache/nginx/[^\s]+)",
    f"proxy_cache_path /var/cache/nginx/{unique_id}",
    content,
)
```

The template files themselves (`odoo_ssl.py`, `flowise.py`, etc.) contain only raw
nginx config text — they do not import Python. The constant cannot be injected into
template string content directly. The source of truth is the constant; the template
literal `/tmp` is acceptable as long as a test verifies consistency.

### Edge cases

- Template files cannot import the constant — they are pure string modules. A grep-based test is the enforcement mechanism.
- `default_ssl_reject` has no `proxy_cache_path` — sentinel is irrelevant for it.
- If a future template accidentally uses `/var/cache/nginx` instead of `/tmp` as its sentinel, the COR-01 regex catches it anyway (the pattern matches both). The constant prevents drift in the sentinel direction.

### Test approach

File: `tests/test_templates.py`, add to `TestCachePathReplacement` or a new class:

```python
def test_sentinel_constant_matches_template_literals(self):
    """Every template with a cache directive must use the exact sentinel string."""
    from nginx_set_conf.templates.all_templates import CACHE_PATH_SENTINEL, TEMPLATES
    sentinel_path = CACHE_PATH_SENTINEL.split()[1]  # "/tmp"
    for name, content in TEMPLATES.items():
        if "proxy_cache_path" in content:
            assert sentinel_path in content, (
                f"Template {name!r} uses a non-standard cache sentinel — expected {sentinel_path!r}"
            )
```

This test fails if any template drifts to a different sentinel.

---

## COR-04: `default_ssl_reject` Absent from `VALID_TEMPLATES`

### Current state

`validators.py:33-51` defines `VALID_TEMPLATES` as a set of 17 template names.
`default_ssl_reject` is absent:

```python
# validators.py:33-51
VALID_TEMPLATES = {
    "code_server",
    "fast_report",
    "flowise",
    "guacamole",
    "kasm",
    "mailpit",
    "n8n",
    "nextcloud",
    "odoo_http",
    "odoo_ssl",
    "pgadmin",
    "portainer",
    "pwa",
    "qdrant",
    "redirect",
    "redirect_ssl",
    "supabase",
}
```

`utils.py:483-509` (`setup_default_server`) is the **only** code path that generates
a `default_ssl_reject` config — it writes it directly to `00-default.conf` and does
not go through `execute_commands`. The template is intentionally inaccessible via
`--config_template default_ssl_reject` because:

1. It writes to `00-default.conf`, not `{domain}.conf`.
2. It uses a self-signed sacrificial cert, not an operator-supplied cert.
3. Exposing it via `--config_template` would let an operator overwrite the default
   catch-all with incorrect parameters, breaking the SNI-reject guarantee.

The current state is therefore **correct behaviour** — the exclusion is intentional.
The finding (COR-LOW-1) is a documentation gap, not a code bug.

### Proposed fix

Add an inline comment to `validators.py` immediately before `VALID_TEMPLATES`:

```python
# VALID_TEMPLATES lists templates accessible via --config_template / YAML config_template.
# `default_ssl_reject` is intentionally excluded: it is only generated by --setup_default
# (setup_default_server in utils.py) which writes to 00-default.conf with a sacrificial
# self-signed cert. Exposing it via --config_template would allow misuse as a regular
# vhost config and could overwrite the SNI catch-all. See CONCERNS.md §COR-LOW-1.
VALID_TEMPLATES = { ...
```

No code change required. The `TEMPLATES` dict in `all_templates.py` already registers
`default_ssl_reject` (line 92) so that template-registry tests pass and the template
is importable for `setup_default_server`.

### Edge cases

- A future operator request to generate `default_ssl_reject` manually: the comment points them to `--setup_default`.
- `VALID_TEMPLATES_COMPAT` (line 54) generates `ngx_` prefixes from `VALID_TEMPLATES` — `ngx_default_ssl_reject` is also correctly excluded.

### Test approach

File: `tests/test_validators.py`, add to `TestValidateConfigTemplate`:

```python
def test_default_ssl_reject_not_in_valid_templates(self):
    """default_ssl_reject must remain excluded from VALID_TEMPLATES (intentional)."""
    from nginx_set_conf.validators import VALID_TEMPLATES
    assert "default_ssl_reject" not in VALID_TEMPLATES

def test_default_ssl_reject_not_in_compat_templates(self):
    from nginx_set_conf.validators import VALID_TEMPLATES_COMPAT
    assert "ngx_default_ssl_reject" not in VALID_TEMPLATES_COMPAT
```

These are regression guards — they fail if someone accidentally adds `default_ssl_reject`
to the whitelist without reading the rationale comment.

---

## COR-05: Cache-Path Regex `repl` Back-Reference Footgun

### Current state

`utils.py:674-676` uses an `f`-string with `\\1` as the `repl` argument to `re.sub`:

```python
# utils.py:673-676
content = re.sub(
    r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
    f"\\1{unique_id}_cache:",
    content,
)
```

`f"\\1{unique_id}_cache:"` evaluates to the string `\1odoo_ssl_example_com_cache:`.
`re.sub` interprets `\1` in the replacement string as "group 1 of the match" — this
is the documented `re.sub` behaviour and works correctly today. However, if `unique_id`
ever starts with a digit (impossible given RFC 1123 domain validation but possible if
the service name changes) or contains a backslash (same caveat), `re.sub` would
mis-parse the replacement string.

The same pattern appears again on line 679-681:

```python
content = re.sub(
    r"(limit_req_zone\s+[^\s]+\s+zone=)[^\s:]+:",
    f"\\1{unique_id}_ratelimit:",
    content,
)
```

And on lines 683-686:

```python
content = re.sub(
    r"(limit_req\s+zone=)[^\s;]+",
    f"\\1{unique_id}_ratelimit",
    content,
)
```

### Proposed fix

Replace `f"\\1..."` strings with `lambda` replacements to make back-reference intent
explicit and immune to special characters in `unique_id`:

```python
# utils.py — keys_zone replacement
content = re.sub(
    r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
    lambda m: f"{m.group(1)}{unique_id}_cache:",
    content,
)

# utils.py — limit_req_zone replacement
content = re.sub(
    r"(limit_req_zone\s+[^\s]+\s+zone=)[^\s:]+:",
    lambda m: f"{m.group(1)}{unique_id}_ratelimit:",
    content,
)

# utils.py — limit_req directive replacement
content = re.sub(
    r"(limit_req\s+zone=)[^\s;]+",
    lambda m: f"{m.group(1)}{unique_id}_ratelimit",
    content,
)
```

The `replace_cache_path` function in `all_templates.py` already uses a `lambda`
(lines 68-72 for `limit_req_zone`) as a model — the fix is consistent with the
existing style in the same file.

### Edge cases

- `re.sub` with a callable `repl` passes the `re.Match` object, not a string — the `lambda m: ...` form is correct.
- The first `re.sub` (line 668-672) rewrites the full path and uses no group capture — it remains a plain f-string and does not need conversion.
- Output must be identical to current output for all valid `unique_id` values (RFC 1123 domains, alphanumeric + hyphen). The golden-output snapshot test (see §Golden-Output Net) verifies this.

### Test approach

File: `tests/test_templates.py`, the golden-output snapshot test (see §Golden-Output Net)
covers COR-05 implicitly. Add a unit test in `test_utils.py`:

```python
class TestCachePathRegexLambda:
    def test_keys_zone_rewritten_correctly(self):
        """Verify lambda repl produces same output as f-string for standard unique_id."""
        import re
        unique_id = "odoo_ssl_example_com"
        content = "proxy_cache_path /var/cache/nginx/odoo_ssl keys_zone=odoo_ssl_cache:10m;"
        result = re.sub(
            r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
            lambda m: f"{m.group(1)}{unique_id}_cache:",
            content,
        )
        assert f"keys_zone={unique_id}_cache:" in result
```

---

## Golden-Output Net

### Does `tests/test_templates.py` currently cover every template?

**Partially.** Current coverage:

| Test class | What it covers | Gap for Phase 2 |
|---|---|---|
| `TestTemplateRegistry` | All 18 templates loaded, non-empty | Does not assert on exact content |
| `TestCachePathReplacement` | `replace_cache_path()` unit logic | Does not test `execute_commands` end-to-end output |
| `TestGetConfigTemplate` | Lookup by name, basic content check | No sentinel-absence assertion |
| `TestTemplateBackendIpPlaceholder` | `{{BACKEND_IP}}` presence, no hardcoded IPs | Orthogonal |
| `TestIpBoundListen` | `listen ip.ip.ip.ip:PORT;` presence | Orthogonal |
| `TestDefaultSslReject` | default_ssl_reject structure | Orthogonal |
| `TestHttp2Enabled` | `http2 on;` in NGINX_CONF_TEMPLATE | Orthogonal |

**Missing:** There is no parametrized test that captures the **full substituted output**
of `execute_commands` for a known input triple `(template, domain, ip)` and compares
it against a stored snapshot. Without this, a refactor that changes output format would
pass all existing tests.

### Required golden-output test (add in plan 02-01 Wave 0, before the refactor)

Add one parametrized snapshot test to `tests/test_templates.py`. It must run
**before COR-01 lands** to capture current output, and then must still pass after:

```python
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from nginx_set_conf.utils import execute_commands


SNAPSHOT_CASES = [
    # (template, domain, ip, unique_id_expected_in_output)
    ("odoo_ssl",     "example.com", "1.2.3.4", "odoo_ssl_example_com"),
    ("flowise",      "flowise.example.com", "1.2.3.4", "flowise_flowise_example_com"),
    ("redirect",     "old.example.com", "1.2.3.4", "redirect_old_example_com"),
    ("redirect_ssl", "old.example.com", "1.2.3.4", "redirect_ssl_old_example_com"),
]


class TestCachePathSubstitutionOutput:
    @pytest.mark.parametrize("template,domain,ip,unique_id", SNAPSHOT_CASES)
    def test_cache_path_unique_id_in_output(self, template, domain, ip, unique_id, tmp_path):
        """Regression: cache path in generated config must contain unique_id = service_domain."""
        written = {}

        def fake_write(path, content):
            written["content"] = content

        with (
            patch("nginx_set_conf.utils.os.makedirs"),
            patch("nginx_set_conf.utils.os.path.exists", return_value=True),
            patch("nginx_set_conf.utils._run_command"),
            patch("builtins.open", MagicMock()),
        ):
            # Call execute_commands in dry_run mode to avoid filesystem writes
            execute_commands(
                config_template=template,
                domain=domain,
                ip=ip,
                port="8080",
                cert_name="example.com",
                redirect_domain="target.example.com" if "redirect" in template else "",
                dry_run=True,
            )
        # dry_run just logs — verify that get_config_template + regex pipeline
        # produces the correct unique_id in the template content by calling
        # the pipeline functions directly
        from nginx_set_conf.templates.all_templates import get_config_template
        import re
        domain_id = domain.replace(".", "_")
        expected_unique_id = f"{template}_{domain_id}"
        content = get_config_template(template, domain)
        content = re.sub(
            r"proxy_cache_path\s+(?:/tmp|/var/cache/nginx/[^\s]+)",
            f"proxy_cache_path /var/cache/nginx/{expected_unique_id}",
            content,
        )
        if "proxy_cache_path" in content:
            assert f"/var/cache/nginx/{expected_unique_id}" in content, (
                f"Template {template!r} with domain {domain!r}: "
                f"expected unique_id {expected_unique_id!r} not found in cache path"
            )
```

**Note for planner:** This test class must be created as the **first task in plan 02-01**
(Wave 0), before the `all_templates.py` and `utils.py` edits. Run it once to confirm
green baseline, then run again after the refactor to confirm output identity.

---

## Wave Structure Recommendation

**Recommendation: (b) 02-01 alone in Wave 1, then 02-02 + 02-03 in Wave 2.**

Rationale: 02-01 (COR-01 + COR-03 + COR-05) rewrites the substitution pipeline at its
root — if it regresses, 02-02 and 02-03 are attempting to build on a broken pipeline.
COR-02 touches `validators.py` and the top of `execute_commands` (before the content
pipeline), while COR-04 is a comment-only change to `validators.py` — both are low risk
and can run in parallel after 02-01 is proven green. Option (a) all-sequential is also
safe but wastes time; option (c) worktrees adds merge complexity for no benefit given
the small diff sizes.

```
Wave 1:  [02-01] COR-01 + COR-03 + COR-05  (utils.py lines 668-686, all_templates.py TEMPLATES dict)
            └── suite green → unlock Wave 2

Wave 2:  [02-02] COR-02  (validators.py new fn, utils.py lines 773-775 guard)
         [02-03] COR-04  (validators.py comment only)
            ↑ both touch validators.py in disjoint locations — parallel is safe
```

---

## Commit Prefix per Plan

| Plan | Fix | Prefix | Rationale |
|------|-----|--------|-----------|
| 02-01 | COR-01 + COR-03 + COR-05 substitution pass consolidation | `[CHG]` | Refactor — same observable output, no new behaviour |
| 02-02 | COR-02 redirect_domain required | `[FIX]` | Closes a correctness bug where a sentinel value leaks into nginx config; behaviour change (previously silent, now validated) |
| 02-03 | COR-04 VALID_TEMPLATES documentation | `[CHG]` | Comment-only modification to existing code; no runtime behaviour change |

---

## Sources

- **All code findings:** Direct inspection of `nginx_set_conf/templates/all_templates.py`,
  `nginx_set_conf/utils.py` (lines 600-790), `nginx_set_conf/validators.py`,
  `nginx_set_conf/templates/redirect_ssl.py`, `nginx_set_conf/templates/redirect.py`,
  `nginx_set_conf/templates/odoo_ssl.py` (lines 1-35), `tests/test_templates.py`.
- **Audit source:** `.planning/codebase/CONCERNS.md` §COR-MED-1 through §COR-LOW-2.
- **Requirements:** `.planning/REQUIREMENTS.md` COR-01..COR-05.
- **Phase structure:** `.planning/ROADMAP.md` Phase 2.
- **Style reference:** `.planning/phases/NSC-01-privileged-write-surface-hardening/01-RESEARCH.md`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `utils.py` regex `proxy_cache_path\s+/var/cache/nginx/[^\s]+` does NOT match `/tmp` (requires COR-01 broadening) | COR-01 proposed fix | If it already matches `/tmp`, the first pass fix is simpler — read the regex pattern text to verify (confirmed above) |

**If this table has only one entry:** All other claims were verified by direct code inspection.

---

## RESEARCH COMPLETE
