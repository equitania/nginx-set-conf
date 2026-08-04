"""
Guards the single source of the three base config files.

myodoo-docker's ``scripts/nginx/`` is authoritative: those files are what
``deploy-nginx-base.sh`` writes to servers. The constants in
``config_verification.py`` are generated from them by
``tools/sync_base_templates.py``.

They must stay **byte-identical**. ``get_template_hash()`` hashes the raw
constant and compares it against the file on the server, so a single stray
newline would make the pre-flight report drift on every run and rewrite a file
that is already correct — the exact ping-pong this consolidation removes.

Skipped when the myodoo-docker checkout is not present (CI, or a clone without
the sibling repo). Point MYODOO_DOCKER_NGINX at it to run the check there.
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "sync_base_templates.py"

sys.path.insert(0, str(TOOL.parent))
import sync_base_templates as sync  # noqa: E402


pytestmark = pytest.mark.skipif(
    not sync.source_dir().is_dir(),
    reason=f"myodoo-docker nginx sources not found at {sync.source_dir()}",
)


def test_embedded_templates_match_myodoo_docker():
    differing = sync.compare()
    assert not differing, (
        "Embedded base templates drifted from myodoo-docker: "
        + ", ".join(differing)
        + f". Run: python3 {TOOL.relative_to(TOOL.parent.parent)} --write"
    )


def test_check_mode_exits_zero_when_in_sync():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_nginx_conf_keeps_the_zones_vhosts_reference():
    """The regression that started this: an older embedded nginx.conf lacked
    these zones, so a vhost referencing them could not pass nginx -t after the
    pre-flight had 'repaired' the base config."""
    from nginx_set_conf.config_verification import NGINX_CONF_TEMPLATE

    for zone in ("keys_zone=my_cache", "keys_zone=fastcgi_cache",
                 "zone=one:", "zone=addr:"):
        assert zone in NGINX_CONF_TEMPLATE, f"{zone} missing from nginx.conf template"


@pytest.mark.parametrize("constant", sorted(sync.MANAGED))
def test_templates_are_raw_strings(constant):
    """nginx configs carry regex escapes (``location ~* \\.(jpg|...)$``). In a
    normal string literal ``\\.`` raises a SyntaxWarning today and a
    SyntaxError from Python 3.14 on — the module would stop importing."""
    source = sync.TARGET.read_text(encoding="utf-8")
    assert f'{constant} = r"""' in source, (
        f"{constant} must be a raw string; run tools/sync_base_templates.py --write"
    )


def test_module_imports_without_syntax_warning():
    import py_compile
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        py_compile.compile(str(sync.TARGET), doraise=True)


def test_security_conf_csp_allows_unsafe_eval():
    """Odoo 17+ compiles OWL templates via new Function(). A CSP without
    'unsafe-eval' renders the login page blank, client-side, with nothing in
    the nginx log."""
    from nginx_set_conf.config_verification import SECURITY_CONF_TEMPLATE

    csp = [l for l in SECURITY_CONF_TEMPLATE.splitlines()
           if "Content-Security-Policy" in l and not l.lstrip().startswith("#")]
    for line in csp:
        assert "'unsafe-eval'" in line, (
            "active CSP without 'unsafe-eval' breaks Odoo 19: " + line.strip()
        )
