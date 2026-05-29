"""
Configuration verification module for nginx-set-conf.

This module provides functionality to verify and sync nginx configuration files
using embedded templates.
"""

import hashlib
import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)

# Embedded template files
NGINX_CONF_TEMPLATE = """# nginx incl. SSL/http2 1.24.1
# Version 1.2 from 28.05.2026
user  nginx;
worker_processes  auto;
worker_rlimit_nofile 65535;
error_log  /var/log/nginx/error.log notice;
pid        /var/run/nginx.pid;

# Load modules
include              /etc/nginx/modules-enabled/*.conf;

events {
    # worker_connections  8192;
    # CPU Kerne x 1024 > CPU Kerne = grep processor /proc/cpuinfo | wc -l
    worker_connections 65535; #4096;
    multi_accept on;
}

http {

    ##
    # Basic Settings
    ##

    charset                utf-8;
    sendfile               on;
    tcp_nopush             on;
    tcp_nodelay            on;
    http2                  on;
    server_tokens          off;
    log_not_found          off;
    types_hash_max_size    2048;
    types_hash_bucket_size 64;
    client_max_body_size   16M;

    # MIME
    include                mime.types;
    default_type           application/octet-stream;

    ##
    # SSL Settings
    ##

    ssl_session_timeout    1d;
    ssl_session_cache      shared:SSL:10m;
    ssl_session_tickets    off;

    # Mozilla Intermediate configuration
    ssl_protocols          TLSv1.2 TLSv1.3;
    ssl_ciphers            ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;

    # OCSP Stapling - DISABLED by default due to Let's Encrypt issues
    # ssl_stapling           on;
    # ssl_stapling_verify    on;
    # resolver               1.1.1.1 1.0.0.1 8.8.8.8 8.8.4.4 208.67.222.222 208.67.220.220 valid=60s;
    # resolver_timeout       2s;

    ##
    # Logging Settings
    ##

    access_log             off;
    error_log              /var/log/nginx/error.log warn;

    include /etc/nginx/conf.d/*.conf;
}
"""

GENERAL_CONF_TEMPLATE = """# nginx incl. SSL/http2 1.24.1
# Version 1.1 from 17.07.2025

# favicon.ico
location = /favicon.ico {
    log_not_found off;
}

# gzip
gzip            on;
gzip_vary       on;
gzip_proxied    any;
gzip_comp_level 6;
gzip_types      text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml;
"""

SECURITY_CONF_TEMPLATE = r"""# nginx incl. SSL/http2 1.24.1
# Version 1.2 from 17.07.2025

# security headers
add_header X-XSS-Protection          "1; mode=block" always;
add_header X-Content-Type-Options    "nosniff" always;
add_header Referrer-Policy           "no-referrer-when-downgrade" always;
#add_header Content-Security-Policy   "default-src 'self' http: https: ws: wss: data: blob: 'unsafe-inline'; frame-ancestors 'self';" always;
add_header Permissions-Policy        "interest-cohort=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# . files
location ~ /\.(?!well-known) {
    deny all;
}
"""


class ConfigVerification:
    """
    Handles verification and synchronization of nginx configuration files using embedded templates.
    """

    def __init__(self, server_config_path: str = "/etc/nginx"):
        """
        Initialize the configuration verification system.

        Args:
            server_config_path: Path to server nginx configuration
        """
        self.server_config_path = Path(server_config_path)
        self.required_files = {
            "nginx.conf": "/etc/nginx/nginx.conf",
            "nginxconfig.io/general.conf": "/etc/nginx/nginxconfig.io/general.conf",
            "nginxconfig.io/security.conf": "/etc/nginx/nginxconfig.io/security.conf",
        }
        self.templates = {
            "nginx.conf": NGINX_CONF_TEMPLATE,
            "nginxconfig.io/general.conf": GENERAL_CONF_TEMPLATE,
            "nginxconfig.io/security.conf": SECURITY_CONF_TEMPLATE,
        }

    def calculate_file_hash(self, file_path: Path) -> str | None:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash string or None if file doesn't exist
        """
        try:
            if not file_path.exists():
                return None

            with open(file_path, "rb") as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get detailed information about a configuration file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        info = {"path": str(file_path), "exists": file_path.exists(), "hash": None, "size": None, "modified": None}

        if file_path.exists():
            try:
                stat = file_path.stat()
                info["hash"] = self.calculate_file_hash(file_path)
                info["size"] = stat.st_size
                info["modified"] = stat.st_mtime
            except Exception as e:
                logger.error(f"Error getting file info for {file_path}: {e}")

        return info

    def get_template_hash(self, file_name: str) -> str:
        """
        Calculate hash of embedded template content.

        Args:
            file_name: Name of the template file

        Returns:
            SHA256 hash of template content
        """
        template_content = self.templates.get(file_name, "")
        return hashlib.sha256(template_content.encode("utf-8")).hexdigest()

    def verify_configuration_consistency(self) -> dict[str, dict]:
        """
        Compare content between embedded templates and server configuration files.

        Returns:
            Dictionary with verification results for each file
        """
        results = {}

        logger.info("Starting nginx configuration verification...")

        for file_name, server_abs_path in self.required_files.items():
            server_path = Path(server_abs_path)
            server_info = self.get_file_info(server_path)

            # Get template hash
            template_hash = self.get_template_hash(file_name)
            template_size = len(self.templates[file_name].encode("utf-8"))

            # Determine consistency status
            consistent = False
            issues = []

            if not server_info["exists"]:
                issues.append("Server file missing")
            else:
                if server_info["hash"] == template_hash:
                    consistent = True
                else:
                    issues.append("Content differs from template")

            results[file_name] = {
                "template": {"hash": template_hash, "size": template_size, "exists": True},
                "server": server_info,
                "consistent": consistent,
                "issues": issues,
                "needs_update": not consistent,
            }

            status = "✓ consistent" if consistent else "✗ inconsistent"
            logger.info(f"Verified {file_name}: {status}")

        return results

    def show_verification_results(self, results: dict[str, dict]) -> None:
        """
        Display verification results in a user-friendly format.

        Args:
            results: Results from verify_configuration_consistency()
        """
        click.echo("\n" + "=" * 60)
        click.echo("NGINX CONFIGURATION VERIFICATION RESULTS")
        click.echo("=" * 60)

        consistent_count = 0
        total_count = len(results)
        files_needing_update = []

        for file_name, result in results.items():
            status = "✓ CONSISTENT" if result["consistent"] else "✗ INCONSISTENT"
            color = "green" if result["consistent"] else "red"

            click.echo(f"\n{file_name}: ", nl=False)
            click.secho(status, fg=color)

            if result["issues"]:
                for issue in result["issues"]:
                    click.echo(f"  - {issue}")

            # Show file details
            if result["server"]["exists"]:
                click.echo(f"  Server: {result['server']['path']} ({result['server']['size']} bytes)")
            click.echo(f"  Template: embedded ({result['template']['size']} bytes)")

            if result["consistent"]:
                consistent_count += 1
            elif result["needs_update"]:
                files_needing_update.append(file_name)

        click.echo(f"\n{'-' * 60}")
        click.echo(f"Summary: {consistent_count}/{total_count} files consistent")

        if consistent_count == total_count:
            click.secho("✓ All configuration files are up to date!", fg="green")
        else:
            click.secho("✗ Configuration inconsistencies detected!", fg="red")
            if files_needing_update:
                click.echo(f"\nFiles that can be updated: {', '.join(files_needing_update)}")

    def create_missing_directories(self) -> bool:
        """
        Create missing nginx configuration directories.

        Returns:
            True if all directories were created successfully
        """
        try:
            # Ensure nginxconfig.io directory exists
            nginxconfig_dir = Path("/etc/nginx/nginxconfig.io")
            nginxconfig_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {nginxconfig_dir}")
            return True
        except Exception as e:
            logger.error(f"Error creating directories: {e}")
            return False

    def sync_configurations(self, results: dict[str, dict], force: bool = False) -> bool:
        """
        Synchronize template files to server configuration.

        Without --force, the method aborts when server files with content
        differences exist, printing a data-loss warning. With force=True,
        the same warning is emitted as a notice and the sync proceeds.
        Missing server files (not yet present on disk) are always safe to
        create and are not subject to the force gate.

        Args:
            results: Results from verify_configuration_consistency()
            force: If True, proceed with overwriting differing server files
                   after printing a data-loss notice. If False (default),
                   abort when differing server files are detected.

        Returns:
            True if sync was successful, False otherwise
        """
        files_to_update = []
        missing_files = []

        for file_name, result in results.items():
            if result["needs_update"]:
                if result["server"]["exists"]:
                    files_to_update.append(file_name)
                else:
                    missing_files.append(file_name)

        if not files_to_update and not missing_files:
            click.echo("All configuration files are already up to date. Nothing to sync.")
            return False

        # Data-loss guard: existing server files with custom operator changes
        # will be permanently overwritten. Gate on --force.
        if files_to_update:
            click.secho(
                "\nWARNING: The following server files differ from the embedded templates.\n"
                "Any operator-local customisations (manual edits, local tuning,\n"
                "site-specific overrides) in these files will be permanently overwritten:",
                fg="yellow",
                err=False,
            )
            for file_name in files_to_update:
                click.echo(f"  - {file_name}")

            if not force:
                click.echo(
                    "\nAborting. Pass --force to proceed with overwriting these files."
                )
                return False

            # force=True: continue after the warning notice
            click.secho(
                "\nNOTICE: --force specified. Proceeding with overwrite.\n"
                "Operator-local customisations will be lost.",
                fg="yellow",
                err=False,
            )

        if missing_files:
            click.echo("\nMissing server files to be created:")
            for file_name in missing_files:
                click.echo(f"  - {file_name}")

        # Create backup first
        if not self.backup_configuration():
            click.echo("Backup failed. Aborting sync.")
            return False

        return self._perform_sync(results, files_to_update + missing_files)

    def _perform_sync(self, results: dict[str, dict], files_to_sync: list) -> bool:
        """
        Perform the actual file synchronization.

        Args:
            results: Verification results
            files_to_sync: List of file names to sync

        Returns:
            True if all files were synced successfully
        """
        success = True

        for file_name in files_to_sync:
            result = results[file_name]
            server_path = Path(result["server"]["path"])
            template_content = self.templates[file_name]

            try:
                # Create server directory if it doesn't exist
                server_path.parent.mkdir(parents=True, exist_ok=True)

                # Write template content to server file
                with open(server_path, "w", encoding="utf-8") as f:
                    f.write(template_content)

                click.echo(f"✓ Updated {file_name}")
                logger.info(f"Updated {server_path} with embedded template")

            except Exception as e:
                click.echo(f"❌ Failed to update {file_name}: {e}")
                logger.error(f"Error syncing {file_name}: {e}")
                success = False

        return success

    def backup_configuration(
        self,
        backup_dir: str = "/var/backups/nginx_set_conf",
        nginx_conf_path: str = "/etc/nginx/nginx.conf",
        nginxconfig_dir: str = "/etc/nginx/nginxconfig.io",
    ) -> bool:
        """
        Create a backup of current server configuration.

        Backups are written to a root-owned directory (mode 0700) to prevent
        symlink attacks. The default location is FHS-compliant at
        /var/backups/nginx_set_conf. A world-writable path such as /tmp must
        not be used, since the tool typically runs as root.

        Args:
            backup_dir: Directory to store backups. Must be a root-owned,
                non-world-writable path.
            nginx_conf_path: Path to the nginx.conf file to back up. Defaults
                to /etc/nginx/nginx.conf. Injectable for testing.
            nginxconfig_dir: Path to the nginxconfig.io directory to back up.
                Defaults to /etc/nginx/nginxconfig.io. Injectable for testing.

        Returns:
            True if backup was successful, False otherwise
        """
        try:
            import shutil
            from datetime import datetime

            backup_root = Path(backup_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_root / f"nginx_config_backup_{timestamp}"

            # Create root directory with restrictive permissions; refuse to
            # follow symlinks for the backup destination itself.
            backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if backup_path.exists() or backup_path.is_symlink():
                logger.error(f"Backup target already exists or is a symlink: {backup_path}")
                return False
            backup_path.mkdir(mode=0o700, parents=False, exist_ok=False)

            # Backup main nginx.conf
            server_nginx_conf = Path(nginx_conf_path)
            if server_nginx_conf.exists():
                target = backup_path / "nginx.conf"
                if target.is_symlink():
                    logger.error(f"Refusing to follow symlink at backup target: {target}")
                    return False
                shutil.copy2(server_nginx_conf, target)

            # Backup nginxconfig.io directory
            server_nginxconfig_dir = Path(nginxconfig_dir)
            if server_nginxconfig_dir.exists():
                if server_nginxconfig_dir.is_symlink():
                    logger.error(
                        "Refusing to backup symlinked source directory: %s",
                        server_nginxconfig_dir,
                    )
                    return False
                shutil.copytree(
                    server_nginxconfig_dir,
                    backup_path / "nginxconfig.io",
                    symlinks=False,
                )

            logger.info(f"Configuration backup created at: {backup_path}")
            click.echo(f"Backup created: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
