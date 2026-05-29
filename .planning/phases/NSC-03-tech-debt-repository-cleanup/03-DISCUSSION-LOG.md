# Phase 3: Tech debt + repository cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 3-tech-debt-repository-cleanup
**Areas discussed:** Shim removal (TD-02), Interactive cert_key (TD-06), nginx verification (TD-05)

---

## Shim removal (TD-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-remove + RELEASE note | Remove config_templates.py entirely; nginx_set_conf.py imports get_config_template directly from all_templates; eliminates print() side-effects; migration note in RELEASE_NOTES. | ✓ |
| Keep thin re-export | Reduce config_templates.py to a side-effect-free re-export, defer removal to a later major version. | |

**User's choice:** Hard-remove + RELEASE note
**Notes:** Module is already publicly marked deprecated; internal CLI module with no documented external Python consumers. Compatibility constraint governs operator YAML, not the Python import surface.

---

## Interactive cert_key (TD-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Document in --help | Leave interactive flow unchanged; document the Let's-Encrypt-only behaviour in --help. | ✓ (combined) |
| Add cert_key prompt | Extend the interactive wizard with a cert_key prompt for full parity with CLI flags. | ✓ (combined) |

**User's choice:** Both — document LE-only in --help AND add the cert_key prompt to the interactive wizard.
**Notes:** Empty cert_key input = no pre-existing key = Let's Encrypt auto-generates. Prompt reuses retrieve_valid_input pattern. Both paths must stay behaviourally consistent.

---

## nginx verification (TD-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Unit-tests + nginx -t at release | Unit tests assert proxy_cache_path/limit_req_zone absent from generated redirect configs; nginx -t stays a documented manual server-side release check. | ✓ |
| Release-blocking checkpoint | Additional hard release-blocking gate requiring server-side nginx -t green before tagging. | |

**User's choice:** Unit-tests + nginx -t at release
**Notes:** Claude cannot run nginx locally; automated guarantee carried by test coverage, nginx -t remains a release-time manual check per ROADMAP success criterion 5.

## Claude's Discretion

- Commit granularity / final plan breakdown (ROADMAP suggests 3 plans).
- Exact placement and wording of the cert_key prompt and --help text.
- RELEASE_NOTES.md entry wording/format.

## Deferred Ideas

None — discussion stayed within phase scope.
