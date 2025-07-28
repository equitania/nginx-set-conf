"""
Configuration verification module for nginx-set-conf.

This module provides functionality to verify and sync nginx configuration files
between local templates and server installations.
"""

import hashlib
import logging
import click
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigVerification:
    """
    Handles verification and synchronization of nginx configuration files.
    """
    
    def __init__(self, local_config_path: str = "yaml_examples", server_config_path: str = "/etc/nginx"):
        """
        Initialize the configuration verification system.
        
        Args:
            local_config_path: Path to local template files
            server_config_path: Path to server nginx configuration
        """
        self.local_config_path = Path(local_config_path)
        self.server_config_path = Path(server_config_path)
        self.required_files = {
            "nginx.conf": "/etc/nginx/nginx.conf",
            "nginxconfig.io/general.conf": "/etc/nginx/nginxconfig.io/general.conf",
            "nginxconfig.io/security.conf": "/etc/nginx/nginxconfig.io/security.conf"
        }
    
    def calculate_file_hash(self, file_path: Path) -> Optional[str]:
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
            
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def get_file_info(self, file_path: Path) -> Dict:
        """
        Get detailed information about a configuration file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        info = {
            "path": str(file_path),
            "exists": file_path.exists(),
            "hash": None,
            "size": None,
            "modified": None
        }
        
        if file_path.exists():
            try:
                stat = file_path.stat()
                info["hash"] = self.calculate_file_hash(file_path)
                info["size"] = stat.st_size
                info["modified"] = stat.st_mtime
            except Exception as e:
                logger.error(f"Error getting file info for {file_path}: {e}")
        
        return info
    
    def verify_configuration_consistency(self) -> Dict[str, Dict]:
        """
        Compare content between local template files and server configuration files.
        
        Returns:
            Dictionary with verification results for each file
        """
        results = {}
        
        logger.info("Starting nginx configuration verification...")
        
        for file_name, server_abs_path in self.required_files.items():
            local_path = self.local_config_path / file_name
            server_path = Path(server_abs_path)
            
            local_info = self.get_file_info(local_path)
            server_info = self.get_file_info(server_path)
            
            # Determine consistency status
            consistent = False
            issues = []
            
            if not local_info["exists"]:
                issues.append("Template file missing")
            if not server_info["exists"]:
                issues.append("Server file missing")
            
            if local_info["exists"] and server_info["exists"]:
                if local_info["hash"] == server_info["hash"]:
                    consistent = True
                else:
                    issues.append("Content differs from template")
            
            results[file_name] = {
                "local": local_info,
                "server": server_info,
                "consistent": consistent,
                "issues": issues,
                "needs_update": not consistent and local_info["exists"]
            }
            
            status = "✓ consistent" if consistent else "✗ inconsistent"
            logger.info(f"Verified {file_name}: {status}")
        
        return results
    
    def show_verification_results(self, results: Dict[str, Dict]) -> None:
        """
        Display verification results in a user-friendly format.
        
        Args:
            results: Results from verify_configuration_consistency()
        """
        click.echo("\n" + "="*60)
        click.echo("NGINX CONFIGURATION VERIFICATION RESULTS")
        click.echo("="*60)
        
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
            if result["local"]["exists"]:
                click.echo(f"  Template: {result['local']['path']} ({result['local']['size']} bytes)")
            
            if result["consistent"]:
                consistent_count += 1
            elif result["needs_update"]:
                files_needing_update.append(file_name)
        
        click.echo(f"\n{'-'*60}")
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
    
    
    def sync_configurations(self, results: Dict[str, Dict]) -> bool:
        """
        Synchronize template files to server configuration.
        
        Args:
            results: Results from verify_configuration_consistency()
            
        Returns:
            True if sync was successful, False otherwise
        """
        files_to_update = []
        missing_files = []
        
        for file_name, result in results.items():
            if result["needs_update"]:
                files_to_update.append(file_name)
            elif not result["server"]["exists"] and result["local"]["exists"]:
                missing_files.append(file_name)
        
        if not files_to_update and not missing_files:
            click.echo("All configuration files are already up to date. Nothing to sync.")
            return False
        
        click.echo(f"\nConfiguration sync required:")
        
        if files_to_update:
            click.echo("\n🔄 Files with content differences:")
            for file_name in files_to_update:
                click.echo(f"  - {file_name}")
        
        if missing_files:
            click.echo("\n📁 Missing server files:")
            for file_name in missing_files:
                click.echo(f"  - {file_name}")
        
        click.echo("\nSync options:")
        click.echo("1. 🔧 Update server configurations from templates [RECOMMENDED]")
        click.echo("2. ❌ Cancel")
        
        choice = click.prompt("Select option", type=int, default=1)
        
        if choice == 1:
            click.echo("\nThis will:")
            click.echo("  • Create backup of current configuration")
            click.echo("  • Update server files with template content")
            click.echo("  • Preserve file permissions")
            
            if click.confirm("Proceed with configuration sync?"):
                # Create backup first
                if not self.backup_configuration():
                    click.echo("❌ Backup failed. Aborting sync.")
                    return False
                
                return self._perform_sync(results, files_to_update + missing_files)
        
        return False
    
    def _perform_sync(self, results: Dict[str, Dict], files_to_sync: list) -> bool:
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
            local_path = Path(result["local"]["path"])
            server_path = Path(result["server"]["path"])
            
            try:
                if not result["local"]["exists"]:
                    logger.warning(f"Cannot sync {file_name}: template file missing")
                    success = False
                    continue
                
                # Create server directory if it doesn't exist
                server_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy template file to server
                import shutil
                shutil.copy2(local_path, server_path)
                
                click.echo(f"✓ Updated {file_name}")
                logger.info(f"Synced {local_path} -> {server_path}")
                
            except Exception as e:
                click.echo(f"❌ Failed to update {file_name}: {e}")
                logger.error(f"Error syncing {file_name}: {e}")
                success = False
        
        return success
    
    def backup_configuration(self, backup_dir: str = "/tmp/nginx_backup") -> bool:
        """
        Create a backup of current server configuration.
        
        Args:
            backup_dir: Directory to store backups
            
        Returns:
            True if backup was successful, False otherwise
        """
        try:
            import shutil
            from datetime import datetime
            
            backup_path = Path(backup_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_path / f"nginx_config_backup_{timestamp}"
            
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Backup main nginx.conf
            server_nginx_conf = Path("/etc/nginx/nginx.conf")
            if server_nginx_conf.exists():
                shutil.copy2(server_nginx_conf, backup_path / "nginx.conf")
            
            # Backup nginxconfig.io directory
            server_nginxconfig_dir = Path("/etc/nginx/nginxconfig.io")
            if server_nginxconfig_dir.exists():
                shutil.copytree(server_nginxconfig_dir, 
                               backup_path / "nginxconfig.io")
            
            logger.info(f"Configuration backup created at: {backup_path}")
            click.echo(f"Backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False