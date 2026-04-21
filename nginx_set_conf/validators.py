"""
Input validation for nginx-set-conf parameters.

Provides validation functions for all user-supplied parameters to prevent
shell injection, nginx config injection, and path traversal attacks.
"""

import ipaddress
import os
import re

# RFC 1123 compliant hostname regex (also allows wildcard subdomains)
_DOMAIN_RE = re.compile(
    r"^(\*\.)?([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
)

# Allowed characters for certificate names/paths
_CERT_PATH_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")

# Allowed characters for auth file paths
_AUTH_FILE_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")

# Valid template names (whitelist)
VALID_TEMPLATES = {
    "code_server",
    "fast_report",
    "flowise",
    "guacamole",
    "kasm",
    "mailpit",
    "n8n",
    "nextcloud",
    "odoo_http",
    "odoo_ssl",
    "pgadmin",
    "portainer",
    "pwa",
    "qdrant",
    "redirect",
    "redirect_ssl",
    "supabase",
}

# Backward compatibility: old template names with ngx_ prefix
VALID_TEMPLATES_COMPAT = {f"ngx_{t}" for t in VALID_TEMPLATES}


class ValidationError(ValueError):
    """Raised when input validation fails."""

    pass


def validate_domain(domain: str) -> str:
    """Validate domain name against RFC 1123.

    Args:
        domain: Domain name to validate.

    Returns:
        The validated domain name.

    Raises:
        ValidationError: If domain is invalid.
    """
    if not domain:
        raise ValidationError("Domain name must not be empty")
    if len(domain) > 253:
        raise ValidationError(f"Domain name too long: {len(domain)} chars (max 253)")
    if not _DOMAIN_RE.match(domain):
        raise ValidationError(f"Invalid domain name: '{domain}'. Must be a valid RFC 1123 hostname")
    return domain


def validate_ip(ip: str) -> str:
    """Validate IP address.

    Args:
        ip: IP address string to validate.

    Returns:
        The validated IP address string.

    Raises:
        ValidationError: If IP address is invalid.
    """
    if not ip:
        raise ValidationError("IP address must not be empty")
    try:
        ipaddress.ip_address(ip)
    except ValueError as e:
        raise ValidationError(f"Invalid IP address: '{ip}'. Must be a valid IPv4 or IPv6 address") from e
    return ip


def validate_port(port: str) -> str:
    """Validate port number.

    Args:
        port: Port number as string.

    Returns:
        The validated port string.

    Raises:
        ValidationError: If port is invalid.
    """
    if not port:
        return port
    try:
        port_int = int(port)
    except ValueError as e:
        raise ValidationError(f"Invalid port: '{port}'. Must be a number") from e
    if not 1 <= port_int <= 65535:
        raise ValidationError(f"Port out of range: {port_int}. Must be between 1 and 65535")
    return str(port_int)


def validate_allowed_ips(allowed_ips: str) -> str:
    """Validate comma-separated list of IP addresses or CIDR blocks.

    Args:
        allowed_ips: Comma-separated IP/CIDR strings.

    Returns:
        The validated allowed_ips string.

    Raises:
        ValidationError: If any IP/CIDR is invalid.
    """
    if not allowed_ips:
        return allowed_ips
    for entry in allowed_ips.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError as e:
            raise ValidationError(
                f"Invalid IP/CIDR in allowed_ips: '{entry}'. "
                "Must be a valid IP address or CIDR block (e.g., '192.168.1.0/24')"
            ) from e
    return allowed_ips


def validate_target_path(target_path: str) -> str:
    """Validate target path for configuration files.

    Ensures the path is absolute and does not contain path traversal.

    Args:
        target_path: Target directory path.

    Returns:
        The validated and resolved target path.

    Raises:
        ValidationError: If path is invalid or contains traversal.
    """
    if not target_path:
        return target_path
    resolved = os.path.realpath(target_path)
    if ".." in target_path:
        raise ValidationError(f"Path traversal detected in target_path: '{target_path}'")
    if not os.path.isabs(resolved):
        raise ValidationError(f"Target path must be absolute: '{target_path}'")
    return resolved


def _reject_path_traversal(value: str, field: str) -> None:
    """Raise ValidationError if value contains a path-traversal component.

    The character-class regex used for cert/auth paths permits '.' and '/',
    so '../' slips through. `..` components must be rejected on the raw
    input — `os.path.normpath()` silently collapses `..` segments inside
    absolute paths (e.g. `/etc/ssl/../../../etc/shadow` → `/etc/shadow`),
    which would let a payload like `/etc/ssl/../../../etc/shadow` bypass
    the check entirely. Split the original value on both Unix and Windows
    separators and reject any literal `..` segment.
    """
    normalised_separators = value.replace("\\", "/")
    if ".." in normalised_separators.split("/"):
        raise ValidationError(f"Path traversal detected in {field}: '{value}'")


def validate_cert_name(cert_name: str) -> str:
    """Validate certificate name/path.

    Args:
        cert_name: Certificate name or path.

    Returns:
        The validated certificate name.

    Raises:
        ValidationError: If cert_name contains invalid characters.
    """
    if not cert_name:
        return cert_name
    if not _CERT_PATH_RE.match(cert_name):
        raise ValidationError(
            f"Invalid certificate name: '{cert_name}'. "
            "Only alphanumeric characters, dots, slashes, hyphens, and underscores are allowed"
        )
    _reject_path_traversal(cert_name, "cert_name")
    return cert_name


def validate_cert_key(cert_key: str) -> str:
    """Validate certificate key path.

    Args:
        cert_key: Certificate key path.

    Returns:
        The validated certificate key path.

    Raises:
        ValidationError: If cert_key contains invalid characters.
    """
    if not cert_key:
        return cert_key
    if not _CERT_PATH_RE.match(cert_key):
        raise ValidationError(
            f"Invalid certificate key path: '{cert_key}'. "
            "Only alphanumeric characters, dots, slashes, hyphens, and underscores are allowed"
        )
    _reject_path_traversal(cert_key, "cert_key")
    return cert_key


def validate_auth_file(auth_file: str) -> str:
    """Validate authentication file path.

    Args:
        auth_file: Path to htaccess auth file.

    Returns:
        The validated auth file path.

    Raises:
        ValidationError: If auth_file contains invalid characters.
    """
    if not auth_file:
        return auth_file
    if not _AUTH_FILE_RE.match(auth_file):
        raise ValidationError(
            f"Invalid auth file path: '{auth_file}'. "
            "Only alphanumeric characters, dots, slashes, hyphens, and underscores are allowed"
        )
    _reject_path_traversal(auth_file, "auth_file")
    return auth_file


def validate_config_template(template: str) -> str:
    """Validate config template name against whitelist.

    Args:
        template: Template name to validate.

    Returns:
        The validated template name (without ngx_ prefix if present).

    Raises:
        ValidationError: If template name is not in the whitelist.
    """
    if not template:
        raise ValidationError("Config template must not be empty")

    # Strip ngx_ prefix for backward compatibility
    clean_name = template
    if template.startswith("ngx_"):
        clean_name = template[4:]

    if clean_name not in VALID_TEMPLATES:
        raise ValidationError(f"Unknown template: '{template}'. Valid templates: {', '.join(sorted(VALID_TEMPLATES))}")
    return clean_name


def validate_redirect_domain(redirect_domain: str) -> str:
    """Validate redirect domain name.

    Args:
        redirect_domain: Redirect target domain.

    Returns:
        The validated redirect domain.

    Raises:
        ValidationError: If domain is invalid.
    """
    if not redirect_domain:
        return redirect_domain
    return validate_domain(redirect_domain)


def validate_all_inputs(
    config_template: str,
    domain: str,
    ip: str,
    port: str,
    cert_name: str = "",
    cert_key: str = "",
    pollport: str = "",
    grpcport: str = "",
    redirect_domain: str = "",
    auth_file: str = "",
    allowed_ips: str = "",
    target_path: str = "",
    backend_ip: str = "",
) -> None:
    """Validate all input parameters at once.

    Args:
        All parameters from execute_commands.

    Raises:
        ValidationError: If any parameter is invalid.
    """
    validate_config_template(config_template)
    validate_domain(domain)
    validate_ip(ip)
    validate_port(port)
    validate_cert_name(cert_name)
    validate_cert_key(cert_key)
    if pollport:
        validate_port(pollport)
    if grpcport:
        validate_port(grpcport)
    if redirect_domain:
        validate_redirect_domain(redirect_domain)
    if auth_file:
        validate_auth_file(auth_file)
    if allowed_ips:
        validate_allowed_ips(allowed_ips)
    if target_path:
        validate_target_path(target_path)
    if backend_ip:
        validate_ip(backend_ip)
