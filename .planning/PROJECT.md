# nginx-set-conf

## What This Is

A Python CLI tool by Equitania Software GmbH that generates `nginx`
reverse-proxy configurations for Docker-based applications (Odoo,
Flowise, Qdrant, n8n, Guacamole, Mailpit, Code-Server, Nextcloud, …).
Templates are shipped as embedded Python modules, deployed under
`/etc/nginx/conf.d/`, validated with `nginx -t` and reloaded gracefully.
The tool also verifies, syncs, and backs up the top-level nginx config
files (`nginx.conf`, `general.conf`, `security.conf`).

## Core Value

**A YAML-driven generator must never become a privileged file-write
surface on the host, and a routine deploy must never take nginx down.**
Every release defends those two invariants — operationally and via
the validator surface.

## Requirements

### Validated

<!-- Shipped and confirmed valuable in v1.11.1 and earlier. -->

- **SEC-HIGH-01**: `nginx -t` validates the generated config before any
  reload (no live nginx crash on bad input).
- **SEC-HIGH-02**: `auth_file` paths are constrained to `/etc/nginx/`
  and may not point at the `conf.d/` snippet directory.
- **SEC-HIGH-03**: Wildcard domains do not produce shell-glob filenames.
- **SEC-V1.10.2**: `..` path-traversal rejection happens BEFORE
  `os.path.normpath` for cert/key/auth-file inputs.
- **NET-V1.11.0**: IP-bound `listen` directives (no DNS-parse-time
  failures, no SNI fallback leaks).
- **TPL-V1.5.4+**: Embedded nginx config templates ship inside the
  package — no filesystem dependency on `yaml_examples/` at runtime.
- **COR-V1.12 (Phase 2)**: Cache-path substitution consolidated into a
  single authoritative pass in `utils.py`; `CACHE_PATH_SENTINEL` defined
  once in `all_templates.py`; redirect/redirect_ssl invocations require
  `--redirect_domain` (no `target.domain.de` sentinel leak); the
  `default_ssl_reject` exclusion from `VALID_TEMPLATES` is documented
  inline. Covers COR-01..COR-05.

### Active

v1.12 scope — see `REQUIREMENTS.md` for the full list.

- [ ] Tighten privileged write surface (key file mode, copytree symlink
      safety, YAML whitespace).
- [ ] Retire the deprecated `config_templates.py` shim and clean up
      committed artefacts (`*.egg-info/`, `*.log`).
- [ ] Resolve open questions (`--migrate_to_ip_bound`, `--sync_config`
      operator-customisation handling) and fix documentation drift.

### Out of Scope

- **Adding a CI publish step to PyPI** — by user preference, publish is
  local-only (`uv build && uv publish`).
- **A configuration GUI / web admin** — this is and stays a CLI.
- **Cross-platform support beyond Linux nginx hosts** — the tool writes
  to `/etc/nginx/conf.d/` and runs `systemctl`; macOS/Windows are not
  target deployment surfaces.

## Context

**Technical environment:** Python ≥ 3.10, Click CLI, hatchling build,
UV package manager. Distributed as `nginx-set-conf` on PyPI. The CLI
runs on the nginx host (usually as root) and mutates `/etc/nginx/conf.d/`
+ runs `systemctl` / `certbot` / `nginx -t` via `subprocess`.

**Recent history (relevant context for any change touching listen, SSL,
or deploy paths):**

- **v1.10.0 (2026-04-21)**: rewrote all 17 templates from hostname-bound
  to wildcard listens to fix DNS-parse-time aborts → caused SNI
  fallback leaks (wrong cert served for unknown SNI) within hours →
  reverted.
- **v1.10.2**: restored hostname-bound default + introduced opt-in
  atomic `--migrate_to_wildcard` with rollback. Plugged the
  `..` path-traversal hole.
- **v1.11.0**: IP-bound listens (Pattern C) — combines DNS-safety and
  SNI-safety.
- **v1.11.1 (2026-05-28)**: three HIGH findings from a codebase audit
  fixed: pre-reload validation, auth_file constraints, wildcard
  filename sanitisation.

**Codebase map:** `.planning/codebase/` contains 7 documents
(STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING,
CONCERNS) — generated 2026-05-28 from a parallel mapper sweep. The
v1.12 backlog is derived from CONCERNS.md.

## Constraints

- **Tech stack**: Python ≥ 3.10, Click, hatchling, UV. No additional
  runtime dependencies introduced lightly — the package is meant to
  install cleanly on minimal hosts.
- **Deployment**: Linux nginx hosts only. The CLI runs as root in
  practice; `subprocess` calls must use argument lists, never `shell=True`.
- **Compatibility**: Existing operator YAML configs must keep working
  across minor versions. Behavioural changes ship with a `RELEASE_NOTES.md`
  migration note.
- **Security**: Every input that lands in a generated nginx directive
  or a filesystem path passes through `validators.py`. Path-traversal
  rejection is done on the raw input, not on `os.path.normpath` output.
- **Testing**: Coverage gate at 60% (currently 67.8%). Goal: 70% for
  the next minor.
- **Documentation language**: Code, docstrings, and commits in
  English. Operator-facing docs (README, RELEASE_NOTES) bilingual
  (English + German). User-facing conversation in German.
- **Publish**: Local-only (`uv build && uv publish`). Never add a PyPI
  upload step to CI.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

- **2026-05-28**: nginx-set-conf is brought under GSD management
  starting with v1.12. The full Codebase-Map (`.planning/codebase/`)
  is the input to REQUIREMENTS.md and ROADMAP.md.
- **2026-05-28**: v1.12 is a **hardening + cleanup** minor, not a
  feature minor. No new CLI flags. Aim: shrink CONCERNS.md to near-zero
  before any new feature work.
- **2026-04-21**: `listen` direktive defaults to **IP-bound** (Pattern
  C). Never reintroduce wildcard listens without a `default_ssl_reject`
  catch-all in the same change.
- **2025-xx-xx**: bump-my-version configured in `pyproject.toml`
  ([tool.bump-my-version]) — never bypass it for releases.

## Project Reference

**Codebase map:** `.planning/codebase/` (7 docs, generated 2026-05-28)
**Skill:** `~/.claude/skills/nginx-set-conf/SKILL.md`
**Repo (origin)**: `git@gitlab.ownerp.io:pypi-projects/nginx-set-conf.git`
**Repo (upstream)**: `git@github.com:equitania/nginx-set-conf.git`
**Current branch:** `2025`
**Released version:** v1.11.1 (2026-05-28)

---

*Initialized: 2026-05-28*
*Source: derived from existing codebase + `.planning/codebase/CONCERNS.md`*
