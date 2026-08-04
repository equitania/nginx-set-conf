"""
Configuration verification module for nginx-set-conf.

This module provides functionality to verify and sync nginx configuration files
using embedded templates.
"""

import hashlib
import logging
import re
import subprocess
from pathlib import Path

import click

logger = logging.getLogger(__name__)

# Dynamic modules (njs, brotli, geoip2, ...) are installed per host, so an
# embedded template can never know which ones a given server loads. These lines
# are carried over from the existing nginx.conf on every sync — dropping one
# makes every vhost using that module's directives fail `nginx -t`.
LOAD_MODULE_PATTERN = re.compile(r"^[ \t]*load_module[ \t]+[^;]+;", re.MULTILINE)

# Embedded template files
NGINX_CONF_TEMPLATE = r"""# nginx incl. SSL/http2 1.26.2
# Version 1.6 from 04.08.2026
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
    # Since nginx 1.25.1 this directive is the ONLY way to enable HTTP/2 — the
    # old `listen ... http2` parameter is deprecated and ignored. The vhost
    # templates emit a plain `listen <ip>:443 ssl;`, so without this line every
    # vhost silently serves HTTP/1.1 only.
    http2                  on;
    server_tokens          off;
    log_not_found          off;
    types_hash_max_size    2048;
    types_hash_bucket_size 64;
    client_max_body_size   16M;

    ##
    # Buffer Size Settings
    ##
    
    client_body_buffer_size 16k;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 8k;

    ##
    # Timeout Settings
    ##
    
    client_body_timeout 12;
    client_header_timeout 12;
    keepalive_timeout 15;
    send_timeout 10;

    ##
    # Rate Limiting
    ##
    
    limit_req_zone $binary_remote_addr zone=one:10m rate=1r/s;
    limit_conn_zone $binary_remote_addr zone=addr:10m;

    ##
    # Gzip Settings
    ##
    
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml;

    ##
    # Cache Settings
    ##
    
    # Proxy Cache
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m inactive=60m use_temp_path=off;
    proxy_cache_key "$scheme$request_method$host$request_uri";

    # FastCGI Cache
    fastcgi_cache_path /var/cache/nginx/fastcgi levels=1:2 keys_zone=fastcgi_cache:10m max_size=10g inactive=60m use_temp_path=off;
    fastcgi_cache_key "$request_method$request_uri";
    fastcgi_cache_use_stale error timeout http_500 http_503;
    fastcgi_cache_valid 200 60m;

    # Open File Cache
    open_file_cache max=1000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;

    # MIME
    include                mime.types;
    default_type           application/octet-stream;

    ##
    # Security Headers
    ##
    #
    # Security headers are NOT set here. nginx does not inherit add_header into a
    # server/location block that defines its own add_header, so duplicating them
    # here only created a divergent, dead set. They live in
    # nginxconfig.io/security.conf, which every vhost includes (single source).

    ##
    # SSL Settings
    ##

    ssl_session_timeout    1d;
    ssl_session_cache      shared:SSL:10m;
    ssl_session_tickets    off;

    # Mozilla Intermediate configuration
    ssl_protocols          TLSv1.2 TLSv1.3;
    ssl_ciphers            ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;

    # OCSP Stapling — disabled.
    # Let's Encrypt retired OCSP in May 2025; renewed certificates no longer
    # carry an OCSP responder URL, so nginx logs a warning per cert at startup
    # and stapling does nothing useful. Re-enable only if you switch to a CA
    # that still issues OCSP-bearing certs.
    ssl_stapling           off;
    ssl_stapling_verify    off;
    resolver               1.1.1.1 1.0.0.1 8.8.8.8 8.8.4.4 208.67.222.222 208.67.220.220 valid=60s;
    resolver_timeout       2s;

    ##
    # Logging Settings
    ##

    access_log             off;
    error_log              /var/log/nginx/error.log warn;

    ##
    # Error Pages
    ##
    #
    # Error pages are defined per vhost (nginx-set-conf templates set
    # `error_page 500 502 503 504 /custom_50x.html;` + a serving location with
    # root /etc/nginx/html/). The previous global `/404.html` / `/50x.html` had no
    # serving location and did not match the deployed custom_50x.html — removed.

    ##
    # Server Blocks
    ##
    
    # Default server block with common location settings
    server {
        # Browser cache settings
        location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
            expires 1y;
            add_header Cache-Control "public, no-transform";
        }

        # Deny access to hidden files
        location ~ /\. {
            deny all;
            access_log off;
            log_not_found off;
        }
    }

    # Host-specific http-level directives: js_import for njs, custom maps,
    # upstreams, extra cache zones — anything this shared template cannot know
    # about. Neither deploy-nginx-base.sh nor nginx-set-conf writes into this
    # directory, so whatever is placed here survives every base-config sync.
    #
    # Why it exists: load_module lines are carried over automatically, but a
    # matching `js_import` lives in the http block and used to be lost on every
    # sync — leaving a vhost with `js_access` that could no longer resolve it
    # ("no imports defined for ..."). Put the js_import in a file here.
    #
    # A missing directory is not an error for a wildcard include.
    include /etc/nginx/conf.local.d/*.conf;

    include /etc/nginx/conf.d/*.conf;
}
"""

GENERAL_CONF_TEMPLATE = r"""# nginx incl. SSL/http2 1.26.2
# Version 1.1 from 27.05.2026

# favicon.ico
location = /favicon.ico {
    log_not_found off;
}

# gzip removed in v1.1: it is configured globally in the http{} block of
# nginx.conf, so repeating it per vhost here was redundant.
"""

SECURITY_CONF_TEMPLATE = r"""# nginx incl. SSL/http2 1.26.2
# Version 1.4 from 04.08.2026
#
# Single source of truth for security headers — included by every vhost
# (nginx does NOT inherit add_header into blocks that set their own, so headers
# are kept here rather than duplicated in the http{} block of nginx.conf).

# security headers
add_header X-Frame-Options           "SAMEORIGIN" always;
# X-XSS-Protection removed in v1.3: deprecated and ignored by modern browsers
# (can even introduce side-channels); CSP frame-ancestors covers the intent.
add_header X-Content-Type-Options    "nosniff" always;
add_header Referrer-Policy           "strict-origin-when-cross-origin" always;
# CSP tuned for Odoo: ws/wss for longpolling, unsafe-inline for Odoo's inline
# assets, data/blob for images; frame-ancestors 'self' backs up X-Frame-Options.
#
# 'unsafe-eval' is REQUIRED from Odoo 17 on and non-negotiable for Odoo 19: OWL
# compiles its templates at runtime via new Function(). Without it the browser
# blocks that call and the login page renders blank — with nothing in the nginx
# log, because the block happens client-side. Never drop it while Odoo is
# served from this vhost.
add_header Content-Security-Policy    "default-src 'self' http: https: ws: wss: data: blob: 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self';" always;
add_header Permissions-Policy        "interest-cohort=()" always;
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

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
                click.echo("\nAborting. Pass --force to proceed with overwriting these files.")
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

    @staticmethod
    def _preserve_load_modules(
        file_name: str, template_content: str, server_path: Path
    ) -> str:
        """Carry host-specific ``load_module`` lines into the template.

        Only nginx.conf can hold them (``load_module`` is a main-context
        directive). Deduplicated by the module path, so repeated syncs do not
        stack them up.
        """
        if file_name != "nginx.conf" or not server_path.is_file():
            return template_content
        try:
            existing = server_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return template_content

        carried = []
        for line in LOAD_MODULE_PATTERN.findall(existing):
            module_path = line.split("load_module", 1)[1].split(";")[0]
            module_path = module_path.strip().strip("\"'")
            if module_path and module_path not in template_content:
                carried.append(line.strip())
                logger.info("Carrying over host module: %s", module_path)
        if not carried:
            return template_content
        click.echo(f"  ↳ kept {len(carried)} host-specific load_module line(s)")
        return "\n".join(carried) + "\n\n" + template_content

    @staticmethod
    def _nginx_test() -> "tuple[bool, str]":
        """Run ``nginx -t`` and return (ok, combined output).

        utils._run_command() returns only a bool and puts the output on
        logger.debug, so an operator running at INFO never learns *why* a
        validation failed — which is the one thing needed to fix it.
        """
        try:
            result = subprocess.run(
                ["nginx", "-t"], capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0, f"{result.stdout}{result.stderr}".strip()
        except FileNotFoundError:
            return False, "nginx binary not found"
        except subprocess.TimeoutExpired:
            return False, "nginx -t timed out"
        except OSError as exc:
            return False, str(exc)

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
            template_content = self._preserve_load_modules(
                file_name, self.templates[file_name], server_path
            )

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
    ) -> "str | None":
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
            The backup directory path (str) on success, None on failure.
            Callers that only need a boolean can rely on the truthiness of
            the return value (a path is truthy, None is falsy).
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
                return None
            backup_path.mkdir(mode=0o700, parents=False, exist_ok=False)

            # Backup main nginx.conf
            server_nginx_conf = Path(nginx_conf_path)
            if server_nginx_conf.exists():
                target = backup_path / "nginx.conf"
                if target.is_symlink():
                    logger.error(f"Refusing to follow symlink at backup target: {target}")
                    return None
                shutil.copy2(server_nginx_conf, target)

            # Backup nginxconfig.io directory
            server_nginxconfig_dir = Path(nginxconfig_dir)
            if server_nginxconfig_dir.exists():
                if server_nginxconfig_dir.is_symlink():
                    logger.error(
                        "Refusing to backup symlinked source directory: %s",
                        server_nginxconfig_dir,
                    )
                    return None
                shutil.copytree(
                    server_nginxconfig_dir,
                    backup_path / "nginxconfig.io",
                    symlinks=False,
                )

            logger.info(f"Configuration backup created at: {backup_path}")
            click.echo(f"Backup created: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    def restore_configuration(
        self,
        backup_path: str,
        nginx_conf_path: str = "/etc/nginx/nginx.conf",
        nginxconfig_dir: str = "/etc/nginx/nginxconfig.io",
    ) -> bool:
        """
        Restore server configuration from a backup created by
        backup_configuration().

        Used as the rollback step of the pre-flight repair: if `nginx -t`
        fails after a resync, the previous state is copied back so the
        pre-flight makes no net change. Mirrors the symlink-refusal guards
        of backup_configuration().

        Args:
            backup_path: Backup directory returned by backup_configuration().
            nginx_conf_path: Target path for the main nginx.conf. Injectable
                for testing.
            nginxconfig_dir: Target nginxconfig.io directory. Injectable for
                testing.

        Returns:
            True if the restore succeeded, False otherwise.
        """
        try:
            import shutil

            backup_root = Path(backup_path)
            if not backup_root.is_dir():
                logger.error(f"Backup path is not a directory: {backup_root}")
                return False

            # Restore main nginx.conf
            backup_nginx_conf = backup_root / "nginx.conf"
            if backup_nginx_conf.exists() and not backup_nginx_conf.is_symlink():
                target = Path(nginx_conf_path)
                if target.is_symlink():
                    logger.error(f"Refusing to restore over a symlink: {target}")
                    return False
                shutil.copy2(backup_nginx_conf, target)

            # Restore nginxconfig.io directory
            backup_nginxconfig_dir = backup_root / "nginxconfig.io"
            if backup_nginxconfig_dir.is_dir() and not backup_nginxconfig_dir.is_symlink():
                target_dir = Path(nginxconfig_dir)
                if target_dir.is_symlink():
                    logger.error("Refusing to restore over a symlinked directory: %s", target_dir)
                    return False
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(
                    backup_nginxconfig_dir,
                    target_dir,
                    symlinks=False,
                )

            logger.info(f"Configuration restored from backup: {backup_root}")
            click.echo(f"Configuration restored from backup: {backup_root}")
            return True

        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False

    def preflight_check_and_repair(self) -> bool:
        """
        Pre-flight gate run before every real vhost deployment.

        Verifies the three managed base config files (nginx.conf,
        general.conf, security.conf) against the embedded templates and
        auto-repairs any drift before a new domain is deployed — so a vhost
        is never written on top of a broken base (e.g. an Odoo-breaking CSP
        in security.conf that lacks 'unsafe-eval').

        On drift: back up, resync the divergent files from the embedded
        templates, then validate with `nginx -t`. If the resync or
        validation fails, the previous state is restored from the backup
        (atomic: the pre-flight then made no net change). The corrected base
        files are activated by the deploy's final nginx reload.

        After a failed repair the verdict depends on what the rollback
        restored: a base config that validates on its own is merely *different*
        from this version's templates — typically a host running a newer
        nginx.conf than the package ships — and the deploy continues with a
        warning. Only a base that is still invalid after the rollback aborts
        the deploy, because then the fault predates this repair.

        Returns:
            True if the base config is consistent (already, after a successful
            repair, or after a rollback that restored a valid config); False
            only if the config is invalid independently of this repair.
        """
        results = self.verify_configuration_consistency()
        divergent = [name for name, result in results.items() if result["needs_update"]]

        if not divergent:
            click.echo("[pre-flight] Base nginx configs are consistent.")
            return True

        click.secho(
            "[pre-flight] Drift detected in: " + ", ".join(divergent) + " — auto-repairing.",
            fg="yellow",
        )

        backup_path = self.backup_configuration()
        if not backup_path:
            click.secho("[pre-flight] Backup failed — aborting deploy.", fg="red")
            return False

        if not self._perform_sync(results, divergent):
            click.secho("[pre-flight] Resync failed — rolling back.", fg="red")
            self.restore_configuration(backup_path)
            return False

        ok, output = self._nginx_test()
        if not ok:
            click.secho("[pre-flight] nginx -t failed after repair — rolling back.", fg="red")
            for line in output.splitlines():
                click.secho(f"    {line}", fg="red")
            self.restore_configuration(backup_path)

            # Whether this aborts the deploy depends on what the rollback
            # restored. A base config that validates fine on its own is simply
            # not identical to the embedded template — a server carrying a
            # newer or locally extended nginx.conf must stay deployable, or
            # this gate would lock out every host that is ahead of the package.
            # Only a base that is broken *independently* of this repair is a
            # real reason to stop.
            restored_ok, restored_output = self._nginx_test()
            if restored_ok:
                click.secho(
                    "[pre-flight] Rollback restored a valid config — continuing. "
                    "The base files differ from this version's templates; see above "
                    "for what the templates would break.",
                    fg="yellow",
                )
                return True

            click.secho(
                "[pre-flight] Config is invalid even after rollback — the fault is "
                "not (only) in the base files:", fg="red")
            for line in restored_output.splitlines():
                click.secho(f"    {line}", fg="red")
            return False

        click.secho("[pre-flight] Base configs repaired and validated.", fg="green")
        return True
