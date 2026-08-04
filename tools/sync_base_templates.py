#!/usr/bin/env python3
"""Regenerate the embedded base-config templates from myodoo-docker.

Why this exists
---------------
Two projects deploy the same three files to /etc/nginx:

  * myodoo-docker's ``scripts/deploy-nginx-base.sh`` (from ``scripts/nginx/``)
  * this package's pre-flight / ``--sync_config`` (from embedded constants)

Both used to carry their own copy. They drifted — the embedded ``nginx.conf``
was two revisions behind and lacked the ``limit_req``/``proxy_cache``/
``fastcgi_cache`` zones that vhosts reference — so each tool declared the
other's work "drift" and overwrote it, and on a host whose vhosts used those
zones the pre-flight's repair could not pass ``nginx -t`` at all.

myodoo-docker is the source of truth: those files are what actually ships to
servers. This script copies them into ``config_verification.py`` at development
time. The templates stay **embedded constants** — the package must never depend
on myodoo-docker being present at runtime.

Usage
-----
    python3 tools/sync_base_templates.py --check     # report drift, exit 1
    python3 tools/sync_base_templates.py --write     # rewrite the constants

Run ``--write`` whenever the nginx base files change in myodoo-docker, then
bump the package version. ``--check`` is what the test suite calls.
"""

import argparse
import os
import re
import sys
from pathlib import Path

DEFAULT_SOURCE = Path.home() / "gitbase" / "myodoo-docker" / "scripts" / "nginx"
TARGET = Path(__file__).resolve().parent.parent / "nginx_set_conf" / "config_verification.py"

# Constant name -> path relative to the source directory.
MANAGED = {
    "NGINX_CONF_TEMPLATE": "nginx.conf",
    "GENERAL_CONF_TEMPLATE": "nginxconfig.io/general.conf",
    "SECURITY_CONF_TEMPLATE": "nginxconfig.io/security.conf",
}


def source_dir() -> Path:
    """Where the authoritative files live (override for CI or a clone)."""
    return Path(os.environ.get("MYODOO_DOCKER_NGINX", DEFAULT_SOURCE))


def _constant_pattern(name: str) -> "re.Pattern[str]":
    # The constants are written as NAME = """...""" or NAME = r"""...""".
    return re.compile(rf'({re.escape(name)} = r?""")(.*?)(""")', re.S)


def read_sources() -> "dict[str, str]":
    """Return {constant: file content}. Raises FileNotFoundError if any is absent."""
    base = source_dir()
    contents = {}
    for constant, relative in MANAGED.items():
        path = base / relative
        if not path.is_file():
            raise FileNotFoundError(f"{path} not found — set MYODOO_DOCKER_NGINX")
        contents[constant] = path.read_text(encoding="utf-8")
    return contents


def compare() -> "list[str]":
    """Return the names of constants that differ from their source file."""
    target_text = TARGET.read_text(encoding="utf-8")
    differing = []
    for constant, content in read_sources().items():
        match = _constant_pattern(constant).search(target_text)
        if not match:
            differing.append(f"{constant} (not found in {TARGET.name})")
            continue
        # Byte-exact on purpose: get_template_hash() hashes the raw constant and
        # compares it against the file on the server. A single stray newline
        # would make the two never match, so the pre-flight would report drift
        # on every run and rewrite a file that is already correct.
        if match.group(2) != content:
            differing.append(constant)
    return differing


def write() -> "list[str]":
    """Rewrite the constants from the source files. Returns what changed."""
    original_text = target_text = TARGET.read_text(encoding="utf-8")
    changed = []
    for constant, content in read_sources().items():
        pattern = _constant_pattern(constant)
        match = pattern.search(target_text)
        if not match:
            raise SystemExit(f"{constant} not found in {TARGET} — cannot rewrite it")
        if match.group(2) == content:
            continue
        # Inserted verbatim so the constant is byte-identical to the file that
        # deploy-nginx-base.sh writes — see compare(). A backslash in the
        # payload (security.conf carries regexes) would be re-interpreted by
        # re.sub's replacement syntax, so splice by offset instead.
        start, end = match.span(2)
        target_text = target_text[:start] + content + target_text[end:]
        changed.append(constant)

    # All three must be raw strings. nginx configs are full of regex escapes
    # (`location ~* \.(jpg|...)$`), and in a normal string `\.` raises a
    # SyntaxWarning today and a SyntaxError from Python 3.14 on — the module
    # would stop importing. Normalising here means a future sync cannot
    # reintroduce it.
    for constant in MANAGED:
        target_text = target_text.replace(f'{constant} = """', f'{constant} = r"""')

    # Compare against the original rather than `changed`: the raw-prefix
    # normalisation above can be the only edit in a run.
    if target_text != original_text:
        TARGET.write_text(target_text, encoding="utf-8")
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report drift, exit 1 on any")
    group.add_argument("--write", action="store_true", help="rewrite the constants")
    args = parser.parse_args(argv)

    try:
        if args.check:
            differing = compare()
            if differing:
                print("Embedded templates differ from myodoo-docker:")
                for name in differing:
                    print(f"  - {name}")
                print(f"\nRun: python3 {Path(__file__).name} --write")
                return 1
            print(f"Embedded templates match {source_dir()}.")
            return 0

        changed = write()
        if changed:
            print("Rewritten from " + str(source_dir()) + ":")
            for name in changed:
                print(f"  - {name}")
            print("\nBump the package version and update RELEASE_NOTES.md.")
        else:
            print("Already up to date.")
        return 0
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
