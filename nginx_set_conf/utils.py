"""
Utility functions for Nginx configuration management.

This module provides helper functions for managing Nginx configurations,
including YAML parsing, configuration deployment, and input validation.
All functions are designed to work with the nginx_set_conf package.

Typical usage example:
    yaml_config = parse_yaml('config.yaml')
    execute_commands(yaml_config['template'], yaml_config['domain'], ...)
"""

# -*- coding: utf-8 -*-
# Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import contextlib
import ipaddress
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import click
import yaml

from .templates.all_templates import get_config_template, CACHE_PATH_SENTINEL
from .validators import ValidationError, validate_all_inputs

# Matches `listen <hostname>:<port>[ ssl];` — i.e. hostname-bound listen
# directives produced by templates before v1.10.0's aborted wildcard
# migration. IP addresses (start with a digit) and IPv6 brackets (start with
# `[`) are intentionally excluded so real IP-bound listens stay untouched.
_HOSTNAME_LISTEN_PATTERN = re.compile(
    r"^(\s*listen\s+)"
    r"([a-zA-Z][a-zA-Z0-9.\-]*)"
    r":(\d+)"
    r"(\s+ssl)?"
    r"\s*;",
    re.MULTILINE,
)

logger = logging.getLogger("nginx_set_conf")


# Prefix used in generated filenames to represent a wildcard domain. Keeps
# the `*` glob character out of `/etc/nginx/conf.d/` filenames while still
# making the wildcard intent obvious to operators.
_WILDCARD_FILENAME_PREFIX = "_wildcard."


def _safe_conf_filename(domain: str) -> str:
    """Return a glob-safe filename stem for a (possibly wildcard) domain.

    Wildcard prefixes (``*.``) are rewritten to a literal token so the
    generated filename never contains a shell glob character. The nginx
    ``server_name`` directive inside the file is unaffected — the domain
    is still substituted verbatim into the template content. Only the
    on-disk filename is rewritten.

    Example:
        ``*.example.com`` → ``_wildcard.example.com``
        ``example.com`` → ``example.com`` (unchanged)
    """
    if domain.startswith("*."):
        return _WILDCARD_FILENAME_PREFIX + domain[2:]
    return domain


def fire_all_functions(function_list: list) -> None:
    """Executes a list of functions in sequence.

    Args:
        function_list: A list of callable functions to be executed.
    """
    for func in function_list:
        func()


def self_clean(input_dictionary: dict) -> dict:
    """Removes duplicate values from dictionary values while preserving keys.

    Args:
        input_dictionary: Dictionary to clean.

    Returns:
        A new dictionary with duplicate values removed from each key's value list.
    """
    return_dict = input_dictionary.copy()
    for key, value in input_dictionary.items():
        return_dict[key] = list(dict.fromkeys(value))
    return return_dict


def parse_yaml(yaml_file: str) -> dict:
    """Parses a YAML file into a Python dictionary.

    Args:
        yaml_file: Path to the YAML file to parse.

    Returns:
        Dictionary containing the parsed YAML data.
        Returns False if parsing fails.

    Raises:
        yaml.YAMLError: If the YAML file is malformed.
    """
    with open(yaml_file) as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.error("YAML parse error: %s", exc)
            return False


def parse_yaml_folder(path: str) -> list:
    """Parses all YAML files in a directory.

    Searches for files with .yaml or .yml extensions in the specified directory
    and parses each one into a Python object.

    Args:
        path: Directory path containing YAML files.

    Returns:
        List of parsed YAML objects.
    """
    yaml_objects = []
    for file in os.listdir(path):
        if file.endswith(".yaml") or file.endswith(".yml"):
            yaml_object = parse_yaml(os.path.join(path, file))
            if yaml_object:
                yaml_objects.append(yaml_object)
    return yaml_objects


def get_default_vars() -> dict:
    """Returns default variables for Nginx configuration.

    Returns:
        Dictionary containing default values for Nginx configuration variables
        including server paths, domains, ports, and certificate locations.
    """
    return {
        "server_path": "/etc/nginx/conf.d",
        "template_domain": "server.domain.de",
        "template_ip": "ip.ip.ip.ip",
        "template_port": "{{PORT}}",
        "template_poll_port": "{{POLL_PORT}}",
        "template_grpc_port": "{{GRPC_PORT}}",
        "template_crt": "zertifikat.crt",
        "template_key": "zertifikat.key",
        "template_self_crt": "/etc/letsencrypt/live/zertifikat.crt/fullchain.pem",
        "template_self_key": "/etc/letsencrypt/live/zertifikat.key/privkey.pem",
        "template_redirect_domain": "target.domain.de",
        "template_auth_file": "authfile",
        "template_backend_ip": "{{BACKEND_IP}}",
    }


# 16x the longest valid domain (253 chars); caps piped stdin
_MAX_INPUT_LENGTH = 4096


def retrieve_valid_input(message: str) -> str:
    """Prompt user for input until non-empty input is provided.

    Iterative (not recursive) to avoid stack overflow on repeated empty input.
    Caps input at _MAX_INPUT_LENGTH characters; handles EOFError gracefully.

    Args:
        message: Prompt message to display to user.

    Returns:
        User's non-empty input string.
    """
    while True:
        try:
            user_input = input(message)
        except EOFError:
            click.echo("\nNo input received (EOF). Exiting.")
            raise SystemExit(1)
        user_input = user_input[:_MAX_INPUT_LENGTH]
        if user_input:
            return user_input


def retrieve_optional_input(message: str) -> str:
    """Prompt user for optional input; empty input is accepted and returns "".

    Unlike retrieve_valid_input, this does NOT loop on empty input — it is used
    for prompts where leaving the field blank is a valid, meaningful choice
    (e.g. cert_key empty => Let's Encrypt auto-generation). Caps input at
    _MAX_INPUT_LENGTH characters; handles EOFError gracefully.

    Args:
        message: Prompt message to display to user.

    Returns:
        User's input string, or "" if the user left it blank.
    """
    try:
        user_input = input(message)
    except EOFError:
        click.echo("\nNo input received (EOF). Exiting.")
        raise SystemExit(1)
    return user_input[:_MAX_INPUT_LENGTH]


@contextlib.contextmanager
def _restrictive_umask():
    """Context manager: set umask 0o077, restore on exit."""
    old_umask = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old_umask)


def _run_command(args: list, dry_run: bool = False, check: bool = False) -> bool:
    """Run a system command safely using subprocess.

    Args:
        args: Command and arguments as a list.
        dry_run: If True, only print command without executing.
        check: If True, raise on non-zero exit code.

    Returns:
        True if command succeeded, False otherwise.
    """
    cmd_str = " ".join(args)
    if dry_run:
        logger.info("[DRY RUN] Would execute: %s", cmd_str)
        return True
    try:
        logger.info("Executing: %s", cmd_str)
        result = subprocess.run(args, capture_output=True, text=True, check=check)
        if result.stdout:
            logger.debug("stdout: %s", result.stdout.strip())
        if result.stderr:
            logger.debug("stderr: %s", result.stderr.strip())
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error("Command failed: %s (exit code %d)", cmd_str, e.returncode)
        return False
    except FileNotFoundError:
        logger.error("Command not found: %s", args[0])
        return False


def _format_ip_for_nginx(ip: str) -> str:
    """Wrap IPv6 addresses in brackets for nginx URL contexts.

    In nginx proxy_pass/grpc_pass directives, IPv6 addresses must be
    enclosed in square brackets. IPv4 addresses are returned unchanged.

    Args:
        ip: IP address string (IPv4 or IPv6).

    Returns:
        Formatted IP string with brackets for IPv6.
    """
    try:
        addr = ipaddress.ip_address(ip)
        if addr.version == 6:
            return f"[{ip}]"
    except ValueError:
        pass
    return ip


def _warn_public_backend_ip(ip: str) -> None:
    """Log a warning if a public IP is used as backend proxy address.

    Docker containers typically bind to 127.0.0.1 (loopback) for security,
    especially when using UFW or similar firewalls. Using a public IP as
    the proxy_pass backend will fail if the container only listens on loopback.
    """
    try:
        addr = ipaddress.ip_address(ip)
        if not addr.is_loopback and not addr.is_private:
            logger.warning(
                "Public IP %s used as backend address (proxy_pass). "
                "Docker containers typically bind to 127.0.0.1 for security (UFW compatibility). "
                "Use 'ip: 127.0.0.1' if the container listens on loopback only.",
                ip,
            )
    except ValueError:
        pass


def _replace_placeholder(content: str, old: str, new: str) -> str:
    """Replace a placeholder in template content.

    Args:
        content: Template content string.
        old: Placeholder to replace.
        new: Replacement value.

    Returns:
        Content with placeholder replaced.
    """
    return content.replace(old, new)


def _insert_after_marker(content: str, marker: str, insert_lines: list, first_only: bool = True) -> str:
    """Insert lines after a marker in the content.

    Args:
        content: Full content string.
        marker: Marker string to search for.
        insert_lines: Lines to insert after marker.
        first_only: If True, only insert after first occurrence.

    Returns:
        Content with lines inserted after marker.
    """
    lines = content.split("\n")
    new_lines = []
    found = False

    for line in lines:
        new_lines.append(line)
        if marker in line and (not found or not first_only):
            new_lines.extend(insert_lines)
            found = True

    return "\n".join(new_lines)


def get_nginx_version() -> "tuple[int, int, int] | None":
    """Parse nginx version from ``nginx -v`` stderr output.

    Returns:
        (major, minor, patch) tuple, or None if nginx is not found or
        the version string cannot be parsed.  Never raises.
    """
    try:
        result = subprocess.run(
            ["nginx", "-v"],
            capture_output=True,
            text=True,
        )
        # nginx -v writes to stderr: "nginx version: nginx/1.27.2"
        match = re.search(r"nginx/(\d+)\.(\d+)\.(\d+)", result.stderr)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except FileNotFoundError:
        pass
    return None


def _quic_reuseport_already_claimed(conf_dir: str, ip: str, port: int = 443) -> bool:
    """Return True if any .conf in conf_dir already carries a quic reuseport listen
    on this port — either IP-bound (``listen <ip>:<port> quic reuseport;``) OR the
    wildcard form emitted by the default_ssl_reject catch-all
    (``listen <port> quic default_server reuseport;``).

    Only one listen directive per (IP, port) may carry reuseport across the entire
    nginx host.  If already claimed, the new vhost must omit it.

    Returns False on any filesystem error (safe default: include reuseport when
    the conf_dir cannot be read, so the operator sees a startup error rather than
    silently missing the socket).
    """
    # IP prefix is OPTIONAL — the default_ssl_reject QUIC catch-all uses a
    # wildcard ``listen 443 quic ... reuseport;`` with no IP prefix.  The scanner
    # MUST match both forms or vhosts would double-claim reuseport on UDP/443
    # and break nginx reload (Phase 5 BLOCKER 3).
    pattern = re.compile(
        rf"listen\s+(?:{re.escape(ip)}:)?{port}\s+quic\b.*\breuseport"
    )
    try:
        for fname in os.listdir(conf_dir):
            if not fname.endswith(".conf"):
                continue
            fpath = os.path.join(conf_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                if pattern.search(f.read()):
                    return True
    except (OSError, PermissionError):
        pass
    return False


def _inject_http3_directives(
    content: str,
    formatted_listen_ip: str,
    conf_dir: str | None = None,
) -> str:
    """Inject QUIC/HTTP/3 directives after the first ``listen <ip>:443 ssl;`` line.

    Inserts the QUIC listen line plus four companion directives immediately after
    the first occurrence of ``listen {formatted_listen_ip}:443 ssl;`` in *content*.
    Uses ``first_only=True`` so a second server block (e.g. qdrant gRPC) is left
    untouched.

    Args:
        content: Already-substituted nginx config string (IP placeholder already
            replaced with ``formatted_listen_ip``).
        formatted_listen_ip: The real IP address, formatted for nginx listen
            directives (e.g. "1.2.3.4" or "[2001:db8::1]").  MUST be the value
            produced by ``_format_ip_for_nginx`` — never the raw placeholder.
        conf_dir: Path to the nginx conf.d directory.  When provided,
            ``_quic_reuseport_already_claimed`` is consulted and ``reuseport``
            is omitted when already claimed by another vhost.  Defaults to None
            (reuseport always included — safe for first deployment).

    Returns:
        Modified content string with HTTP/3 directives injected.  Returns
        *content* unchanged (with a warning log) if the marker is not found.

    Note:
        IPv6 QUIC injection is intentionally absent: none of the 12 HTTP/3-
        included templates carry a ``listen [::]:443 ssl;`` line (only
        default_ssl_reject does, and that template is excluded from
        --enable_http3).  If a future template gains an IPv6 ssl listen this
        function must be extended.
    """
    marker = f"listen {formatted_listen_ip}:443 ssl;"

    if conf_dir is not None and _quic_reuseport_already_claimed(conf_dir, formatted_listen_ip):
        reuseport_suffix = ""
    else:
        reuseport_suffix = " reuseport"

    # CR-02: deliberately NO `ssl_protocols TLSv1.3;` here. The QUIC listener
    # negotiates TLS 1.3 at the protocol level regardless (QUIC mandates it),
    # so adding a server-scope ssl_protocols directive would override the
    # http-scope `ssl_protocols TLSv1.2 TLSv1.3;` and drop TLSv1.2 fallback for
    # the TCP/443 (HTTP/2) listener sharing this server block — violating
    # ROADMAP SC-1 ("TCP/443 server block remains unchanged").
    insert_lines = [
        f"    listen {formatted_listen_ip}:443 quic{reuseport_suffix};",
        "    http3 on;",
        "    quic_retry on;",
        "    add_header Alt-Svc 'h3=\":443\"; ma=86400' always;",
    ]

    result = _insert_after_marker(content, marker, insert_lines, first_only=True)

    if result == content:
        logger.warning(
            "_inject_http3_directives: marker '%s' not found in content — "
            "no HTTP/3 directives injected",
            marker,
        )

    return result


def _create_cert_if_needed(cert_name: str, dry_run: bool = False) -> None:
    """Check for Let's Encrypt certificate and create if missing.

    Args:
        cert_name: Certificate/domain name.
        dry_run: If True, only print what would be done.
    """
    if dry_run:
        logger.info(
            "[DRY RUN] Would check for and possibly create certificate for: %s",
            cert_name,
        )
        return

    fullchain = f"/etc/letsencrypt/live/{cert_name}/fullchain.pem"
    privkey = f"/etc/letsencrypt/live/{cert_name}/privkey.pem"
    cert_exists = os.path.isfile(fullchain) and os.path.isfile(privkey)

    if not cert_exists:
        _run_command(["systemctl", "stop", "nginx.service"])
        _run_command(
            [
                "certbot",
                "certonly",
                "--standalone",
                "--agree-tos",
                "--register-unsafely-without-email",
                "-d",
                cert_name,
            ]
        )
        logger.info("Certificate created for: %s", cert_name)


def _rewrite_listen_directives(content: str) -> tuple[str, int]:
    """Rewrite `listen <hostname>:<port>[ ssl];` to `listen <port>[ ssl];`.

    Returns:
        Tuple of (new_content, number_of_substitutions).
    """
    count = 0

    def _sub(match: re.Match) -> str:
        nonlocal count
        count += 1
        prefix = match.group(1)
        port = match.group(3)
        ssl_part = match.group(4) or ""
        return f"{prefix}{port}{ssl_part};"

    new_content = _HOSTNAME_LISTEN_PATTERN.sub(_sub, content)
    return new_content, count


def migrate_configs_to_wildcard(
    conf_dir: str = "/etc/nginx/conf.d",
    backup_root: str = "/var/backups/nginx_set_conf",
    dry_run: bool = False,
) -> bool:
    """Atomically migrate hostname-bound listen directives to wildcard form.

    Scans `conf_dir` for `*.conf` files, finds every
    `listen <hostname>:<port>[ ssl];` directive and rewrites it as
    `listen <port>[ ssl];`. A timestamped backup of every file that would
    change is written to `backup_root` before any modification. If the
    subsequent `nginx -t` fails, all migrated files are restored from the
    backup.

    This is the recommended migration path for users who want the DNS
    parse-time-independent listen behaviour introduced by v1.10.0. The
    atomic all-or-nothing semantics prevent the partial-migration SNI
    fallback that caused the v1.10.0 production incident.

    Args:
        conf_dir: Directory containing *.conf files to migrate.
        backup_root: Root directory for timestamped backups.
        dry_run: If True, report planned changes without writing.

    Returns:
        True if migration succeeded (or if dry_run), False on any error.
    """
    conf_path = Path(conf_dir)
    if not conf_path.is_dir():
        logger.error("Config directory not found: %s", conf_dir)
        return False

    conf_files = sorted(conf_path.glob("*.conf"))
    if not conf_files:
        logger.warning("No *.conf files found in %s", conf_dir)
        return True

    # Scan for affected files
    affected: dict[Path, tuple[str, int]] = {}
    for conf_file in conf_files:
        try:
            content = conf_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Cannot read %s: %s", conf_file, e)
            return False
        new_content, count = _rewrite_listen_directives(content)
        if count > 0:
            affected[conf_file] = (new_content, count)

    if not affected:
        logger.info("No hostname-bound listen directives found; nothing to migrate")
        return True

    logger.info("Migration preview (%d file(s) to change):", len(affected))
    for conf_file, (_, count) in affected.items():
        logger.info("  %s: %d directive(s)", conf_file, count)

    if dry_run:
        logger.info("[DRY RUN] No changes written")
        return True

    # Create backup
    try:
        backup_root_path = Path(backup_root)
        backup_root_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_root_path / f"migrate_to_wildcard_{timestamp}"
        if backup_path.exists() or backup_path.is_symlink():
            logger.error("Backup target already exists: %s", backup_path)
            return False
        backup_path.mkdir(mode=0o700, exist_ok=False)
        for conf_file in affected:
            shutil.copy2(conf_file, backup_path / conf_file.name)
        logger.info("Backup created at: %s", backup_path)
    except OSError as e:
        logger.error("Backup failed: %s", e)
        return False

    # Write migrated content
    written: list[Path] = []
    try:
        for conf_file, (new_content, _) in affected.items():
            conf_file.write_text(new_content, encoding="utf-8")
            written.append(conf_file)
        logger.info("Wrote %d migrated config file(s)", len(written))
    except OSError as e:
        logger.error("Write failed: %s — rolling back from %s", e, backup_path)
        for wf in written:
            try:
                shutil.copy2(backup_path / wf.name, wf)
            except OSError as rollback_err:
                logger.error("Rollback failed for %s: %s", wf, rollback_err)
        return False

    # Validate via nginx -t
    if not _run_command(["nginx", "-t"]):
        logger.error("nginx -t failed after migration — rolling back from %s", backup_path)
        for wf in written:
            try:
                shutil.copy2(backup_path / wf.name, wf)
            except OSError as rollback_err:
                logger.error("Rollback failed for %s: %s", wf, rollback_err)
        return False

    logger.info("Migration complete. Reload nginx to activate: systemctl reload nginx")
    return True


def setup_default_server(
    target_path: str = "/etc/nginx/conf.d",
    ssl_dir: str = "/etc/nginx/ssl",
    cert_file: str = "default.crt",
    key_file: str = "default.key",
    dry_run: bool = False,
) -> bool:
    """Install the default_ssl_reject catch-all block.

    Generates a self-signed sacrificial certificate (if missing) and writes
    the default_ssl_reject template to `<target_path>/00-default.conf`. The
    filename prefix `00-` ensures nginx loads it before any domain-specific
    config, so it wins the `default_server` election for `listen 80` and
    `listen 443 ssl` — but only for wildcard listen sockets. If the host
    still has hostname-bound listen directives, migrate them first via
    `migrate_configs_to_wildcard` or the `--migrate_to_wildcard` CLI flag.

    Args:
        target_path: Directory for 00-default.conf (default: /etc/nginx/conf.d).
        ssl_dir: Directory for the self-signed cert/key (default: /etc/nginx/ssl).
        cert_file: Cert filename (default: default.crt).
        key_file: Key filename (default: default.key).
        dry_run: If True, log intended actions without executing.

    Returns:
        True on success (or in dry-run), False on error.
    """
    cert_path = os.path.join(ssl_dir, cert_file)
    key_path = os.path.join(ssl_dir, key_file)
    conf_path = os.path.join(target_path, "00-default.conf")

    if dry_run:
        logger.info("[DRY RUN] Would create SSL dir: %s", ssl_dir)
        logger.info("[DRY RUN] Would generate self-signed cert: %s / %s", cert_path, key_path)
        logger.info("[DRY RUN] Would write default config: %s", conf_path)
        return True

    try:
        os.makedirs(ssl_dir, exist_ok=True)
    except OSError as e:
        logger.error("Could not create SSL directory %s: %s", ssl_dir, e)
        return False

    # The cert is never presented to legitimate clients — the server
    # `return 444`s the connection right after the TLS handshake. A
    # throwaway CN is fine.
    cert_exists = os.path.isfile(cert_path) and os.path.isfile(key_path)
    if not cert_exists:
        logger.info("Generating self-signed default cert at %s", cert_path)
        with _restrictive_umask():
            ok = _run_command(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-nodes",
                    "-days",
                    "3650",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    key_path,
                    "-out",
                    cert_path,
                    "-subj",
                    "/CN=default-reject",
                ]
            )
        if not ok:
            logger.error("Failed to generate self-signed default cert")
            return False
    else:
        logger.info("Self-signed default cert already exists, skipping generation")

    content = get_config_template("default_ssl_reject")
    if not content:
        logger.error("default_ssl_reject template not found in registry")
        return False

    try:
        os.makedirs(target_path, exist_ok=True)
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Wrote default config: %s", conf_path)
    except OSError as e:
        logger.error("Could not write %s: %s", conf_path, e)
        return False

    return True


def execute_commands(
    config_template,
    domain,
    ip,
    cert_name,
    cert_key,
    port,
    pollport,
    redirect_domain,
    auth_file,
    allowed_ips,
    target_path=None,
    dry_run=False,
    grpcport=None,
    disable_domain_listen=False,
    backend_ip=None,
    enable_http3=False,
):
    """Generates and deploys Nginx config files based on input parameters.

    All placeholder replacements are performed in-memory using Python string
    operations. No shell commands (sed) are used for text manipulation.

    Args:
        config_template: Template name for Nginx configuration.
        domain: Domain name for Nginx configuration.
        ip: IP address for Nginx configuration.
        cert_name: Certificate name for Nginx configuration.
        cert_key: Certificate key for Nginx configuration.
        port: Port number for Nginx configuration.
        pollport: Polling port number for Nginx configuration (optional).
        redirect_domain: Redirect domain for Nginx configuration (optional).
        auth_file: Authentication file for Nginx configuration (optional).
        allowed_ips: Comma-separated list of allowed IPs/CIDR blocks (optional).
        target_path: Custom target path for generated configs (optional).
        dry_run: If True, display commands without executing them.
        grpcport: gRPC port number for Nginx configuration (optional).
        disable_domain_listen: If True, remove domain prefix from listen directives.
        backend_ip: Backend IP for proxy_pass/grpc_pass (default: 127.0.0.1).
        enable_http3: If True, emit QUIC/HTTP/3 listen directives and Alt-Svc header.
    """
    # Validate all inputs
    try:
        validate_all_inputs(
            config_template=config_template,
            domain=domain,
            ip=ip,
            port=port or "",
            cert_name=cert_name or "",
            cert_key=cert_key or "",
            pollport=pollport or "",
            grpcport=grpcport or "",
            redirect_domain=redirect_domain or "",
            auth_file=auth_file or "",
            allowed_ips=allowed_ips or "",
            target_path=target_path or "",
            backend_ip=backend_ip or "",
            enable_http3=enable_http3,
        )
    except ValidationError as e:
        logger.error("Input validation failed: %s", e)
        print(f"ERROR: {e}")
        return

    # Mutual exclusion (CR-01): --disable_domain_listen rewrites
    # `listen <ip>:443` to the wildcard `listen 443`, which destroys the
    # `listen <ip>:443 ssl;` marker that _inject_http3_directives relies on.
    # Combining the two flags would silently emit a config with NO HTTP/3
    # directives (the injection no-ops and only logs a warning). Fail fast
    # instead so the operator cannot ship a silently-degraded config.
    if enable_http3 and disable_domain_listen:
        raise click.ClickException(
            "--enable_http3 cannot be combined with --disable_domain_listen: "
            "the wildcard listen rewrite removes the IP-bound marker required "
            "for QUIC injection, which would silently drop all HTTP/3 "
            "directives. Drop one of the two flags."
        )

    # nginx version gate — checked BEFORE any file write or content substitution.
    # Only evaluated when enable_http3=True to avoid subprocess overhead for
    # existing operators who don't use HTTP/3.
    if enable_http3:
        version = get_nginx_version()
        if version is None or version < (1, 25, 0):
            ver_str = ".".join(str(v) for v in version) if version else "unknown"
            raise click.ClickException(
                f"HTTP/3 requires nginx >= 1.25.0 (you have {ver_str}). "
                "Either upgrade nginx (Debian: bookworm-backports; Ubuntu: 24.04+; "
                "RHEL: 9.4+) or omit --enable_http3 to ship HTTP/2-only configs."
            )

    # Get default vars
    default_vars = get_default_vars()
    server_path = target_path if target_path else default_vars["server_path"]

    # Create target directory if it doesn't exist
    if not dry_run and target_path and not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)
        logger.info("Created directory: %s", target_path)

    # Service name is directly the template name
    service_name = config_template

    # Create unique cache directory based on domain
    if domain:
        domain_id = domain.replace(".", "_")
        unique_id = f"{service_name}_{domain_id}"
    else:
        unique_id = service_name

    cache_dir = f"/var/cache/nginx/{unique_id}"
    logger.info("Using domain-specific cache path: %s", cache_dir)

    if not dry_run and not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir, exist_ok=True)
            logger.info("Created cache directory: %s", cache_dir)
            _run_command(["chown", "-R", "nginx:nginx", cache_dir])
            _run_command(["chmod", "-R", "755", cache_dir])
        except Exception as e:
            logger.warning("Could not create cache directory: %s", e)
    elif dry_run:
        logger.info("[DRY RUN] Would create cache directory: %s", cache_dir)

    # Get template content with domain-specific cache paths
    logger.info("Generating domain-specific template for %s using %s", domain, config_template)
    content = get_config_template(config_template, domain)
    if not content:
        logger.error("No valid config template found for: %s", config_template)
        print("No valid config template")
        return

    # Apply cache path fix with regex (domain-specific unique IDs).
    # _SENTINEL_PATH: derive the path segment from the constant so the regex
    # stays in sync if CACHE_PATH_SENTINEL ever changes (sentinel-drift protection).
    _SENTINEL_PATH = re.escape(CACHE_PATH_SENTINEL.split()[1])

    # First re.sub: rewrite the cache path.  Pattern covers BOTH the raw /tmp
    # sentinel (COR-01: templates now store raw sentinel) AND any pre-existing
    # /var/cache/nginx/... path (handles prior-version configs on disk).
    content = re.sub(
        rf"proxy_cache_path\s+(?:{_SENTINEL_PATH}|/var/cache/nginx/[^\s]+)",
        f"proxy_cache_path /var/cache/nginx/{unique_id}",
        content,
    )
    # Second re.sub: rewrite the keys_zone name — lambda repl makes back-reference
    # semantics explicit and immune to digit-prefix / backslash in unique_id (COR-05).
    content = re.sub(
        r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
        lambda m: f"{m.group(1)}{unique_id}_cache:",
        content,
    )
    # Third re.sub: rewrite the limit_req_zone name (COR-05).
    content = re.sub(
        r"(limit_req_zone\s+[^\s]+\s+zone=)[^\s:]+:",
        lambda m: f"{m.group(1)}{unique_id}_ratelimit:",
        content,
    )
    # Fourth re.sub: rewrite limit_req zone references (COR-05).
    content = re.sub(
        r"(limit_req\s+zone=)[^\s;]+",
        lambda m: f"{m.group(1)}{unique_id}_ratelimit",
        content,
    )

    # Replace listen-IP placeholder FIRST (before domain replacement), so that
    # templates' `listen ip.ip.ip.ip:PORT;` becomes `listen <actual-ip>:PORT;`.
    # IPv6 addresses are wrapped in brackets (`listen [2001:db8::1]:443 ssl;`).
    # This binds the nginx listen socket to a specific interface and avoids both
    # (a) DNS-parse-time failures of hostname-bound listens and (b) SNI fallback
    # leakage of wildcard listens. See RELEASE_NOTES.md v1.11.0.
    formatted_listen_ip = _format_ip_for_nginx(ip)
    logger.info("Set listen IP in conf to %s", formatted_listen_ip)
    content = _replace_placeholder(content, default_vars["template_ip"], formatted_listen_ip)

    # Replace domain placeholder (server_name, cache paths, log file names)
    logger.info("Set domain name in conf to %s", domain)
    content = _replace_placeholder(content, default_vars["template_domain"], domain)

    # Handle disable_domain_listen (must be AFTER IP replacement): strip the
    # IP prefix so the listen socket becomes a wildcard (0.0.0.0:PORT). Flag
    # name is kept for backward compatibility; the effective behaviour is
    # "unbind listen from any interface". Only safe when default_ssl_reject
    # is deployed as 00-default.conf — otherwise SNI fallback applies.
    if disable_domain_listen:
        logger.warning(
            "--disable_domain_listen is active: listen socket will be wildcard. "
            "Make sure default_ssl_reject is deployed (--setup_default) to "
            "prevent SNI fallback to the wrong certificate."
        )
        content = content.replace(f"listen {formatted_listen_ip}:80", "listen 80")
        content = content.replace(f"listen {formatted_listen_ip}:443", "listen 443")

    # Inject HTTP/3 (QUIC) directives after the listen :443 ssl; line.
    # Placement invariant: AFTER IP-placeholder, domain-placeholder, and
    # disable_domain_listen passes so that formatted_listen_ip is already the
    # real IP value and the marker `listen <ip>:443 ssl;` is present in content.
    # BEFORE backend-IP substitution (backend IP is unrelated to the listen block).
    if enable_http3:
        effective_conf_dir = target_path if target_path else "/etc/nginx/conf.d"
        content = _inject_http3_directives(content, formatted_listen_ip, effective_conf_dir)

    # Backend IP handling (proxy_pass target)
    effective_backend_ip = backend_ip if backend_ip else "127.0.0.1"
    _warn_public_backend_ip(effective_backend_ip)
    formatted_backend_ip = _format_ip_for_nginx(effective_backend_ip)
    logger.info("Set backend IP in conf to %s (formatted: %s)", effective_backend_ip, formatted_backend_ip)
    content = _replace_placeholder(content, default_vars["template_backend_ip"], formatted_backend_ip)

    # Handle certificate placeholders
    if cert_key:
        # Self-signed or purchased certificate
        logger.info("Set cert name in conf to %s", cert_name)
        content = _replace_placeholder(content, default_vars["template_self_crt"], cert_name)
        content = _replace_placeholder(content, default_vars["template_self_key"], cert_key)
    else:
        # Let's Encrypt certificate
        cert_key = cert_name
        logger.info("Set cert name in conf to %s", cert_name)
        content = _replace_placeholder(content, default_vars["template_crt"], cert_name)
        content = _replace_placeholder(content, default_vars["template_key"], cert_key)

    # Replace port placeholder
    if port:
        logger.info("Set port in conf to %s", port)
        content = _replace_placeholder(content, default_vars["template_port"], port)

    # Replace poll port placeholder
    if pollport:
        logger.info("Set poll port in conf to %s", pollport)
        content = _replace_placeholder(content, default_vars["template_poll_port"], pollport)

    # Replace gRPC port placeholder
    if grpcport:
        logger.info("Set gRPC port in conf to %s", grpcport)
        content = _replace_placeholder(content, default_vars["template_grpc_port"], grpcport)

    # Handle authentication
    if auth_file:
        logger.info("Set auth file to %s", auth_file)
        auth_lines = [
            '        auth_basic       "Restricted Area";',
            f"        auth_basic_user_file  {auth_file};",
        ]
        content = _insert_after_marker(content, "#authentication", auth_lines)

    # Handle IP restrictions
    if allowed_ips:
        logger.info("Set IP restrictions to %s", allowed_ips)
        ip_lines = ["    # IP restrictions"]
        for ip_entry in allowed_ips.split(","):
            ip_entry = ip_entry.strip()
            if ip_entry:
                ip_lines.append(f"    allow {ip_entry};")
        ip_lines.append("    deny all;")
        content = _insert_after_marker(content, "#ip_restrictions", ip_lines)

    # Handle redirect domain
    if "redirect" in config_template and redirect_domain:
        logger.info("Set redirect domain in conf to %s", redirect_domain)
        content = _replace_placeholder(content, default_vars["template_redirect_domain"], redirect_domain)

    # Write final configuration to target. `_safe_conf_filename` strips any
    # wildcard glob (`*.foo` → `_wildcard.foo`) so the on-disk filename is
    # safe to enumerate with shell globs and `rm /etc/nginx/conf.d/*.conf`.
    target_file = os.path.join(server_path, f"{_safe_conf_filename(domain)}.conf")
    if not dry_run:
        logger.info("Writing configuration to %s", target_file)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        logger.info("[DRY RUN] Would write configuration to %s", target_file)

    # Handle Let's Encrypt certificate creation
    if cert_key == cert_name:
        _create_cert_if_needed(cert_name, dry_run)

    # Handle redirect SSL certificate
    if "redirect_ssl" in config_template and redirect_domain:
        _create_cert_if_needed(redirect_domain, dry_run)
