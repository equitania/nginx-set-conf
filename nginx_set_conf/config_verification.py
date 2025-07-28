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
    Handles verification of nginx configuration files.
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
            "nginxconfig.io/ssl_stapling.conf": "/etc/nginx/nginxconfig.io/ssl_stapling.conf"
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
        Verify that required nginx configuration files exist on the server.
        
        Returns:
            Dictionary with verification results for each file
        """
        results = {}
        
        logger.info("Starting nginx configuration verification...")
        
        for file_name, server_abs_path in self.required_files.items():
            server_path = Path(server_abs_path)
            
            file_info = self.get_file_info(server_path)
            
            # Check if file exists
            exists = file_info["exists"]
            
            results[file_name] = {
                "path": server_abs_path,
                "exists": exists,
                "size": file_info["size"],
                "info": file_info
            }
            
            logger.info(f"Checked {file_name}: {'✓ exists' if exists else '✗ missing'}")
        
        return results
    
    def show_verification_results(self, results: Dict[str, Dict]) -> None:
        """
        Display verification results in a user-friendly format.
        
        Args:
            results: Results from verify_configuration_consistency()
        """
        click.echo("\n" + "="*60)
        click.echo("NGINX CONFIGURATION FILE CHECK")
        click.echo("="*60)
        
        existing_count = 0
        total_count = len(results)
        
        for file_name, result in results.items():
            status = "✓ EXISTS" if result["exists"] else "✗ MISSING"
            color = "green" if result["exists"] else "red"
            
            click.echo(f"\n{file_name}: ", nl=False)
            click.secho(status, fg=color)
            click.echo(f"  Path: {result['path']}")
            
            if result["exists"]:
                click.echo(f"  Size: {result['size']} bytes")
                existing_count += 1
            else:
                click.echo("  Status: File not found")
        
        click.echo(f"\n{'-'*60}")
        click.echo(f"Summary: {existing_count}/{total_count} files found")
        
        if existing_count == total_count:
            click.secho("✓ All required nginx configuration files exist!", fg="green")
        else:
            click.secho("✗ Some nginx configuration files are missing!", fg="red")
    
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
    
    
    def interactive_directory_creation(self, results: Dict[str, Dict]) -> bool:
        """
        Interactive prompt for creating missing directories.
        
        Args:
            results: Results from verify_configuration_consistency()
            
        Returns:
            True if directories were created, False otherwise
        """
        missing_files = []
        
        for file_name, result in results.items():
            if not result["exists"]:
                missing_files.append((file_name, result["path"]))
        
        if not missing_files:
            click.echo("All required nginx configuration files exist. Nothing to do.")
            return False
        
        click.echo(f"\nFound {len(missing_files)} missing files:")
        for file_name, path in missing_files:
            click.echo(f"  - {file_name} at {path}")
        
        # Check if it's just missing directories
        nginxconfig_missing = any("nginxconfig.io" in path for _, path in missing_files)
        
        if nginxconfig_missing:
            click.echo("\n📁 Missing nginxconfig.io directory structure detected.")
            click.echo("\nOptions:")
            click.echo("1. 🔧 Create missing directories")
            click.echo("2. ❌ Cancel")
            
            choice = click.prompt("Select option", type=int, default=1)
            
            if choice == 1:
                return self.create_missing_directories()
        else:
            click.echo("\n⚠️  Essential nginx configuration files are missing.")
            click.echo("Please ensure nginx is properly installed.")
        
        return False
    
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