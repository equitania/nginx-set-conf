# CLAUDE.md

nginx-set-conf is a Python Click CLI that generates nginx reverse-proxy vhosts for Docker services from
templates (`nginx_set_conf/templates/`) and keeps three base configs (`nginx.conf`, `general.conf`,
`security.conf`) in sync on the server. Design details, invariants and incident history live in the
`nginx-set-conf` skill — load it before touching listen directives, HTTP/3, pre-flight or validators.

## Setup

```bash
uv venv && venv+
uv pip install -e ".[dev]"
```

## What can run here and what cannot

- **Runs locally:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy nginx_set_conf`, `uv build`, and `--dry_run` / `show` / `templates` / `--help`.
  CI runs exactly the lint, format, mypy and test steps — all must be green.
- **Never here:** real deploys, `verify`/`sync`/`backup` against a server, nginx reloads. They need
  root and `/etc/nginx` on a server; the user runs them. When unsure what exists on a server, ask.
- **Publishing is local only** (`uv build` + `uvpublish` by the user) — never add a publish step to CI.

## Rules that are easy to get wrong

- **The flag-only call form must keep working.** Operators copy
  `nginx-set-conf --config_path=/root/docker-builds/ngx-conf` between servers; it is routed to the
  hidden `legacy` command. Keep it on one line in `--help`.
- **Base-config source of truth is myodoo-docker**, not `yaml_examples/`. Update the embedded
  constants in `config_verification.py` only via `python3 tools/sync_base_templates.py --write`;
  `--check` runs in the test suite. The copies under `yaml_examples/nginxconfig.io/` are stale.
- **New template:** module in `templates/`, entry in `TEMPLATES` **and** `TEMPLATE_DESCRIPTIONS`
  (`all_templates.py`), name in `VALID_TEMPLATES` (`validators.py`), test in `tests/test_templates.py`,
  example in `yaml_examples/server_config/config.yaml`. `ip.ip.ip.ip` is for `listen` lines only;
  upstreams use `{{BACKEND_IP}}`.
- **Version bump:** `bump-my-version bump patch --allow-dirty --no-commit --no-tag`, then `uv lock`.
  The config table must stay `[tool.bumpversion]` (1.5+ silently ignores `[tool.bump-my-version]`).
- **`ruff format .` must not touch `.planning/`** (excluded in `pyproject.toml`; ruff 0.16 formats
  Markdown code blocks).
- **This repo is mirrored to public GitHub** (`upstream`): examples use `example.com`, `1.2.3.4`,
  `203.0.113.x` — never real customer IPs or hostnames, also not in tests or release notes.
