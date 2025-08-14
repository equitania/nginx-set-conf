"""
Command-line interface for configuring Nginx servers with various templates.

This module provides a CLI tool for setting up Nginx configurations with support
for different use cases like code-server, FastReport, MailHog, NextCloud, Odoo,
pgAdmin4, Portainer, PWA, and domain redirects. It supports both HTTP and HTTPS
configurations.

Typical usage example:
    nginx_set_conf --config_template="ngx_odoo_ssl" --domain="example.com" --ip="10.0.0.1"
    nginx_set_conf --config_template="ngx_odoo_ssl" --domain="example.com" --target_path="/tmp/nginx/" --dry_run
"""

# -*- coding: utf-8 -*-
# Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os
import click
import logging
from logging.handlers import RotatingFileHandler
from .utils import execute_commands, parse_yaml_folder, retrieve_valid_input
from . import __version__
from .config_templates import get_config_template
from .config_verification import ConfigVerification

# Setup logging
logger = logging.getLogger('nginx_set_conf')
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()
file_handler = RotatingFileHandler(
    'nginx_set_conf.log',
    maxBytes=1024*1024,  # 1MB
    backupCount=3
)

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

__version__ = __version__

def welcome():
    logger.info("Welcome to the nginx_set_conf!")
    logger.info(f"Version {__version__}")
    logger.info("Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany")
    logger.info("License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).")
    logger.info('nginx_set_conf  --config_path="$HOME/docker-builds/ngx-conf/"')
    
# Help text conf
eq_config_support = """
Insert the conf-template.
\f
We support:\f
\b
- ngx_code_server (code-server with ssl)
- ngx_fast_report (FastReport with ssl)
- ngx_kasm (Kasm Workspaces with ssl/http2)
- ngx_mailpit (Mailpit with ssl/http2)
- ngx_n8n (n8n with ssl/http2)
- ngx_nextcloud (NextCloud with ssl)
- ngx_odoo_http (Odoo only http)
- ngx_odoo_ssl (Odoo with ssl)
- ngx_pgadmin (pgAdmin4 with ssl)
- ngx_portainer (Portainer with ssl)
- ngx_pwa (Progressive Web App with ssl)
- ngx_qdrant (Qdrant vector database with ssl/http2 and gRPC support)
- ngx_redirect (Redirect Domain without ssl)
- ngx_redirect_ssl (Redirect Domain with ssl)
- ngx_supabase (Supabase database server with ssl/http2)
\b

Configuration Management Options:
- --verify_config: Check consistency between local and server config files
- --sync_config: Interactive sync of configuration files 
- --backup_config: Create backup of current server configuration
\b
"""


@click.command(help=f"nginx-set-conf {__version__} - Command-line interface for configuring Nginx servers")
@click.version_option(version=__version__)
@click.option("--config_template", help=eq_config_support)
@click.option("--show_template", is_flag=True, help="Show the template configuration without applying it")
@click.option("--ip", help="IP address of the server")
@click.option("--domain", help="Name of the domain")
@click.option("--port", help="Primary port for the Docker container")
@click.option("--cert_name", help="Name of certificate if you want to use letsencrypt - complete path for self signed or purchased certificates")
@click.option("--cert_key", help="Name and path of certificate key - for self signed or purchased certificates - leave empty for letsencrypt")
@click.option("--pollport", help="Secondary Docker container port for odoo pollings")
@click.option("--grpcport", help="Secondary Docker container port for qdrant grpc")
@click.option("--redirect_domain", help="Redirect domain")
@click.option("--auth_file", help="Use authfile for htAccess")
@click.option("--allowed_ips", help="Comma-separated list of allowed IPs/CIDR blocks (e.g., '192.168.1.0/24,10.0.0.50')")
@click.option("--disable_domain_listen", is_flag=True, help="Disable domain prefix in listen directives (for intranet systems)")
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
    disable_domain_listen,
    config_path,
    target_path,
    dry_run,
    verify_config,
    sync_config,
    backup_config,
):
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
            logger.info(f"\nTemplate for {config_template}:\n")
            print(template_content)
            return
        else:
            logger.error(f"Template {config_template} not found!")
            return

    if dry_run:
        logger.info("DRY RUN MODE: No actual changes will be made to your system")
        logger.info("No certificates will be created, and no configurations will be applied")

    if not dry_run:
        logger.info("Starting nginx service")
        os.system("systemctl start nginx.service")
        
    if config_path:
        yaml_config_files = parse_yaml_folder(config_path)
        for yaml_config_file in yaml_config_files:
            for _, yaml_config in yaml_config_file.items():
                config_template = yaml_config["config_template"]
                ip = yaml_config["ip"]
                domain = yaml_config["domain"]
                try:
                    port = str(yaml_config["port"])
                except:
                    port = ""
                try:
                    cert_name = yaml_config["cert_name"]
                except:
                    cert_name = ""
                try:
                    cert_key = yaml_config["cert_key"]
                except:
                    cert_key = ""
                try:
                    pollport = str(yaml_config["pollport"])
                except:
                    pollport = ""
                try:
                    grpcport = str(yaml_config["grpcport"])
                except:
                    grpcport = ""
                try:
                    redirect_domain = str(yaml_config["redirect_domain"])
                except:
                    redirect_domain = ""
                try:
                    auth_file = str(yaml_config["auth_file"])
                except:
                    auth_file = ""
                try:
                    allowed_ips = str(yaml_config["allowed_ips"])
                except:
                    allowed_ips = ""
                try:
                    yaml_disable_domain_listen = yaml_config.get("disable_domain_listen", False)
                except:
                    yaml_disable_domain_listen = False
                try:
                    yaml_target_path = str(yaml_config["target_path"])
                except:
                    yaml_target_path = target_path
                
                # Debug log for domain-specific cache paths
                logger.info(f"Generating configuration for {domain} using template {config_template}")
                logger.info(f"This will use domain-specific cache paths to avoid conflicts")
                    
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
                )
    elif config_template and ip and domain and port and cert_name:
        # Debug log for domain-specific cache paths
        logger.info(f"Generating configuration for {domain} using template {config_template}")
        logger.info(f"This will use domain-specific cache paths to avoid conflicts")
        
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
    else:
        config_template = retrieve_valid_input(eq_config_support + "\n")
        ip = retrieve_valid_input("IP address of the server" + "\n")
        domain = retrieve_valid_input("Name of the domain" + "\n")
        port = retrieve_valid_input("Primary port for the Docker container" + "\n")
        cert_name = retrieve_valid_input("Name of certificate" + "\n")
        pollport = retrieve_valid_input(
            "Secondary Docker container port for odoo pollings" + "\n"
        )
        grpcport = retrieve_valid_input(
            "Secondary Docker container port for qdrant gRPC" + "\n"
        )
        redirect_domain = retrieve_valid_input("Redirect domain" + "\n")
        auth_file = retrieve_valid_input("authfile" + "\n")
        allowed_ips = retrieve_valid_input("Allowed IPs (comma-separated, optional)" + "\n")
        disable_domain_listen_input = retrieve_valid_input("Disable domain prefix in listen directives? (yes/no, optional)" + "\n")
        disable_domain_listen = disable_domain_listen_input.lower() in ['yes', 'y', 'true', '1'] if disable_domain_listen_input else False
        custom_target_path = retrieve_valid_input("Target path (leave empty for default /etc/nginx/conf.d)" + "\n")
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
        # Restart and check the nginx service
        logger.info("Restarting nginx service")
        os.system("systemctl restart nginx.service")
        logger.info("Checking nginx service status")
        os.system("systemctl status nginx.service")
        logger.info("Testing nginx configuration")
        os.system("nginx -t")
        logger.info("Checking nginx version")
        os.system("nginx -V")
    else:
        logger.info("DRY RUN COMPLETED: Configuration would have been generated but not applied")
        logger.info("To apply the configuration, run again without the --dry_run flag")


if __name__ == "__main__":
    welcome()
    start_nginx_set_conf()
