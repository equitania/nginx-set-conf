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
    
    def __init__(self, local_config_path: str = "yaml_examples", 
                 server_config_path: str = "/etc/nginx"):
        """
        Initialize the configuration verification system.
        
        Args:
            local_config_path: Path to local configuration files
            server_config_path: Path to server nginx configuration
        """
        self.local_config_path = Path(local_config_path)
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
        Verify consistency between local and server configuration files.
        
        Returns:
            Dictionary with verification results for each file
        """
        results = {}
        
        logger.info("Starting configuration consistency verification...")
        
        for local_rel_path, server_abs_path in self.required_files.items():
            local_path = self.local_config_path / local_rel_path
            server_path = Path(server_abs_path)
            
            local_info = self.get_file_info(local_path)
            server_info = self.get_file_info(server_path)
            
            # Determine consistency status
            consistent = False
            issues = []
            
            if not local_info["exists"]:
                issues.append("Local file missing")
            if not server_info["exists"]:
                issues.append("Server file missing")
            
            if local_info["exists"] and server_info["exists"]:
                if local_info["hash"] == server_info["hash"]:
                    consistent = True
                else:
                    issues.append("File content differs")
            
            results[local_rel_path] = {
                "local": local_info,
                "server": server_info,
                "consistent": consistent,
                "issues": issues
            }
            
            logger.info(f"Verified {local_rel_path}: {'✓' if consistent else '✗'}")
        
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
        
        for file_path, result in results.items():
            status = "✓ CONSISTENT" if result["consistent"] else "✗ INCONSISTENT"
            color = "green" if result["consistent"] else "red"
            
            click.echo(f"\n{file_path}: ", nl=False)
            click.secho(status, fg=color)
            
            if result["issues"]:
                for issue in result["issues"]:
                    click.echo(f"  - {issue}")
            
            # Show file details if both exist but differ
            if (result["local"]["exists"] and result["server"]["exists"] and 
                not result["consistent"]):
                click.echo(f"  Local:  {result['local']['size']} bytes")
                click.echo(f"  Server: {result['server']['size']} bytes")
            
            if result["consistent"]:
                consistent_count += 1
        
        click.echo(f"\n{'-'*60}")
        click.echo(f"Summary: {consistent_count}/{total_count} files consistent")
        
        if consistent_count == total_count:
            click.secho("✓ All configuration files are consistent!", fg="green")
        else:
            click.secho("✗ Configuration inconsistencies detected!", fg="red")
    
    def sync_configuration_files(self, results: Dict[str, Dict], 
                                 direction: str = "local_to_server") -> bool:
        """
        Synchronize configuration files between local and server.
        
        Args:
            results: Results from verify_configuration_consistency()
            direction: 'local_to_server' or 'server_to_local'
            
        Returns:
            True if sync was successful, False otherwise
        """
        if direction not in ["local_to_server", "server_to_local"]:
            logger.error(f"Invalid sync direction: {direction}")
            return False
        
        success = True
        
        for file_path, result in results.items():
            if result["consistent"]:
                continue
            
            local_path = self.local_config_path / file_path
            server_path = Path(self.required_files[file_path])
            
            try:
                if direction == "local_to_server":
                    if result["local"]["exists"]:
                        # Create server directory if it doesn't exist
                        server_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy local file to server
                        import shutil
                        shutil.copy2(local_path, server_path)
                        logger.info(f"Copied {local_path} -> {server_path}")
                    else:
                        logger.warning(f"Cannot sync {file_path}: local file missing")
                        success = False
                
                else:  # server_to_local
                    if result["server"]["exists"]:
                        # Create local directory if it doesn't exist
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy server file to local
                        import shutil
                        shutil.copy2(server_path, local_path)
                        logger.info(f"Copied {server_path} -> {local_path}")
                    else:
                        logger.warning(f"Cannot sync {file_path}: server file missing")
                        success = False
            
            except Exception as e:
                logger.error(f"Error syncing {file_path}: {e}")
                success = False
        
        return success
    
    def interactive_sync_prompt(self, results: Dict[str, Dict]) -> bool:
        """
        Interactive prompt for resolving configuration discrepancies.
        
        Args:
            results: Results from verify_configuration_consistency()
            
        Returns:
            True if user chose to proceed with sync, False otherwise
        """
        inconsistent_files = [
            file_path for file_path, result in results.items() 
            if not result["consistent"]
        ]
        
        if not inconsistent_files:
            click.echo("No configuration discrepancies found. Nothing to sync.")
            return False
        
        click.echo(f"\nFound {len(inconsistent_files)} inconsistent files:")
        for file_path in inconsistent_files:
            click.echo(f"  - {file_path}")
        
        click.echo("\nSync options:")
        click.echo("1. Local -> Server (update server with local files)")
        click.echo("2. Server -> Local (update local files with server files)")
        click.echo("3. Cancel")
        
        choice = click.prompt("Select sync direction", type=int, default=3)
        
        if choice == 1:
            if click.confirm("This will overwrite server files. Continue?"):
                return self.sync_configuration_files(results, "local_to_server")
        elif choice == 2:
            if click.confirm("This will overwrite local files. Continue?"):
                return self.sync_configuration_files(results, "server_to_local")
        
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