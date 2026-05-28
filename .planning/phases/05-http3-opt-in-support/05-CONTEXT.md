# Phase 5: HTTP/3 opt-in support — Context

**Gathered:** 2026-05-28
**Status:** Ready for planning
**Source:** `/gsd:discuss-phase --all` (HTTP/3 protocol scope review)

<domain>
## Phase Boundary

Phase 5 delivers a new opt-in `--enable_http3` CLI flag (and its YAML
equivalent `enable_http3: true`) that adds QUIC + HTTP/3 listen
directives to **12 of 17 templates** — the browser/end-user-facing SSL
templates. The phase does NOT change the default behaviour for any
existing operator: the flag must be set explicitly, the firewall must
be opened separately (UDP/443), and an nginx-version gate refuses to
emit `quic` directives on too-old nginx.

This phase deliberately follows the v1.10.0 lessons learned: a mass
template rewrite touching `listen` lines is exactly the shape of the
21.04.2026 incident. The mitigations are: opt-in (no default change),
nginx-version pre-write gate, default-server QUIC catch-all, and
atomic per-vhost emission (no `--migrate_to_http3` in this phase —
that is v2 work, see `REQUIREMENTS.md` §PROTO-V2-01).
</domain>

<decisions>
## Implementation Decisions

### Scope: which templates get HTTP/3

**Included (12 templates)** — browser/end-user web UIs and PWAs:

| Template | Rationale |
|---|---|
| `odoo_ssl` | ERP web UI, longpoll, mobile workforce |
| `flowise` | AI workflow UI, streaming responses |
| `n8n` | Workflow automation web UI |
| `nextcloud` | File sync clients + browser UI, large transfers |
| `guacamole` | Browser RDP/VNC — latency-sensitive |
| `kasm` | Browser VDI — latency-sensitive |
| `pgadmin` | Postgres admin UI (low traffic, harmless inclusion) |
| `portainer` | Docker management UI |
| `pwa` | Generic PWA shell (HTTP/3 ideal for PWA) |
| `code_server` | VSCode in browser, developer UX |
| `supabase` | Backend-as-a-service, mixed API + browser |
| `qdrant` | **REST port only** — gRPC port stays HTTP/2 |

**Excluded (5 templates + qdrant gRPC port)**:

| Template / port | Rationale |
|---|---|
| `fast_report` | Server-to-server PDF API — no browser traffic |
| `mailpit` | Dev SMTP test tool, internal-only |
| `redirect` | HTTP-only — no TLS, no HTTP/3 |
| `redirect_ssl` | Trivial 301 response — UDP/QUIC overhead not worth it |
| `default_ssl_reject` | SNI catch-all returns 444 — no useful response |
| `odoo_http` | HTTP-only — no TLS |
| `qdrant` gRPC port | gRPC over QUIC is non-standard; gRPC+HTTP/2 stays |

The exclusion list is **encoded** (not just documented). The
validator rejects `--enable_http3` for excluded templates with a
clear message naming the rationale.

### CLI / YAML surface

- New CLI flag: `--enable_http3` (boolean, default `False`).
- New YAML key: `enable_http3: true` (default omitted = `False`).
- Passed through `execute_commands` exactly the same way as
  `disable_domain_listen`.
- Validated in `validators.py` against the per-template exclusion
  list (see Scope above).
- README documents both surfaces with a banner-style callout.

### Generated directives (per HTTP/3-enabled vhost)

The emitted SSL server block grows by these directives:

```nginx
# inside the HTTPS server block, after the existing `listen ... ssl;`:
listen ip.ip.ip.ip:443 quic reuseport;
listen [::]:443 quic reuseport;       # only if IPv6 listen is present
http3 on;
quic_retry on;
ssl_protocols TLSv1.3;                # HTTP/3 requires TLS 1.3
add_header Alt-Svc 'h3=":443"; ma=86400' always;
```

**`reuseport` rule:** at most ONE listen directive per (IP, port)
across the entire host may carry `reuseport`. If multiple
HTTP/3-enabled vhosts share the same IP, only the first emits
`reuseport`. Tracking mechanism options (decided in planning):
- Per-host state file under `/var/lib/nginx-set-conf/` (mirrors the
  pattern already used for backups)
- Or: detect `reuseport` already present in `/etc/nginx/conf.d/`
  before emit
- Or: punt to operator with documented "first config wins" rule

Default decision (subject to planning override): **detect at deploy
time** by grepping the target directory for an existing `quic
reuseport` on the same `(ip, port)` pair. If found, omit
`reuseport` on this vhost.

### nginx version gate

Before writing any HTTP/3-emitting config, the tool runs:

```bash
nginx -v 2>&1
```

Parses the output (`nginx version: nginx/1.27.2` → `1.27.2`) and
compares to `1.25.0`. **If the installed nginx is older, the tool
aborts via `click.ClickException`** with a message:

```
HTTP/3 requires nginx ≥ 1.25.0 (you have 1.24.0).
Either upgrade nginx (Debian: bookworm-backports; Ubuntu: 24.04+;
RHEL: 9.4+) or omit --enable_http3 to ship HTTP/2-only configs.
```

The check is mandatory because `listen ... quic` on nginx 1.24
fails `nginx -t` with `[emerg] unknown directive "quic"`, and at
that point the v1.11.1 reload gate has already saved the live
nginx — but the operator-facing error is opaque. The version gate
makes the failure intelligible.

The version detection is testable: extract `nginx -v` parsing into
a helper that can be unit-tested with mocked output.

### Default-server QUIC catch-all

The v1.10.0 incident root cause was wildcard `listen 443 ssl;`
without a `default_server` catch-all → SNI fallback served the
wrong cert for unknown hostnames. The HTTP/3 surface has the same
risk shape: a QUIC connection for an unknown SNI falls back to the
first-loaded QUIC server block.

**Mitigation:** the `default_ssl_reject` template is extended (or a
sibling `default_quic_reject` template is added) so that any host
running at least one HTTP/3-enabled vhost ALSO gets a
QUIC-catch-all that returns 444 for unknown SNI. The
`--setup_default` flow installs both TCP and QUIC catch-alls when
the host has any HTTP/3 config present.

The decision between "extend `default_ssl_reject`" vs "add
`default_quic_reject`" is a planning-time call — `default_ssl_reject`
is currently a single template; if it cleanly extends, do that;
otherwise split.

### TLS 1.3 scoping

The embedded `NGINX_CONF_TEMPLATE` currently sets
`ssl_protocols TLSv1.2 TLSv1.3;` globally. HTTP/3 requires TLS 1.3
specifically. Two options:

1. **Scoped override (preferred):** emit `ssl_protocols TLSv1.3;`
   inside the HTTP/3 server block only. The non-HTTP/3 server block
   keeps the global TLS 1.2+1.3 default. Browsers fall back to
   TCP/HTTP/2 (which supports TLS 1.2) for legacy clients.
2. Global TLS-1.3-only: would deny TLS 1.2 clients on every vhost
   the operator runs. **Rejected** — too disruptive.

Chosen: option 1 (scoped).

### Alt-Svc + browser behaviour

Browsers learn about HTTP/3 availability via the `Alt-Svc`
response header on the initial TCP/HTTP/2 connection. The header
is set to:

```
Alt-Svc: h3=":443"; ma=86400
```

`ma=86400` (24h) caches the H3 endpoint client-side for a day,
limiting churn when the operator toggles the flag.

The `always` modifier ensures the header is set on error responses
too, otherwise nginx omits it on 5xx.

### Migration: deferred to v2

A `--migrate_to_http3` server-side flag (analog to
`--migrate_to_wildcard`) is explicitly **out of scope** for Phase 5.
The reasoning is the same as why `--migrate_to_ip_bound` was deferred
in v1.11.0: a mass server-side `listen`-line rewrite is high-risk
and we should ship the per-vhost emission first, watch one or two
deployments, then decide whether bulk migration is worth the
risk-engineered tooling. Captured as `PROTO-V2-01` in
`REQUIREMENTS.md`.

### Claude's Discretion (planning-time decisions)

Items the planner can decide without re-asking:

- Whether to add a new sibling template `default_quic_reject` or
  extend `default_ssl_reject` to also handle QUIC.
- The exact mechanism for `reuseport` tracking (per-host state vs
  deploy-time detect).
- Whether `--enable_http3` is a boolean flag or carries an opt-in
  value like `--enable_http3 reject-fallback` for future extension
  (currently boolean; YAGNI for the value form).
- Test approach for `nginx -v` parsing (mock vs golden).
- README admonition style (Markdown blockquote vs HTML callout —
  see existing README conventions).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before
investigating or implementing.**

### Project state
- `.planning/PROJECT.md` — project context, constraints, core value.
- `.planning/REQUIREMENTS.md` §PROTO — PROTO-02..06 with citations.
- `.planning/ROADMAP.md` §Phase 5 — success criteria and plan
  placeholders.

### Codebase map (this is the input that surfaced the HTTP/3 topic)
- `.planning/codebase/STACK.md` — Python/Click/hatchling/UV.
- `.planning/codebase/ARCHITECTURE.md` — substitution pipeline,
  `execute_commands` call graph.
- `.planning/codebase/STRUCTURE.md` — per-template module layout.
- `.planning/codebase/CONCERNS.md` — the original audit (HTTP/2 gap
  added in the same edit that created this CONTEXT.md).

### Source files that will change
- `nginx_set_conf/nginx_set_conf.py` — Click CLI surface, where
  `--enable_http3` is wired.
- `nginx_set_conf/utils.py` — `execute_commands`, where the flag
  propagates into template substitution.
- `nginx_set_conf/validators.py` — exclusion list enforcement,
  per-template gate.
- `nginx_set_conf/templates/*.py` — the 12 included templates get
  HTTP/3 directives; 5 excluded templates stay unchanged.
- `nginx_set_conf/templates/default_ssl_reject.py` — extended for
  QUIC catch-all (or a sibling `default_quic_reject.py` is added).
- `nginx_set_conf/config_verification.py` — embedded
  `NGINX_CONF_TEMPLATE` may need `http3 on;` at `http {}` level
  depending on the chosen emit pattern.
- `README.md` + `RELEASE_NOTES.md` — operator-facing docs.

### nginx documentation (researcher will need this)
- nginx docs: HTTP/3 module configuration (`http3`, `quic_retry`,
  `listen ... quic`, `Alt-Svc`).
- nginx changelog 1.25.0 (May 2023) for HTTP/3 stabilisation.
- Mozilla SSL Configuration Generator — confirms TLS 1.3 + HTTP/3
  intermediate config.

### v1.10.0 incident context (MUST READ before touching listen lines)
- `~/.claude/skills/nginx-set-conf/SKILL.md` §DANGER ZONE — listen
  directives and the v1.10.0 SNI-fallback incident.
- `git log v1.10.0..v1.11.0 -- nginx_set_conf/templates/` — see the
  shape of the revert and the IP-bound default arrival.

</canonical_refs>

<specifics>
## Specific Ideas Raised in Discussion

- **Captain's input verbatim (2026-05-28):** "Es gibt ja neben
  HTTP/2 inzwischen das HTTP/3-Protokoll. Und du hast mir auch
  schon gesagt, dass ich bei der Firewall das Protokoll UDP auf
  Port 443 aufmachen muss, weil das Ganze gegebenenfalls
  unterstützt wird. Du schaust dir jetzt mal alle Templates an und
  welche Systeme wir unterstützen, und überlegst bzw. überprüfst,
  bei welchen der Installationen HTTP/3 überhaupt verfügbar
  gemacht werden kann und sollte."

  → Captured: UDP/443 firewall is OPERATOR-side; the tool documents
  it but does not (and cannot) modify host firewall rules.
  → Captured: template-by-template applicability matrix is the
  artefact (see Scope above).

- **General audit re-request:** the Captain asked for a broader
  performance/quality/security review. CONCERNS.md (2026-05-28) is
  the canonical answer for security + correctness + tech-debt. The
  HTTP/2 finding (now logged) is the only material gap found during
  this discuss-phase. Phase 4's success criterion #4 already
  schedules a re-audit before v1.12 release. No separate
  re-audit phase is added.

</specifics>

<deferred>
## Deferred Ideas

- **Atomic `--migrate_to_http3`** — bulk server-side migration.
  Deferred to v2 (`PROTO-V2-01`). Rationale: ship per-vhost emit
  first, learn from one or two real deployments, then decide
  whether the bulk-rewrite tooling is worth the v1.10.0-class
  risk.
- **0-RTT (`ssl_early_data on;`)** — improves resumption latency
  but exposes replay-attack vectors for non-idempotent requests.
  Deferred to v2 (`PROTO-V2-02`).
- **Connection migration / address rebinding tuning** —
  `quic_max_idle_timeout`, `quic_max_ack_delay`. nginx defaults are
  sane for v1.12; revisit if operators report mobile-network
  rebinding issues.
- **Datagram (`http3_hq` / WebTransport)** — too early; no
  production demand surfaced.

</deferred>

---

*Phase: 05-http3-opt-in-support*
*Context gathered: 2026-05-28 via `/gsd:discuss-phase --all`*
