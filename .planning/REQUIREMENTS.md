# Requirements: nginx-set-conf v1.12

**Defined:** 2026-05-28
**Core Value:** A YAML-driven generator must never become a privileged file-write surface on the host, and a routine deploy must never take nginx down.

## v1.12 Requirements

v1.12 is a **hardening + cleanup** minor release. Every requirement
below traces back to a specific finding in
`.planning/codebase/CONCERNS.md` produced by the 2026-05-28 audit.
Categories use the codebase-map taxonomy: SEC (security), COR
(correctness), TD (tech debt), DOC (documentation), Q (open question).

### SEC — Security hardening (MEDIUM + LOW)

- [ ] **SEC-01**: `validate_target_path` strips whitespace before the
      `..` check so YAML-supplied values like `"  ../etc"` cannot
      sidestep the literal substring test.
      *(CONCERNS.md §SEC-MED-1 — `validators.py:162-169`,
      `nginx_set_conf.py:363-365`.)*
- [ ] **SEC-02**: `backup_configuration` uses
      `shutil.copytree(..., symlinks=False)` and rejects a symlinked
      `/etc/nginx/nginxconfig.io` source so a compromised host cannot
      coerce the backup to follow attacker-controlled symlinks.
      *(CONCERNS.md §SEC-MED-2 — `config_verification.py:436-444`.)*
- [ ] **SEC-03**: `setup_default_server` pre-creates the private key
      file with mode `0o600` before invoking `openssl req` (or sets
      `umask(0o077)` around the openssl call) so the world-readable
      window is eliminated.
      *(CONCERNS.md §SEC-MED-3 — `utils.py:490-497`.)*
- [ ] **SEC-04**: `retrieve_valid_input` is converted from a recursive
      to an iterative loop and enforces a maximum input length so a
      piped non-interactive stdin cannot exhaust the stack.
      *(CONCERNS.md §SEC-LOW-1 — `nginx_set_conf.py:415`,
      `utils.py:138-151`.)*

### COR — Correctness (MEDIUM + LOW)

- [ ] **COR-01**: The dual cache-path substitution pipeline is
      consolidated into a single authoritative pass. The
      module-level pre-substitution in `all_templates.py` is removed
      now that `utils.py` does the domain-qualified pass.
      *(CONCERNS.md §COR-MED-1 — `all_templates.py:56-82`,
      `utils.py:620-638`.)*
- [ ] **COR-02**: `redirect_domain` is required (validated) for the
      `redirect` and `redirect_ssl` templates so the literal
      `target.domain.de` sentinel can no longer leak into nginx log
      file paths.
      *(CONCERNS.md §COR-MED-2 — `templates/redirect_ssl.py:19-35`,
      `utils.py:726-728`.)*
- [ ] **COR-03**: A single `CACHE_PATH_SENTINEL` constant is shared
      between `all_templates.py` and every template file so the
      replacement cannot silently fail when a template's sentinel
      drifts.
      *(CONCERNS.md §COR-MED-3 — `all_templates.py:58`, every template
      file line 13.)*
- [ ] **COR-04**: `default_ssl_reject` is either added to
      `VALID_TEMPLATES` with documentation, or its absence is
      explained inline so future operators do not file phantom bugs.
      *(CONCERNS.md §COR-LOW-1 — `validators.py:25-43`, `utils.py:501`.)*
- [ ] **COR-05**: The cache-path regex substitution uses a lambda
      `repl` instead of `f"\\1{unique_id}_cache:"` so back-reference
      semantics are explicit and a future `unique_id` change cannot
      silently break the substitution.
      *(CONCERNS.md §COR-LOW-2 — `utils.py:628`.)*

### TD — Tech debt cleanup (MEDIUM + LOW)

- [ ] **TD-01**: The stale `nginx_set_conf_equitania.egg-info/`
      directory is removed from the repository. The remaining
      `nginx_set_conf.egg-info/` is verified to be ignored.
      *(CONCERNS.md §TD-MED-1.)*
- [ ] **TD-02**: The deprecated `config_templates.py` shim is removed.
      `nginx_set_conf.py` imports directly from `all_templates`. The
      `print()` side-effects on every template fetch are eliminated.
      *(CONCERNS.md §TD-MED-2 — `config_templates.py:28,94,97`.)*
- [ ] **TD-03**: `nginx_set_conf.log` is removed from version control
      (`git rm --cached`) — it was committed before the `*.log` entry
      was added to `.gitignore`.
      *(CONCERNS.md §TD-LOW-1.)*
- [ ] **TD-04**: `build/` and `dist/` are explicitly in `.gitignore`
      and verified untracked. This is a no-op confirmation but worth
      documenting.
      *(CONCERNS.md §TD-LOW-2.)*
- [ ] **TD-05**: The unused `proxy_cache_path` and `limit_req_zone`
      directives are stripped from `templates/redirect.py` and
      `templates/redirect_ssl.py`. nginx no longer allocates shared
      memory zones for these vhosts.
      *(CONCERNS.md §TD-LOW-3 — `templates/redirect.py:13,17`,
      `templates/redirect_ssl.py:13-14`.)*
- [ ] **TD-06**: The interactive `start_nginx_set_conf` path either
      prompts for `cert_key` or its Let's-Encrypt-only behaviour is
      documented in the help text.
      *(CONCERNS.md §TD-LOW-4 — `nginx_set_conf.py:414-448`.)*

### DOC — Documentation drift (LOW)

- [ ] **DOC-01**: `CLAUDE.md` is corrected — `replace_cache_path` lives
      in `nginx_set_conf/templates/all_templates.py`, not
      `nginx_set_conf/__init__.py`.
      *(CONCERNS.md §DOC-LOW-1.)*

### Q — Open questions to resolve (decisions, then implement or document)

- [ ] **Q-01**: Decide on `--migrate_to_ip_bound` (RELEASE_NOTES v1.11.0
      teases it). Implement the analog to `--migrate_to_wildcard` OR
      remove the teaser and document the manual procedure in README.
      *(CONCERNS.md §Q-1 — `RELEASE_NOTES.md:31-32`.)*
- [ ] **Q-02**: `--sync_config` currently silently overwrites operator
      customisations. Add a `--force` flag and a clearer warning before
      sync, OR document this limitation prominently in README.
      *(CONCERNS.md §Q-2 — `config_verification.py:199-241`.)*

## v2 Requirements

Deferred to a future release (no current roadmap slot).

### Migration tooling
- **MIG-01**: A bulk server-side upgrade path from hostname-bound
  (Pattern A) to IP-bound (Pattern C) listens, analogous to the
  existing `--migrate_to_wildcard` flow. (Track decision in Q-01.)

### Coverage
- **TEST-01**: Raise the coverage gate from 60% → 70% and add tests
  for `config_verification.py` (currently 11% covered).

## Out of Scope

| Feature | Reason |
|---------|--------|
| GitHub Actions PyPI publish step | Local-only publish is a hard user preference (memory: `feedback_publish.md`). |
| Web admin / GUI | nginx-set-conf is and stays a CLI. |
| Cross-platform (macOS / Windows nginx hosts) | Tool writes to `/etc/nginx/conf.d/` and calls `systemctl`; Linux only. |
| New service templates in v1.12 | This minor is hardening, not feature. New templates are unblocked again from v1.13. |
| Replacing Click with a different CLI framework | Stable, well-tested, no upside. |

## Traceability

Mapped during ROADMAP creation (see `ROADMAP.md`).

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| COR-01 | Phase 2 | Pending |
| COR-02 | Phase 2 | Pending |
| COR-03 | Phase 2 | Pending |
| COR-04 | Phase 2 | Pending |
| COR-05 | Phase 2 | Pending |
| TD-01 | Phase 3 | Pending |
| TD-02 | Phase 3 | Pending |
| TD-03 | Phase 3 | Pending |
| TD-04 | Phase 3 | Pending |
| TD-05 | Phase 3 | Pending |
| TD-06 | Phase 3 | Pending |
| DOC-01 | Phase 4 | Pending |
| Q-01 | Phase 4 | Pending |
| Q-02 | Phase 4 | Pending |

**Coverage:**
- v1.12 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-05-28*
*Source: `.planning/codebase/CONCERNS.md` (3 HIGH already fixed in v1.11.1)*
