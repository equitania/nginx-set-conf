# Phase 3: Tech debt + repository cleanup - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

The repository checkout matches a clean build. This phase removes stale
committed artefacts, retires the deprecated `config_templates.py` shim,
slims redirect templates to only the directives they use, and reconciles
the interactive CLI path with the actual SSL/cert behaviour.

Covers requirements TD-01 through TD-06. No new capabilities — pure
tech-debt reduction and repository hygiene against the existing v1.11.1
baseline.

</domain>

<decisions>
## Implementation Decisions

### Deprecated shim removal (TD-02)
- **D-01:** Hard-remove `nginx_set_conf/config_templates.py` entirely. Do
  NOT keep a re-export shim. The module is already publicly marked
  `"deprecated and will be removed in a future version"` in its docstring,
  and it is an internal CLI module with no documented external Python
  consumers. The compatibility constraint in PROJECT.md governs operator
  YAML configs, not the Python import surface.
- **D-02:** `nginx_set_conf/nginx_set_conf.py` imports `get_config_template`
  directly from `nginx_set_conf.templates.all_templates` (currently line 26
  imports it from `.config_templates`). The call site at ~line 337 is
  unchanged in behaviour.
- **D-03:** The `print()` side-effects on template fetch are eliminated.
  Their root cause is the eager evaluation of `config_template_dict` at
  module import in `config_templates.py` — removing the module removes the
  side-effect.
- **D-04:** Add a migration note to `RELEASE_NOTES.md` documenting the
  removal of `config_templates.py` (the deprecation→removal step).

### Interactive cert_key (TD-06)
- **D-05:** Do BOTH — belt and suspenders:
  1. Add a `cert_key` prompt to the interactive `start_nginx_set_conf`
     wizard, using the existing `retrieve_valid_input(...)` pattern, placed
     logically near the `cert_name` prompt. Empty input is valid and means
     "no pre-existing key → Let's Encrypt generates one."
  2. Document the Let's-Encrypt-only behaviour (cert_key omitted → automatic
     LE cert) in the `--help` text so the non-interactive default is
     explicit.

### Verification approach (TD-05)
- **D-06:** Verify the redirect-template slim-down via unit tests that assert
  `proxy_cache_path` and `limit_req_zone` directives are ABSENT from the
  generated `redirect` and `redirect_ssl` configs. Claude cannot run nginx
  locally.
- **D-07:** `nginx -t` acceptance stays a documented manual server-side check
  performed at release time (per ROADMAP success criterion 5). It is NOT a
  hard release-blocking gate in tooling — test coverage carries the
  automated guarantee.

### Mechanical cleanup (TD-01, TD-03, TD-04)
- **D-08:** TD-01 (remove stale `nginx_set_conf_equitania.egg-info/`),
  TD-03 (`git rm --cached nginx_set_conf.log`), and TD-04 (confirm
  `build/`/`dist/` gitignored + untracked) are mechanical, no-gray-area
  cleanups. Planner sequences them; no further user input needed.

### Claude's Discretion
- Commit granularity / plan breakdown (ROADMAP suggests 3 plans: shim
  removal, repo-artefact cleanup, redirect slim-down + interactive help) —
  planner decides final shape.
- Exact placement and wording of the `cert_key` prompt and `--help` text.
- RELEASE_NOTES.md entry wording/format (follow existing project convention).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §TD-01..TD-06 — the six tech-debt requirements
  with their CONCERNS.md cross-references.
- `.planning/ROADMAP.md` → "Phase 3: Tech debt + repository cleanup" — goal,
  7 success criteria, suggested 3-plan breakdown.

### Concern provenance
- `.planning/codebase/CONCERNS.md` §TD-MED-1 (egg-info), §TD-MED-2
  (`config_templates.py:28,94,97` print side-effects), §TD-LOW-1 (committed
  `.log`), §TD-LOW-2 (build/dist), §TD-LOW-3
  (`templates/redirect.py:13,17`, redirect_ssl), §TD-LOW-4
  (`nginx_set_conf.py:414-448` interactive cert_key).

### Project constraints
- `.planning/PROJECT.md` → "Constraints" — compatibility applies to operator
  YAML across minor versions; behavioural changes ship with a RELEASE_NOTES
  migration note.
- `RELEASE_NOTES.md` — target for the TD-02 migration note (D-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nginx_set_conf/templates/all_templates.py::get_config_template` — the
  canonical template fetcher; becomes the direct import target replacing the
  `config_templates.py` shim (D-02).
- `retrieve_valid_input(prompt)` in `nginx_set_conf/nginx_set_conf.py` — the
  established interactive-prompt helper; the new `cert_key` prompt reuses it
  (D-05).

### Established Patterns
- The interactive wizard (`else` branch of `start_nginx_set_conf`,
  ~lines 423-448) prompts each field sequentially via `retrieve_valid_input`,
  then calls `execute_commands(...)`. `cert_key` is currently passed through
  from a function-level default without ever being prompted → implicit
  Let's-Encrypt-only.
- `config_templates.py` builds `config_template_dict` eagerly at import,
  calling `all_get_config_template(...)` for every entry — the source of the
  per-fetch `print()` noise (D-03).

### Integration Points
- `nginx_set_conf/nginx_set_conf.py:26` — import line to repoint to
  `all_templates`.
- `nginx_set_conf/nginx_set_conf.py:~337` — `get_config_template(config_template)`
  call site (behaviour unchanged).
- `nginx_set_conf/templates/redirect.py:13,17` and
  `nginx_set_conf/templates/redirect_ssl.py` — `proxy_cache_path` /
  `limit_req_zone` lines to strip (TD-05).

</code_context>

<specifics>
## Specific Ideas

- `cert_key` prompt empty-string semantics: empty = no pre-existing key =
  Let's Encrypt auto-generates. This must match the non-interactive flag
  behaviour exactly so both paths are consistent.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Documentation reconciliation
beyond the `--help` cert_key note belongs to Phase 4 "Docs, open questions,
release"; HTTP/3 work is Phase 5.)

</deferred>

---

*Phase: 3-tech-debt-repository-cleanup*
*Context gathered: 2026-05-29*
