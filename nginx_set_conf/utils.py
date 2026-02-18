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

import ipaddress
import logging
import os
import re
import subprocess

import yaml

from .config_templates import get_config_template
from .validators import ValidationError, validate_all_inputs

logger = logging.getLogger("nginx_set_conf")


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
    }


def retrieve_valid_input(message: str) -> str:
    """Prompts user for input until non-empty input is provided.

    Args:
        message: Prompt message to display to user.

    Returns:
        User's non-empty input string.
    """
    user_input = input(message)
    if user_input:
        return user_input
    else:
        return retrieve_valid_input(message)


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
        )
    except ValidationError as e:
        logger.error("Input validation failed: %s", e)
        print(f"ERROR: {e}")
        return

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

    # Apply cache path fix with regex (domain-specific unique IDs)
    content = re.sub(
        r"proxy_cache_path\s+/var/cache/nginx/[^\s]+",
        f"proxy_cache_path /var/cache/nginx/{unique_id}",
        content,
    )
    content = re.sub(
        r"(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:",
        f"\\1{unique_id}_cache:",
        content,
    )
    content = re.sub(
        r"(limit_req_zone\s+[^\s]+\s+zone=)[^\s:]+:",
        f"\\1{unique_id}_ratelimit:",
        content,
    )
    content = re.sub(
        r"(limit_req\s+zone=)[^\s;]+",
        f"\\1{unique_id}_ratelimit",
        content,
    )

    # Replace domain placeholder
    logger.info("Set domain name in conf to %s", domain)
    content = _replace_placeholder(content, default_vars["template_domain"], domain)

    # Handle disable_domain_listen (must be AFTER domain replacement)
    if disable_domain_listen:
        logger.info("Removing domain prefix from listen directives (for intranet systems)")
        content = content.replace(f"listen {domain}:80", "listen 80")
        content = content.replace(f"listen {domain}:443", "listen 443")

    # Replace IP placeholder - with IPv6 bracket formatting for URL contexts
    formatted_ip = _format_ip_for_nginx(ip)
    logger.info("Set ip in conf to %s (formatted: %s)", ip, formatted_ip)
    content = _replace_placeholder(content, default_vars["template_ip"], formatted_ip)

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

    # Write final configuration to target
    target_file = os.path.join(server_path, f"{domain}.conf")
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
