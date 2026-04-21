"""
Command-line interface for configuring Nginx servers with various templates.

This module provides a CLI tool for setting up Nginx configurations with support
for different use cases like code-server, FastReport, MailHog, NextCloud, Odoo,
pgAdmin4, Portainer, PWA, and domain redirects. It supports both HTTP and HTTPS
configurations.

Typical usage example:
    nginx_set_conf --config_template="odoo_ssl" --domain="example.com" --ip="10.0.0.1"
    nginx_set_conf --config_template="odoo_ssl" --domain="example.com" --target_path="/tmp/nginx/" --dry_run
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
from .config_templates import get_config_template
from .config_verification import ConfigVerification
from .utils import (
    execute_commands,
    migrate_configs_to_wildcard,
    parse_yaml_folder,
    retrieve_valid_input,
    setup_default_server,
)

# Setup logging
logger = logging.getLogger("nginx_set_conf")
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()

# Use /var/log path when running as root, otherwise current directory
_log_dir = "/var/log/nginx_set_conf"
if os.getuid() == 0:
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, "nginx_set_conf.log")
else:
    _log_path = "nginx_set_conf.log"

try:
    file_handler = RotatingFileHandler(
        _log_path,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=3,
    )
except (PermissionError, OSError):
    # Fallback to current directory if log dir is not writable
    file_handler = RotatingFileHandler(
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


def welcome():
    logger.info("Welcome to the nginx_set_conf!")
    logger.info("Version %s", __version__)
    logger.info("Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany")
    logger.info("License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).")
    logger.info('nginx_set_conf  --config_path="$HOME/docker-builds/ngx-conf/"')


def _run_service_command(args: list, dry_run: bool = False) -> None:
    """Run a system service command safely using subprocess.

    Args:
        args: Command and arguments as a list.
        dry_run: If True, only log what would be done.
    """
    cmd_str = " ".join(args)
    if dry_run:
        logger.info("[DRY RUN] Would execute: %s", cmd_str)
        return
    try:
        logger.info("Executing: %s", cmd_str)
        result = subprocess.run(args, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        logger.error("Command not found: %s", args[0])


# Help text conf
eq_config_support = """
Insert the conf-template.
\f
We support:\f
\b
- code_server (code-server with ssl)
- fast_report (FastReport with ssl)
- flowise (Flowise AI with ssl/http2)
- guacamole (Apache Guacamole with ssl/http2 and WebSocket)
- kasm (Kasm Workspaces with ssl/http2)
- mailpit (Mailpit with ssl/http2)
- n8n (n8n with ssl/http2)
- nextcloud (NextCloud with ssl)
- odoo_http (Odoo only http)
- odoo_ssl (Odoo with ssl)
- pgadmin (pgAdmin4 with ssl)
- portainer (Portainer with ssl)
- pwa (Progressive Web App with ssl)
- qdrant (Qdrant vector database with ssl/http2 and gRPC support)
- redirect (Redirect Domain without ssl)
- redirect_ssl (Redirect Domain with ssl)
- supabase (Supabase database server with ssl/http2)
\b

Example usage:
nginx-set-conf --config_path=/root/docker-builds/ngx-conf
\b

Configuration Management Options:
- --verify_config: Check consistency between local and server config files
- --sync_config: Interactive sync of configuration files
- --backup_config: Create backup of current server configuration
- --migrate_to_wildcard: Atomically rewrite hostname-bound listen directives
- --setup_default: Install default_server catch-all for unknown SNI
\b
"""


@click.command(help=f"nginx-set-conf {__version__} - Command-line interface for configuring Nginx servers")
@click.version_option(version=__version__)
@click.option("--config_template", help=eq_config_support)
@click.option(
    "--show_template",
    is_flag=True,
    help="Show the template configuration without applying it",
)
@click.option("--ip", help="IP address of the server")
@click.option("--domain", help="Name of the domain")
@click.option("--port", help="Primary port for the Docker container")
@click.option(
    "--cert_name",
    help="Name of certificate if you want to use letsencrypt - complete path for self signed or purchased certificates",
)
@click.option(
    "--cert_key",
    help="Name and path of certificate key - for self signed or purchased certificates - leave empty for letsencrypt",
)
@click.option(
    "--pollport",
    help="Secondary Docker container port for odoo pollings",
)
@click.option(
    "--grpcport",
    help="Secondary Docker container port for qdrant grpc",
)
@click.option("--redirect_domain", help="Redirect domain")
@click.option("--auth_file", help="Use authfile for htAccess")
@click.option(
    "--allowed_ips",
    help="Comma-separated list of allowed IPs/CIDR blocks (e.g., '192.168.1.0/24,10.0.0.50')",
)
@click.option(
    "--backend_ip",
    help="Backend IP for proxy_pass (default: 127.0.0.1)",
)
@click.option(
    "--disable_domain_listen",
    is_flag=True,
    help=(
        "Generate `listen 80;` / `listen 443 ssl;` instead of "
        "`listen <domain>:80;` / `listen <domain>:443 ssl;`. "
        "Avoids DNS resolution at nginx config-parse time (useful if "
        "upstream DNS is flaky) and intranet systems without public DNS. "
        "WARNING: mixing both styles on the same server causes SNI "
        "fallback to the first server block — migrate all configs in one "
        "go via `--migrate_to_wildcard`."
    ),
)
@click.option(
    "--config_path",
    help='Yaml configuration folder f.e.  --config_path="$HOME/docker-builds/ngx-conf/"',
)
@click.option(
    "--target_path",
    help="Target path where the configuration files will be saved (default: /etc/nginx/conf.d)",
)
@click.option(
    "--dry_run",
    is_flag=True,
    help="Run configuration generation without applying changes or creating certificates",
)
@click.option(
    "--verify_config",
    is_flag=True,
    help="Compare nginx configuration files between templates and server",
)
@click.option(
    "--sync_config",
    is_flag=True,
    help="Synchronize template files to server configuration",
)
@click.option(
    "--backup_config",
    is_flag=True,
    help="Create a backup of current server configuration",
)
@click.option(
    "--setup_default",
    is_flag=True,
    help=(
        "Install a default_server catch-all (00-default.conf) that closes "
        "connections for unknown SNI/Host with HTTP 444. Generates a "
        "self-signed sacrificial cert at /etc/nginx/ssl/default.{crt,key} "
        "if not present. Only effective on wildcard listen sockets — "
        "migrate first via --migrate_to_wildcard if still on hostname-bound "
        "listen directives."
    ),
)
@click.option(
    "--migrate_to_wildcard",
    is_flag=True,
    help=(
        "Atomically migrate all `listen <hostname>:<port>;` directives in "
        "/etc/nginx/conf.d/*.conf to `listen <port>;`. Creates a backup and "
        "rolls back on `nginx -t` failure. Use to unblock the DNS "
        "parse-time hardening path without risking partial-migration SNI "
        "fallback."
    ),
)
def start_nginx_set_conf(
    config_template,
    show_template,
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
    disable_domain_listen,
    config_path,
    target_path,
    dry_run,
    verify_config,
    sync_config,
    backup_config,
    setup_default,
    migrate_to_wildcard,
):
    # Handle atomic migration to wildcard listen directives
    if migrate_to_wildcard:
        welcome()
        target = target_path if target_path else "/etc/nginx/conf.d"
        if migrate_configs_to_wildcard(conf_dir=target, dry_run=dry_run):
            logger.info("Migration to wildcard listen directives succeeded")
            if not dry_run:
                _run_service_command(["systemctl", "reload", "nginx.service"])
        else:
            logger.error("Migration to wildcard listen directives failed")
        return

    # Handle default_server installation (SNI-mismatch hardening)
    if setup_default:
        welcome()
        target = target_path if target_path else "/etc/nginx/conf.d"
        if setup_default_server(target_path=target, dry_run=dry_run):
            logger.info("Default server block installed successfully")
            if not dry_run:
                _run_service_command(["nginx", "-t"])
                _run_service_command(["systemctl", "reload", "nginx.service"])
        else:
            logger.error("Failed to install default server block")
        return

    # Handle configuration verification and management
    if verify_config or sync_config or backup_config:
        welcome()
        verifier = ConfigVerification()

        if backup_config:
            logger.info("Creating backup of current server configuration...")
            if verifier.backup_configuration():
                logger.info("Backup completed successfully")
            else:
                logger.error("Backup failed")
            return

        if verify_config or sync_config:
            logger.info("Verifying nginx configuration files...")
            results = verifier.verify_configuration_consistency()
            verifier.show_verification_results(results)

            if sync_config:
                logger.info("Starting configuration synchronization...")
                if verifier.sync_configurations(results):
                    logger.info("Configuration sync completed successfully")
                    # Re-verify after sync
                    logger.info("Re-verifying configuration after sync...")
                    new_results = verifier.verify_configuration_consistency()
                    verifier.show_verification_results(new_results)
                else:
                    logger.info("Configuration sync cancelled or failed")
            return

    # Add new template display logic
    if show_template and config_template:
        # For display purposes, we don't need domain-specific paths
        template_content = get_config_template(config_template)
        if template_content:
            logger.info("Template for %s:", config_template)
            print(template_content)
            return
        else:
            logger.error("Template %s not found!", config_template)
            return

    if dry_run:
        logger.info("DRY RUN MODE: No actual changes will be made to your system")
        logger.info("No certificates will be created, and no configurations will be applied")

    if not dry_run:
        logger.info("Starting nginx service")
        _run_service_command(["systemctl", "start", "nginx.service"])

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
                yaml_disable_domain_listen = yaml_config.get("disable_domain_listen", False)
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
                )
    elif config_template and ip and domain and port and cert_name:
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
        )
    else:
        config_template = retrieve_valid_input(eq_config_support + "\n")
        ip = retrieve_valid_input("IP address of the server\n")
        domain = retrieve_valid_input("Name of the domain\n")
        port = retrieve_valid_input("Primary port for the Docker container\n")
        cert_name = retrieve_valid_input("Name of certificate\n")
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
        )

    if not dry_run:
        logger.info("Restarting nginx service")
        _run_service_command(["systemctl", "restart", "nginx.service"])
        logger.info("Checking nginx service status")
        _run_service_command(["systemctl", "status", "nginx.service"])
        logger.info("Testing nginx configuration")
        _run_service_command(["nginx", "-t"])
        logger.info("Checking nginx version")
        _run_service_command(["nginx", "-V"])
    else:
        logger.info("DRY RUN COMPLETED: Configuration would have been generated but not applied")
        logger.info("To apply the configuration, run again without the --dry_run flag")


if __name__ == "__main__":
    welcome()
    start_nginx_set_conf()
