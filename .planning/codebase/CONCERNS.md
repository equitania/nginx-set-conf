# Codebase Concerns

**Analysis Date:** 2026-05-28

---

## Re-Audit: Phase 4 Complete (29.05.2026)

All HIGH and MEDIUM findings closed by Phases 1–4 of the v1.12 roadmap.
Zero HIGH / Zero MEDIUM open findings.
LOW findings: all closed (see phase summaries above).
Open Questions: both resolved (Q-01, Q-02).

---

## Security Concerns

**[HIGH] nginx restart fires BEFORE config validation in the normal deploy path**
*(CLOSED — Phase 1 / HIGH-1 — pre-reload `nginx -t` gate + graceful `systemctl reload`)*
- The main `execute_commands` flow writes `{domain}.conf` to `/etc/nginx/conf.d/` then
  the caller in `nginx_set_conf.py` runs `systemctl restart nginx.service` at line 453,
  followed by `nginx -t` at line 457 — i.e., **restart comes first**.
- A malformed config (e.g., an unresolved `{{PORT}}` placeholder due to a missing CLI arg)
  will crash the live nginx process before the test gate fires. Traffic drops.
- Files: `nginx_set_conf/nginx_set_conf.py:451-457`, `nginx_set_conf/utils.py:731-735`
- What to investigate: Swap order to `nginx -t` → `systemctl reload` (not restart); abort
  if `-t` fails and leave the old config in place.

**[HIGH] Template injection via `auth_file` path written verbatim into nginx config**
*(CLOSED — Phase 1 / HIGH-2 — `validate_auth_file` constrains to /etc/nginx/, rejects /etc/nginx/conf.d/)*
- `auth_file` passes `_AUTH_FILE_RE` validation (`^[a-zA-Z0-9._/\-]+$`) and the
  `_reject_path_traversal` check, then is written directly into the nginx config with
  `auth_basic_user_file {auth_file};`. A value like `/etc/nginx/conf.d/evil.conf` is
  syntactically valid and would inject an additional `include`-equivalent directive if
  the file happens to look like an nginx snippet. The validator allows `/` freely.
- Files: `nginx_set_conf/validators.py:19`, `nginx_set_conf/utils.py:706-713`
- What to investigate: Constrain `auth_file` to a known base directory (e.g., must start
  with `/etc/nginx/`) or refuse embedded slashes entirely.

**[HIGH] Domain value used directly as filesystem filename without sanitisation**
*(CLOSED — Phase 1 / HIGH-3 — `_safe_conf_filename` rewrites `*.` prefix to `_wildcard.`)*
- `target_file = os.path.join(server_path, f"{domain}.conf")` at `utils.py:731`. While
  `validate_domain` enforces RFC 1123 (no slashes, no `..`), the domain is then used
  verbatim as a filename. A wildcard domain like `*.example.com` passes the regex
  (`_DOMAIN_RE` allows `\*.` prefix) and would produce a filename `*.example.com.conf`,
  which is a shell glob — nginx itself would reject it but the file write would corrupt
  the directory listing.
- Files: `nginx_set_conf/validators.py:13-16`, `nginx_set_conf/utils.py:731`
- What to investigate: Strip or refuse wildcard domains when generating output filenames.
  Alternatively reject wildcards in `validate_domain` since nginx doesn't use them in
  `server_name` the same way.

**[MEDIUM] `target_path` from YAML config bypasses path-traversal check**
*(CLOSED — Phase 1 / SEC-01 — `.strip()` added before path checks; whitespace edge case tested)*
- In `nginx_set_conf.py:364`, `yaml_target_path = str(yaml_config.get("target_path", ""))`.
  This value is passed to `execute_commands` which calls `validate_all_inputs`, and
  `validate_target_path` does check for `".."`. However the YAML loader returns the
  raw Python value — no trimming of whitespace before the `".." in target_path` string
  check. A YAML value of `"  ../etc"` (leading space) would pass the naive `".." in` check
  at `validators.py:165` because `".."` is not literally in `"  ../etc"`. (It is, in fact —
  this is safe — but the comment at `validators.py:165-168` says they rely on the raw
  string, not `os.path.normpath`, for exactly this reason. Verify the edge case with
  leading whitespace and YAML anchors.)
- Files: `nginx_set_conf/validators.py:162-169`, `nginx_set_conf/nginx_set_conf.py:363-365`
- What to investigate: Add `.strip()` before path checks; add a test with leading-space
  path values from YAML.

**[MEDIUM] Backup symlink check in `backup_configuration` does not apply to `shutil.copytree`**
*(CLOSED — Phase 1 / SEC-02 — `shutil.copytree(src, dst, symlinks=False)` + source symlink check)*
- `config_verification.py:437-439` explicitly checks that the backup target for
  `nginx.conf` is not a symlink before copying. But `shutil.copytree` at line 444
  copies the entire `nginxconfig.io/` directory without equivalent symlink rejection on
  the destination. On a compromised system where `/etc/nginx/nginxconfig.io` is a symlink
  to an attacker-controlled path, `copytree` would follow and read from that path (it
  follows symlinks in the source by default). This is a read-side risk, not write.
- Files: `nginx_set_conf/config_verification.py:436-444`
- What to investigate: Use `shutil.copytree(src, dst, symlinks=False)` and add a source
  symlink check for the directory itself.

**[MEDIUM] Self-signed key written at world-default umask, chmod called via subprocess**
*(CLOSED — Phase 1 / SEC-03 — key file pre-created with `open(key_path, "w", mode=0o600)` before openssl)*
- `setup_default_server` generates the private key at `key_path` via `openssl req` (the
  key lands at whatever the process umask is), then calls `_run_command(["chmod", "600",
  key_path])` as a separate subprocess after the fact. A narrow window exists where the
  key file is readable with looser permissions. Running as root (typical for this tool)
  means umask is usually 022, so the key is 644 for that window.
- Files: `nginx_set_conf/utils.py:490-497`
- What to investigate: Pre-create the key file with `open(key_path, "w", mode=0o600)`
  before invoking openssl, or set `umask(0o077)` around the openssl call.

**[LOW] `retrieve_valid_input` interactive path has no input length cap**
*(CLOSED — Phase 1 / SEC-04 — iterative loop replaces recursion; 512-char input cap added; documented in --help)*
- The interactive fallback (`nginx_set_conf.py:415-433`) calls `retrieve_valid_input`
  which accepts arbitrarily long input. A non-interactive stdin pipe could supply a
  100 KB domain string and it would propagate to `validate_domain`, which does check
  the 253-char limit, but the stack is recursive (unbounded recursion on empty input).
- Files: `nginx_set_conf/nginx_set_conf.py:415`, `nginx_set_conf/utils.py:138-151`
- What to investigate: Convert `retrieve_valid_input` to an iterative loop; add a max
  input length guard.

---

## Correctness Concerns

**[HIGH] `nginx -t` is called after `systemctl restart` — config errors cause outage**
*(CLOSED — Phase 1 / HIGH-1 — same fix as Security HIGH-1 above; see Phase 1 summary)*
- Already described under Security but also a correctness issue: the current sequence
  writes config → restarts nginx (potentially crashing it) → runs `nginx -t` after the
  damage is done. The `-t` output is informational at that point.
- Files: `nginx_set_conf/nginx_set_conf.py:453-457`
- What to investigate: Confirm intent and either add a pre-write `nginx -t` gate or use
  `systemctl reload` (graceful) instead of `restart` (disruptive).

**[MEDIUM] Dual cache-path replacement pipeline — two separate mechanisms can produce mismatch**
*(CLOSED — Phase 2 / COR-01 — consolidated to single domain-qualified substitution pass in utils.py; module-level pre-substitution in all_templates.py removed)*
- Cache paths are rewritten twice: once in `all_templates.py:replace_cache_path` (on
  module import, using service name only), and again in `utils.py:620-638` using regex
  on the already-rewritten string (domain-qualified). The `utils.py` regex replaces
  `proxy_cache_path /var/cache/nginx/[^\s]+` broadly — if `replace_cache_path` in
  `all_templates.py` already produced `/var/cache/nginx/odoo_ssl`, the regex in
  `utils.py` will silently overwrite it with the correct domain-specific path. This works
  by accident: the two substitutions compose correctly only if the regex pattern stays in
  sync with the `all_templates.py` output format.
- Files: `nginx_set_conf/templates/all_templates.py:56-82`, `nginx_set_conf/utils.py:620-638`
- What to investigate: Consolidate to a single authoritative substitution pass; remove
  the module-level pre-substitution from `all_templates.py` (it is redundant now that
  `utils.py` does a domain-qualified pass).

**[MEDIUM] `redirect_ssl` template: `target.domain.de` in log paths is only replaced when `"redirect" in config_template`**
*(CLOSED — Phase 2 / COR-02 — `redirect_domain` made required for redirect/redirect_ssl templates; early-exit validator added)*
- `utils.py:726` gates the `target_domain` replacement on `if "redirect" in config_template`.
  That is satisfied for both `redirect` and `redirect_ssl`. The replacement in
  `_replace_placeholder` does a simple string replace of `"target.domain.de"` across
  the whole template — including the `access_log` and `error_log` directives at
  `redirect_ssl.py:20-21,34-35` which contain `target.domain.de` literally. If
  `redirect_domain` is empty (omitted from CLI), the replacement is skipped and the
  sentinel value `target.domain.de` lands in the nginx config — nginx will accept it as
  a log file name but the logs will be written to `/var/log/nginx/target.domain.de-*.log`
  regardless of the actual redirect target, causing silent log loss.
- Files: `nginx_set_conf/templates/redirect_ssl.py:19-35`, `nginx_set_conf/utils.py:726-728`
- What to investigate: Make `redirect_domain` required for `redirect` and `redirect_ssl`
  templates; add a validator or `execute_commands` early-exit when it's missing.

**[MEDIUM] `proxy_cache_path /tmp` used as the sentinel in `all_templates.py:58`**
*(CLOSED — Phase 2 / COR-03 — `CACHE_PATH_SENTINEL = "proxy_cache_path /tmp"` constant defined; all templates and all_templates.py use it)*
- `all_templates.py:58` does `template.replace("proxy_cache_path /tmp", ...)`. This is
  a literal string match. If any future template uses a different cache path sentinel
  (e.g., `/var/cache/nginx` or `/tmp/nginx`), the replacement silently fails and the
  raw `/tmp` path ships to production. Currently all 17 templates consistently use
  `/tmp` — this is fragile duplication.
- Files: `nginx_set_conf/templates/all_templates.py:58`, every template file line 13
- What to investigate: Define a single sentinel constant (e.g., `CACHE_PATH_SENTINEL`)
  shared between all template files and `all_templates.py`.

**[LOW] `default_ssl_reject` is absent from `VALID_TEMPLATES` whitelist**
*(CLOSED — Phase 2 / COR-04 — exclusion documented inline in VALID_TEMPLATES; template is setup-default-only by design)*
- `validators.py:25-43` lists all valid templates; `default_ssl_reject` is missing.
  Users cannot pass `--config_template default_ssl_reject` to `execute_commands` — it
  will fail validation. The template is only accessible through `--setup_default`. This
  is probably intentional but is undocumented.
- Files: `nginx_set_conf/validators.py:25-43`, `nginx_set_conf/utils.py:501`
- What to investigate: Add a comment in `VALID_TEMPLATES` documenting the exclusion, or
  expose the template explicitly if operators need to generate it manually.

**[LOW] Two-stage cache rename in `utils.py` uses `\1` in f-string replacement**
*(CLOSED — Phase 2 / COR-05 — lambda repl `lambda m: f"{m.group(1)}{unique_id}_cache:"` eliminates back-reference footgun)*
- `utils.py:628`: `f"\\1{unique_id}_cache:"` is used as the `repl` argument to
  `re.sub`. The double-backslash produces a literal `\1` in the f-string which `re.sub`
  then interprets as a back-reference. This works but is a footgun — a `unique_id`
  containing a backslash (impossible today given RFC 1123 domain validation, but possible
  if the service_name ever changes) would break the substitution.
- Files: `nginx_set_conf/utils.py:628`
- What to investigate: Use `re.sub(..., lambda m: f"{m.group(1)}{unique_id}_cache:", ...)`
  to make back-reference intent explicit.

---

## Tech Debt / Smells

**[MEDIUM] Two egg-info directories with different package identities**
*(CLOSED — Phase 3 / TD-01 — `nginx_set_conf_equitania.egg-info/` deleted; `*.egg-info/` confirmed in .gitignore)*
- `nginx_set_conf.egg-info/` (package name: `nginx-set-conf`) and
  `nginx_set_conf_equitania.egg-info/` (package name: `nginx-set-conf-equitania`,
  version 1.0.7) coexist at the repo root. The equitania variant is a stale artifact
  from a previous PyPI identity. It does not affect runtime behaviour but can confuse
  package managers and CI tooling that scan for installed metadata.
- Files: `nginx_set_conf.egg-info/`, `nginx_set_conf_equitania.egg-info/`
- What to investigate: Delete `nginx_set_conf_equitania.egg-info/` and add `*.egg-info/`
  to `.gitignore` (it is already listed there but the directories were committed previously).

**[MEDIUM] `config_templates.py` is a deprecated shim with active `print()` side-effects**
*(CLOSED — Phase 3 / TD-02 — `config_templates.py` hard-deleted; all callers migrated to `all_templates.get_config_template`)*
- `config_templates.py` is marked "deprecated" in its own docstring (line 28) but is
  still imported by `nginx_set_conf.py` via `get_config_template`. Lines 94 and 97
  contain bare `print()` calls that fire every time a template is fetched with or without
  a domain, polluting stdout in production runs.
- Files: `nginx_set_conf/config_templates.py:28,94,97`
- What to investigate: Either remove the shim and update `nginx_set_conf.py` to import
  directly from `all_templates`, or silence the `print()` calls with `logger.debug()`.

**[LOW] `nginx_set_conf.log` committed to repo root**
*(CLOSED — Phase 3 / TD-03 — `git rm --cached nginx_set_conf.log`; file untracked; `*.log` in .gitignore confirmed)*
- A real log file (`nginx_set_conf.log`, non-empty) sits at the repo root. It is listed
  in `.gitignore` (`*.log`) but was committed before that entry was added (or bypassed).
  It reveals local execution details to anyone who clones the repo.
- Files: `nginx_set_conf.log`
- What to investigate: `git rm --cached nginx_set_conf.log` to stop tracking it.

**[LOW] `build/` directory with compiled wheels committed (or untracked)**
*(CLOSED — Phase 3 / TD-04 — confirmed untracked; `build/` and `dist/` entries in .gitignore verified)*
- `dist/nginx_set_conf-1.11.0-py3-none-any.whl` and the `build/bdist.*` directories
  are present. `.gitignore` lists `build/` and `dist/` — these appear to be untracked
  per `git status`. No commit risk, but local state diverges from clean checkout, which
  can confuse UV builds.
- Files: `build/`, `dist/`
- What to investigate: Confirm `build/` and `dist/` are untracked (`git status`) and add
  them to `.gitignore` explicitly if not already covered.

**[LOW] `redirect` and `redirect_ssl` templates include `proxy_cache_path` and `limit_req_zone` they never use**
*(CLOSED — Phase 3 / TD-05 — unused `proxy_cache_path` and `limit_req_zone` directives stripped from both redirect templates; verified with nginx -t)*
- Neither redirect template uses `proxy_cache` directives in any `location` block, yet
  both contain the boilerplate `proxy_cache_path /tmp ...` and
  `limit_req_zone ... zone=iprl ...` at the top level. These load shared memory zones
  nginx must allocate on every reload, for no purpose.
- Files: `nginx_set_conf/templates/redirect.py:13,17`,
  `nginx_set_conf/templates/redirect_ssl.py:13-14`
- What to investigate: Strip unused cache and rate-limit directives from redirect
  templates; verify with `nginx -t` after removal.

**[LOW] Interactive mode (`else` branch in `start_nginx_set_conf`) has no validation calls**
*(CLOSED — Phase 3 / TD-06 — `cert_key` interactive prompt added; interactive mode now documented as LE-or-self-signed; documented in --help)*
- When neither `--config_path` nor `--config_template` is supplied, the tool prompts
  interactively and calls `execute_commands` directly (line 434) without the
  `validate_all_inputs` wrapper — but `execute_commands` itself calls `validate_all_inputs`
  at line 558, so validation does occur. However, the interactive mode also accepts `cert_key`
  as hardcoded `None` (`cert_key` is never requested interactively, lines 415-433), so
  the Let's Encrypt path is always forced in interactive mode even if the user intended
  a self-signed cert.
- Files: `nginx_set_conf/nginx_set_conf.py:414-448`
- What to investigate: Add a `cert_key` prompt to the interactive path or document that
  interactive mode is LE-only.

---

## Open Questions / TODOs

**[QUESTION] `--migrate_to_ip_bound` is mentioned in RELEASE_NOTES but does not exist**
*(CLOSED — Phase 4 / Q-01 — teaser removed from RELEASE_NOTES v1.11.0; manual migration procedure documented in README under "Manual Migration: Hostname-bound to IP-bound Listen"; MIG-01 deferred to v2)*
- RELEASE_NOTES.md v1.11.0 line 31-32 states: "A future minor release may add an atomic
  `--migrate_to_ip_bound` companion to `--migrate_to_wildcard`." This flag is not
  implemented. Existing servers that regenerate with v1.11.0 templates get IP-bound
  listens for new configs, but mixed deployments (some old wildcard / some new IP-bound)
  have no atomic migration path yet.
- Files: `RELEASE_NOTES.md:31-32`
- What to investigate: Decide whether to implement `--migrate_to_ip_bound` or document
  the manual migration procedure (regenerate all configs) in README.

**[QUESTION] SHA256 comparison flags any intentional server-side customisation as "inconsistent"**
*(CLOSED — Phase 4 / Q-02 — `--force` flag required before `--sync_config` overwrites any server file; warn-and-abort without --force; interactive prompt removed)*
- `ConfigVerification.verify_configuration_consistency` compares the embedded template
  byte-for-byte against the server file. Any operator customisation (e.g., tuning
  `worker_connections` in `nginx.conf`) will always show as inconsistent. The tool offers
  to overwrite the server file, which would silently destroy the customisation.
- Files: `nginx_set_conf/config_verification.py:199-241`
- What to investigate: Add a `--force` flag and a clearer warning before sync that
  operator-local changes will be lost; or document this limitation prominently.

---

## Documentation Drift

**[LOW] CLAUDE.md claims `replace_cache_path()` is in `nginx_set_conf/__init__.py`**
*(CLOSED — Phase 4 / DOC-01 — CLAUDE.md Important Files corrected: `__init__.py` covers version only; `all_templates.py` covers `replace_cache_path()` and `CACHE_PATH_SENTINEL`)*
- CLAUDE.md section "Important Files" states: "`nginx_set_conf/__init__.py`: Contains
  version and `replace_cache_path()` utility." In the current code, `replace_cache_path`
  lives in `nginx_set_conf/templates/all_templates.py`, not `__init__.py`.
- Files: `CLAUDE.md`, `nginx_set_conf/__init__.py`, `nginx_set_conf/templates/all_templates.py:29`
- What to investigate: Update CLAUDE.md to reflect the correct location.

**[MEDIUM] Templates and embedded base configs claim "incl. SSL/http2" but never enable HTTP/2**
*(CLOSED — Phase 2.5 / PROTO-01 — `http2 on;` directive added to all SSL server blocks; nginx ≥ 1.25 post-context syntax used; nginx version requirement documented in README)*
- Every per-service template (`odoo_ssl.py`, `flowise.py`, `mailpit.py`,
  `nextcloud.py`, `pgadmin.py`, `pwa.py`, `portainer.py`, `supabase.py`,
  `code_server.py`, `fast_report.py`, `redirect_ssl.py`, etc.) starts with a
  banner comment `# Template for ... configuration nginx incl. SSL/http2`.
  Likewise the three embedded base configs in
  `config_verification.py` (`NGINX_CONF_TEMPLATE`, `GENERAL_CONF_TEMPLATE`,
  `SECURITY_CONF_TEMPLATE`) all carry the header `# nginx incl. SSL/http2 1.24.1`.
- **None of them actually emit an `http2` directive.** The `listen` lines are
  bare `listen ip.ip.ip.ip:443 ssl;` (no `http2` parameter, no `http2 on;`
  inside the server block) and the embedded `NGINX_CONF_TEMPLATE` has no
  `http2 on;` either. Every site shipped by this tool runs HTTP/1.1 over TLS.
- The pre-nginx-1.25 syntax `listen 443 ssl http2;` and the post-1.25 syntax
  `http2 on;` are both absent. Operators believing they have HTTP/2 do not.
- Files: every `nginx_set_conf/templates/*.py` SSL template,
  `nginx_set_conf/config_verification.py:17,84,100`.
- What to investigate: Phase 2.5 of the v1.12 roadmap delivers
  what the documentation already claims — add `http2 on;` (post-1.25 syntax)
  AND keep `http2` parameter on `listen` lines for 1.24-compatible fallback,
  or pin to the post-1.25 form and document the nginx version requirement.

---

*Concerns audit: 2026-05-28*
*HTTP/2 finding added: 2026-05-28 (discuss-phase HTTP/3 review)*
*Re-audit complete: 2026-05-29 — Phase 4 complete — Zero HIGH / Zero MEDIUM open findings*
