"""
Command-line interface for configuring Nginx servers with various templates.

This module provides a CLI tool for setting up Nginx configurations with support
for different use cases like code-server, FastReport, MailHog, NextCloud, Odoo,
pgAdmin4, Portainer, PWA, and domain redirects. It supports both HTTP and HTTPS
configurations.

The CLI is organised in subcommands (deploy, show, templates, verify, sync,
backup, setup-default, migrate). The flag-only form of earlier versions keeps
working: a call whose first argument is an option (e.g. ``--config_path=...``)
is routed to a hidden ``legacy`` command with the original option set.

Typical usage example:
    nginx-set-conf --config_path=/root/docker-builds/ngx-conf
    nginx-set-conf deploy --config_template=odoo_ssl --domain=example.com --ip=10.0.0.1 ...
    nginx-set-conf show odoo_ssl
"""

# -*- coding: utf-8 -*-
# Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import os
import subprocess
from logging.handlers import RotatingFileHandler

import click

from . import __version__
from .config_verification import ConfigVerification
from .templates.all_templates import TEMPLATE_DESCRIPTIONS, get_config_template
from .utils import (
    execute_commands,
    migrate_configs_to_wildcard,
    parse_yaml_folder,
    retrieve_optional_input,
    retrieve_valid_input,
    setup_default_server,
)

# Setup logging
logger = logging.getLogger("nginx_set_conf")
logger.setLevel(logging.INFO)

LOG_FILE_MODE = 0o600


class PrivateRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler whose log files are readable by the owner only.

    The log records every domain, IP, certificate path and executed command.
    The file is created with 0600 regardless of the umask — also after each
    rollover, which opens a fresh file — and a file left behind by an older
    version with wider permissions is tightened when it is opened.
    """

    def _open(self):
        fd = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, LOG_FILE_MODE)
        try:
            os.fchmod(fd, LOG_FILE_MODE)
        except OSError:
            # Not the owner: the file stays as it is; writing still works.
            pass
        return open(fd, self.mode, encoding=self.encoding, errors=self.errors)


# Create handlers
console_handler = logging.StreamHandler()

# Use /var/log path when running as root, otherwise current directory
_log_dir = "/var/log/nginx_set_conf"
if os.getuid() == 0:
    os.makedirs(_log_dir, mode=0o700, exist_ok=True)
    _log_path = os.path.join(_log_dir, "nginx_set_conf.log")
else:
    _log_path = "nginx_set_conf.log"

try:
    file_handler = PrivateRotatingFileHandler(
        _log_path,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=3,
    )
except (PermissionError, OSError):
    # Fallback to current directory if log dir is not writable
    file_handler = PrivateRotatingFileHandler(
        "nginx_set_conf.log",
        maxBytes=1024 * 1024,
        backupCount=3,
    )

# Create formatters and add it to handlers
log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

__version__ = __version__

DEFAULT_TARGET_PATH = "/etc/nginx/conf.d"

# The call operators copy from one server to the next — kept on ONE line in
# the help so it can be copied without re-joining a wrapped line.
STANDARD_CALL = "nginx-set-conf --config_path=/root/docker-builds/ngx-conf"


def welcome():
    logger.info("Welcome to the nginx_set_conf!")
    logger.info("Version %s", __version__)
    logger.info("Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany")
    logger.info("License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).")
    logger.info("%s", STANDARD_CALL)


def _run_service_command(args: list, dry_run: bool = False):
    """Run a system service command safely using subprocess.

    Args:
        args: Command and arguments as a list.
        dry_run: If True, only log what would be done.

    Returns:
        subprocess.CompletedProcess on success, None on dry_run or
        when the binary is not found. Callers MUST check the result's
        returncode before assuming success when correctness depends on it
        (e.g., ``nginx -t`` before a reload).
    """
    cmd_str = " ".join(args)
    if dry_run:
        logger.info("[DRY RUN] Would execute: %s", cmd_str)
        return None
    try:
        logger.info("Executing: %s", cmd_str)
        result = subprocess.run(args, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result
    except FileNotFoundError:
        logger.error("Command not found: %s", args[0])
        return None


def template_list_text() -> str:
    """Return the registered templates as aligned ``name  description`` lines."""
    width = max(len(name) for name in TEMPLATE_DESCRIPTIONS)
    return "\n".join(f"  {name.ljust(width)}  {desc}" for name, desc in sorted(TEMPLATE_DESCRIPTIONS.items()))


# ---------------------------------------------------------------------------
# Actions — shared by the subcommands and the legacy flag-only command.
# Each returns True on success so subcommands can set the exit code.
# ---------------------------------------------------------------------------


def _run_migrate(target_path: str | None, dry_run: bool) -> bool:
    welcome()
    target = target_path if target_path else DEFAULT_TARGET_PATH
    if migrate_configs_to_wildcard(conf_dir=target, dry_run=dry_run):
        logger.info("Migration to wildcard listen directives succeeded")
        if not dry_run:
            _run_service_command(["systemctl", "reload", "nginx.service"])
        return True
    logger.error("Migration to wildcard listen directives failed")
    return False


def _run_setup_default(target_path: str | None, dry_run: bool) -> bool:
    welcome()
    target = target_path if target_path else DEFAULT_TARGET_PATH
    if setup_default_server(target_path=target, dry_run=dry_run):
        logger.info("Default server block installed successfully")
        if not dry_run:
            _run_service_command(["nginx", "-t"])
            _run_service_command(["systemctl", "reload", "nginx.service"])
        return True
    logger.error("Failed to install default server block")
    return False


def _run_backup() -> bool:
    welcome()
    logger.info("Creating backup of current server configuration...")
    if ConfigVerification().backup_configuration():
        logger.info("Backup completed successfully")
        return True
    logger.error("Backup failed")
    return False


def _run_verify(sync: bool, force: bool) -> bool:
    welcome()
    verifier = ConfigVerification()
    logger.info("Verifying nginx configuration files...")
    results = verifier.verify_configuration_consistency()
    verifier.show_verification_results(results)
    if not sync:
        return True

    logger.info("Starting configuration synchronization...")
    if verifier.sync_configurations(results, force=force):
        logger.info("Configuration sync completed successfully")
        # Re-verify after sync
        logger.info("Re-verifying configuration after sync...")
        new_results = verifier.verify_configuration_consistency()
        verifier.show_verification_results(new_results)
        return True
    logger.info("Configuration sync cancelled or failed")
    return False


def _run_show(config_template: str) -> bool:
    # For display purposes, we don't need domain-specific paths
    template_content = get_config_template(config_template)
    if template_content:
        logger.info("Template for %s:", config_template)
        print(template_content)
        return True
    logger.error("Template %s not found!", config_template)
    return False


def _run_deploy(
    config_template,
    ip,
    domain,
    port,
    cert_name,
    cert_key,
    pollport,
    grpcport,
    redirect_domain,
    auth_file,
    allowed_ips,
    backend_ip,
    root_path,
    disable_domain_listen,
    enable_http3,
    config_path,
    target_path,
    dry_run,
):
    if dry_run:
        logger.info("DRY RUN MODE: No actual changes will be made to your system")
        logger.info("No certificates will be created, and no configurations will be applied")

    if not dry_run:
        logger.info("Starting nginx service")
        _run_service_command(["systemctl", "start", "nginx.service"])

    # Pre-flight: ensure the three managed base configs (nginx.conf,
    # general.conf, security.conf) match the embedded templates before
    # deploying any vhost. Auto-repairs drift (e.g. an Odoo-breaking CSP in
    # security.conf that lacks 'unsafe-eval') so new domains never deploy on a
    # broken base. Runs exactly once per invocation and is idempotent.
    # Skipped for --dry_run (no server writes).
    if not dry_run:
        if not ConfigVerification().preflight_check_and_repair():
            logger.error("Pre-flight base-config check failed — aborting deploy.")
            return

    if config_path:
        yaml_config_files = parse_yaml_folder(config_path)
        for yaml_config_file in yaml_config_files:
            for _, yaml_config in yaml_config_file.items():
                config_template = yaml_config["config_template"]
                ip = yaml_config["ip"]
                domain = yaml_config["domain"]
                port = str(yaml_config.get("port", ""))
                cert_name = yaml_config.get("cert_name", "")
                cert_key = yaml_config.get("cert_key", "")
                pollport = str(yaml_config.get("pollport", ""))
                grpcport = str(yaml_config.get("grpcport", ""))
                redirect_domain = str(yaml_config.get("redirect_domain", ""))
                auth_file = str(yaml_config.get("auth_file", ""))
                allowed_ips = str(yaml_config.get("allowed_ips", ""))
                yaml_backend_ip = str(yaml_config.get("backend_ip", ""))
                yaml_root_path = str(yaml_config.get("root_path", ""))
                yaml_disable_domain_listen = yaml_config.get("disable_domain_listen", False)
                yaml_enable_http3 = yaml_config.get("enable_http3", False)
                yaml_target_path = str(yaml_config.get("target_path", ""))
                if not yaml_target_path:
                    yaml_target_path = target_path

                logger.info(
                    "Generating configuration for %s using template %s",
                    domain,
                    config_template,
                )

                execute_commands(
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
                    yaml_target_path,
                    dry_run,
                    grpcport,
                    yaml_disable_domain_listen,
                    backend_ip=yaml_backend_ip or None,
                    enable_http3=yaml_enable_http3,
                    root_path=yaml_root_path or None,
                )
    elif config_template and ip and domain and cert_name and (port or root_path):
        logger.info(
            "Generating configuration for %s using template %s",
            domain,
            config_template,
        )

        execute_commands(
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
            target_path,
            dry_run,
            grpcport,
            disable_domain_listen,
            backend_ip=backend_ip,
            enable_http3=enable_http3,
            root_path=root_path,
        )
    else:
        config_template = retrieve_valid_input(f"Template name:\n{template_list_text()}\n")
        ip = retrieve_valid_input("IP address of the server\n")
        domain = retrieve_valid_input("Name of the domain\n")
        port = retrieve_valid_input("Primary port for the Docker container\n")
        cert_name = retrieve_valid_input("Name of certificate\n")
        cert_key = retrieve_optional_input(
            "Path to certificate key file (leave empty for Let's Encrypt auto-generate)\n"
        )
        pollport = retrieve_valid_input("Secondary Docker container port for odoo pollings\n")
        grpcport = retrieve_valid_input("Secondary Docker container port for qdrant gRPC\n")
        redirect_domain = retrieve_valid_input("Redirect domain\n")
        auth_file = retrieve_valid_input("authfile\n")
        allowed_ips = retrieve_valid_input("Allowed IPs (comma-separated, optional)\n")
        disable_domain_listen_input = retrieve_valid_input(
            "Disable domain prefix in listen directives? (yes/no, optional)\n"
        )
        disable_domain_listen = (
            disable_domain_listen_input.lower() in ["yes", "y", "true", "1"] if disable_domain_listen_input else False
        )
        enable_http3_input = retrieve_valid_input("Enable HTTP/3 QUIC directives? (yes/no, optional)\n")
        enable_http3 = enable_http3_input.lower() in ["yes", "y", "true", "1"] if enable_http3_input else False
        root_path = retrieve_optional_input("Document root for static templates (leave empty for default /opt/www)\n")
        custom_target_path = retrieve_valid_input("Target path (leave empty for default /etc/nginx/conf.d)\n")
        target_path = custom_target_path if custom_target_path else target_path

        execute_commands(
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
            target_path,
            dry_run,
            grpcport,
            disable_domain_listen,
            enable_http3=enable_http3,
            root_path=root_path or None,
        )

    if not dry_run:
        # Validate the new configuration BEFORE touching the live nginx process.
        # A failing `nginx -t` after `systemctl restart` would have already crashed
        # the running nginx with a malformed config and dropped traffic.
        logger.info("Testing nginx configuration")
        test_result = _run_service_command(["nginx", "-t"])
        if test_result is not None and test_result.returncode != 0:
            raise click.ClickException(
                "nginx -t failed — refusing to reload. The running nginx process "
                "keeps the previous configuration. Fix the generated config and re-run."
            )
        # Graceful reload (no traffic drop) instead of disruptive restart.
        logger.info("Reloading nginx service")
        _run_service_command(["systemctl", "reload", "nginx.service"])
        logger.info("Checking nginx service status")
        _run_service_command(["systemctl", "status", "nginx.service"])
        logger.info("Checking nginx version")
        _run_service_command(["nginx", "-V"])
    else:
        logger.info("DRY RUN COMPLETED: Configuration would have been generated but not applied")
        logger.info("To apply the configuration, run again without the --dry_run flag")


# ---------------------------------------------------------------------------
# Click plumbing
# ---------------------------------------------------------------------------

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 110}


class NginxSetConfGroup(click.Group):
    """Top-level group that keeps the flag-only call form of earlier versions.

    ``nginx-set-conf --config_path=...`` (first argument is an option, not
    ``--help``/``--version``) is routed to the hidden ``legacy`` command, so
    scripts and copied one-liners keep working unchanged.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and args[0].startswith("-") and args[0] not in (*ctx.help_option_names, "--version"):
            args = ["legacy", *args]
        return super().parse_args(ctx, args)

    def list_commands(self, ctx: click.Context) -> list[str]:
        # Registration order (deploy first), not alphabetical.
        return list(self.commands)


class SectionedCommand(click.Command):
    """Command whose --help lists the options under titled sections."""

    def __init__(self, *args, sections: dict[str, list[str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sections = sections or {}

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        records = {}
        for param in self.get_params(ctx):
            record = param.get_help_record(ctx)
            if record and param.name:
                records[param.name] = record
        placed: set[str] = set()
        for title, names in self.sections.items():
            rows = [records[name] for name in names if name in records]
            placed.update(names)
            if rows:
                with formatter.section(title):
                    formatter.write_dl(rows)
        rest = [record for name, record in records.items() if name not in placed]
        if rest:
            with formatter.section("Other"):
                formatter.write_dl(rest)


def _options(decorators):
    """Apply a list of click.option decorators in listed order."""

    def apply(func):
        for decorator in reversed(decorators):
            func = decorator(func)
        return func

    return apply


_TARGET_PATH_OPTION = click.option(
    "--target_path",
    metavar="DIR",
    help=f"Directory for the generated config files (default: {DEFAULT_TARGET_PATH})",
)
_DRY_RUN_OPTION = click.option(
    "--dry_run",
    is_flag=True,
    help="Show what would happen; write nothing, create no certificates, reload nothing",
)

DEPLOY_OPTIONS = [
    click.option(
        "--config_path",
        metavar="DIR",
        help="Folder with YAML files; deploys every vhost defined there",
    ),
    click.option("--config_template", metavar="NAME", help="Template name — list them with 'nginx-set-conf templates'"),
    click.option("--domain", help="Domain name (server_name)"),
    click.option("--ip", help="Server IP the vhost listens on (IPv4 or IPv6)"),
    click.option("--port", help="Primary port of the Docker container"),
    click.option("--pollport", help="Secondary port: Odoo longpolling"),
    click.option("--grpcport", help="Secondary port: Qdrant gRPC"),
    click.option("--backend_ip", help="Backend IP for proxy_pass (default: 127.0.0.1)"),
    click.option(
        "--root_path", metavar="DIR", help="Document root for static_ssl / static_public_ssl (default: /opt/www)"
    ),
    click.option("--redirect_domain", help="Target domain for redirect / redirect_ssl"),
    click.option(
        "--cert_name",
        help="Let's Encrypt: certificate name. Own certificate: full path to the .crt file",
    ),
    click.option(
        "--cert_key",
        help="Own certificate: full path to the key file. Omit for Let's Encrypt (key is generated)",
    ),
    click.option("--auth_file", metavar="FILE", help="htpasswd file for HTTP basic auth"),
    click.option(
        "--allowed_ips",
        metavar="LIST",
        help="Comma-separated IPs/CIDR blocks allowed to connect (e.g. '192.168.1.0/24,10.0.0.50')",
    ),
    click.option(
        "--enable_http3",
        is_flag=True,
        help=(
            "Add QUIC/HTTP/3 listeners and Alt-Svc header. Needs nginx >= 1.25.0 and UDP/443 open "
            "in the firewall. Not for: fast_report, mailpit, redirect, redirect_ssl, "
            "default_ssl_reject, odoo_http"
        ),
    ),
    click.option(
        "--disable_domain_listen",
        is_flag=True,
        help=(
            "Emit wildcard `listen 443 ssl;` instead of IP-bound `listen <ip>:443 ssl;`. "
            "Unknown SNI then falls back to the first vhost — only safe after 'setup-default'"
        ),
    ),
    _TARGET_PATH_OPTION,
    _DRY_RUN_OPTION,
]

DEPLOY_SECTIONS = {
    "Batch deploy (YAML)": ["config_path"],
    "Single vhost": [
        "config_template",
        "domain",
        "ip",
        "port",
        "pollport",
        "grpcport",
        "backend_ip",
        "root_path",
        "redirect_domain",
    ],
    "Certificate": ["cert_name", "cert_key"],
    "Access": ["auth_file", "allowed_ips"],
    "Listen": ["enable_http3", "disable_domain_listen"],
    "Run": ["target_path", "dry_run"],
}


@click.group(
    cls=NginxSetConfGroup,
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    help=f"""nginx-set-conf {__version__} – nginx reverse-proxy configs for Docker services.

\b
Standard server run:
  {STANDARD_CALL}
""",
    epilog="Run 'nginx-set-conf COMMAND --help' for the options of a command.",
)
@click.version_option(version=__version__)
@click.pass_context
def start_nginx_set_conf(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@start_nginx_set_conf.command(
    "deploy",
    cls=SectionedCommand,
    sections=DEPLOY_SECTIONS,
    short_help="Generate vhost configs and reload nginx",
    help="""Generate vhost configs, test them with `nginx -t` and reload nginx.

\b
From a YAML folder:
  nginx-set-conf deploy --config_path=/root/docker-builds/ngx-conf
Single vhost:
  nginx-set-conf deploy --config_template=odoo_ssl --domain=erp.example.com --ip=203.0.113.10 --port=8069 --pollport=8072 --cert_name=erp.example.com

Before the first vhost is written, the base configs (nginx.conf, general.conf,
security.conf) are checked and repaired if they drifted. Without --config_path
and without the required single-vhost options, the values are asked
interactively. Calling the options without 'deploy' (as in older versions)
does the same.
""",
)
@_options(DEPLOY_OPTIONS)
def deploy_command(**params):
    _run_deploy(**params)


@start_nginx_set_conf.command(
    "show", context_settings=CONTEXT_SETTINGS, short_help="Print a template without applying it"
)
@click.argument("template")
def show_command(template: str) -> None:
    """Print the raw TEMPLATE with its placeholders, without applying it."""
    if not get_config_template(template):
        raise click.ClickException(f"Unknown template '{template}'. List them with 'nginx-set-conf templates'.")
    _run_show(template)


@start_nginx_set_conf.command("templates", context_settings=CONTEXT_SETTINGS, short_help="List available templates")
def templates_command() -> None:
    """List every template usable with --config_template."""
    click.echo(template_list_text())


@start_nginx_set_conf.command(
    "verify",
    context_settings=CONTEXT_SETTINGS,
    short_help="Compare the base configs on the server with the embedded ones",
)
def verify_command() -> None:
    """Compare nginx.conf, general.conf and security.conf on the server with the
    versions embedded in this tool. Changes nothing."""
    _run_verify(sync=False, force=False)


@start_nginx_set_conf.command(
    "sync", context_settings=CONTEXT_SETTINGS, short_help="Write the embedded base configs to the server"
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite server files that differ from the embedded ones (local customisations are lost; a backup is made)",
)
def sync_command(force: bool) -> None:
    """Verify, then write the embedded nginx.conf, general.conf and security.conf
    to the server. A backup is made first. Aborts on differences unless --force."""
    if not _run_verify(sync=True, force=force):
        raise SystemExit(1)


@start_nginx_set_conf.command(
    "backup", context_settings=CONTEXT_SETTINGS, short_help="Back up the current nginx configuration"
)
def backup_command() -> None:
    """Back up nginx.conf and the nginxconfig.io/ directory to /var/backups/nginx_set_conf/."""
    if not _run_backup():
        raise SystemExit(1)


@start_nginx_set_conf.command(
    "setup-default",
    context_settings=CONTEXT_SETTINGS,
    short_help="Install the catch-all for unknown SNI (00-default.conf)",
)
@_options([_TARGET_PATH_OPTION, _DRY_RUN_OPTION])
def setup_default_command(target_path: str | None, dry_run: bool) -> None:
    """Install 00-default.conf, a default_server that closes connections for
    unknown SNI/Host with HTTP 444. Creates a self-signed throwaway certificate at
    /etc/nginx/ssl/default.{crt,key} if none exists."""
    if not _run_setup_default(target_path, dry_run):
        raise SystemExit(1)


@start_nginx_set_conf.command(
    "migrate", context_settings=CONTEXT_SETTINGS, short_help="Rewrite hostname-bound listen directives to wildcard"
)
@_options([_TARGET_PATH_OPTION, _DRY_RUN_OPTION])
def migrate_command(target_path: str | None, dry_run: bool) -> None:
    """Rewrite every `listen <hostname>:<port>;` in the conf.d files to
    `listen <port>;` in one go. Makes a backup and rolls back if `nginx -t`
    fails. Run 'setup-default' as well, otherwise unknown SNI falls back to the
    first vhost."""
    if not _run_migrate(target_path, dry_run):
        raise SystemExit(1)


@start_nginx_set_conf.command("legacy", hidden=True, context_settings=CONTEXT_SETTINGS)
@_options(DEPLOY_OPTIONS)
@click.option("--show_template", is_flag=True, help="Show the template without applying it")
@click.option("--verify_config", is_flag=True, help="Same as 'verify'")
@click.option("--sync_config", is_flag=True, help="Same as 'sync'")
@click.option("--force", is_flag=True, help="With --sync_config: overwrite differing server files")
@click.option("--backup_config", is_flag=True, help="Same as 'backup'")
@click.option("--setup_default", is_flag=True, help="Same as 'setup-default'")
@click.option("--migrate_to_wildcard", is_flag=True, help="Same as 'migrate'")
def legacy_command(
    show_template,
    verify_config,
    sync_config,
    force,
    backup_config,
    setup_default,
    migrate_to_wildcard,
    **deploy_params,
):
    """Flag-only call form of versions before 1.19 — same precedence as before."""
    target_path = deploy_params["target_path"]
    dry_run = deploy_params["dry_run"]
    if migrate_to_wildcard:
        _run_migrate(target_path, dry_run)
        return
    if setup_default:
        _run_setup_default(target_path, dry_run)
        return
    if backup_config:
        _run_backup()
        return
    if verify_config or sync_config:
        _run_verify(sync=sync_config, force=force)
        return
    if show_template and deploy_params["config_template"]:
        _run_show(deploy_params["config_template"])
        return
    _run_deploy(**deploy_params)


if __name__ == "__main__":
    welcome()
    start_nginx_set_conf()
