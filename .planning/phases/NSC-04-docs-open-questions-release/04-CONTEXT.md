# Phase 4: Docs, open questions, release - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Source:** Interactive decisions (plan-phase, no discuss-phase)

<domain>
## Phase Boundary

This phase closes out the v1.12.0 milestone. It delivers:
1. **DOC-01** — a documentation-drift correction in `CLAUDE.md`.
2. **Q-01** — a recorded decision + implementation for the teased
   `--migrate_to_ip_bound` flag.
3. **Q-02** — a recorded decision + implementation for `--sync_config`
   silently overwriting operator customisations.
4. The **v1.12.0 release** (version bump, RELEASE_NOTES finalisation,
   tag, push, local PyPI publish).
5. A **CONCERNS.md re-audit** confirming zero HIGH/MEDIUM findings remain
   after Phases 1–4.

NOT in scope: HTTP/3 (Phase 5), migration tooling beyond the manual
procedure (MIG-01 stays v2).
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### DOC-01 — CLAUDE.md correction
- `CLAUDE.md` currently states `replace_cache_path` lives in
  `nginx_set_conf/__init__.py`. **Correct it** to
  `nginx_set_conf/templates/all_templates.py` (its actual location after
  the Phase 2/3 consolidation).
- Verify the corrected location against the live code before editing.
- Check for the same wrong reference elsewhere (README.md, other docs) and
  fix consistently.

### Q-01 — `--migrate_to_ip_bound` → REMOVE TEASER + DOCUMENT MANUAL
- **Decision: do NOT implement the flag.** Avoids the v1.10.0 risk class
  (mass rewrite of `listen` lines across templates). Migration tooling
  (MIG-01) is explicitly deferred to v2.
- Remove the `--migrate_to_ip_bound` teaser from `RELEASE_NOTES.md`
  (around lines 31–32, the v1.11.0 section).
- Document a **manual** hostname-bound → IP-bound migration procedure in
  `README.md` (operators do it by hand; reference the existing
  `--migrate_to_wildcard` flow as the pattern to follow conceptually).
- Record the decision in the RELEASE_NOTES v1.12.0 section.

### Q-02 — `--sync_config` → IMPLEMENT `--force` + PRE-SYNC WARNING
- **Decision: implement a safety gate.** `--sync_config` currently silently
  overwrites operator-local customisations in the server config files
  (`config_verification.py:199-241`).
- Add a `--force` CLI flag. Without `--force`: print a clear warning that
  operator-local customisations to the synced files WILL be lost, and
  abort (require explicit `--force` to proceed). With `--force`: proceed
  and emit the same warning as a notice.
- This aligns with the project's data-loss-prevention ethos.
- Record the decision in the RELEASE_NOTES v1.12.0 section.
- Add/extend tests covering: warn-and-abort without `--force`, proceed
  with `--force`.

### Release mechanics (v1.12.0)
- Use **`bump-my-version bump minor`** to go 1.11.1 → 1.12.0 (updates
  version headers + date per project convention DD.MM.YYYY).
- Finalise the `## Version 1.12.0` RELEASE_NOTES.md section (it currently
  carries a `(development)` marker from Phase 3 — drop that, add the Q-01/
  Q-02/DOC-01 entries, set the release date).
- **CRITICAL — publish is LOCAL-ONLY.** The git tag push (`origin` +
  `upstream`) and the `uv build` + PyPI publish (`uvpublish`) are run by
  the operator locally. NEVER add a publish/release step to any CI
  workflow (.github/workflows). Plan tasks that perform tag-push / build /
  publish must be `autonomous: false` (operator-run) — Claude cannot test
  or deploy locally.

### Claude's Discretion
- Exact wording of the README manual-migration section and the `--force`
  warning text.
- Test structure for the `--force` gate (follow existing test patterns in
  `tests/`).
- Whether the CONCERNS.md re-audit is its own task or folded into the
  release-prep plan.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Open-question source
- `.planning/codebase/CONCERNS.md` — §DOC-LOW-1 (Q-01 §Q-1, Q-02 §Q-2);
  re-audit target for Success Criterion 4.
- `RELEASE_NOTES.md` — v1.11.0 section holds the `--migrate_to_ip_bound`
  teaser to remove; v1.12.0 section to finalise.

### Code touch points
- `CLAUDE.md` — DOC-01 fix.
- `README.md` — manual IP-bound migration procedure (Q-01).
- `nginx_set_conf/config_verification.py:199-241` — `--sync_config` logic
  for the Q-02 `--force` gate.
- `nginx_set_conf/nginx_set_conf.py` — Click option wiring for `--force`;
  reference `--migrate_to_wildcard` (lines ~250, 282) as the analog for
  CLI flag plumbing.
- `pyproject.toml` / `nginx_set_conf/__init__.py` — version source for the
  bump.

### Project rules
- `./CLAUDE.md` (project + root) — commit prefixes, version/date headers,
  UV usage, UTF-8.
- Memory: publish is local-only, never a CI step.
</canonical_refs>

<specifics>
## Specific Ideas

- Success Criteria (from ROADMAP) that the plan's must_haves must cover:
  1. CLAUDE.md states `replace_cache_path` in `all_templates.py`.
  2. Q-01 decision documented in RELEASE_NOTES v1.12 + manual procedure in
     README (teaser removed).
  3. Q-02 decision documented + `--force` gate implemented with warning.
  4. CONCERNS.md re-audited — zero HIGH/MEDIUM; LOW findings justified.
  5. `bump-my-version bump minor` succeeds; `v1.12.0` tag pushed to
     `origin` + `upstream`; local PyPI publish completes. (Operator-run.)
- Likely 2 plans: (04-01) docs + Q-01/Q-02 decisions & implementation,
  (04-02) release prep + re-audit. Release push/publish steps are
  operator-run (`autonomous: false`).
</specifics>

<deferred>
## Deferred Ideas

- `--migrate_to_ip_bound` flag implementation (MIG-01) — deferred to v2.
- HTTP/3 support (Phase 5).
</deferred>

---

*Phase: 04-docs-open-questions-release*
*Context gathered: 2026-05-29 via interactive plan-phase decisions*
