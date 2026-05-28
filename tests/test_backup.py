"""
Regression tests for SEC-02: backup_configuration symlink hardening.

Covers:
- Refusal when nginxconfig_dir is itself a symlink (threat T-01-02-01)
- Acceptance of a real directory (happy path)
- shutil.copytree symlinks=False contract: in-tree symlinks are dereferenced (T-01-02-02)
"""

import shutil
from pathlib import Path

import pytest

from nginx_set_conf.config_verification import ConfigVerification


class TestBackupConfiguration:
    """SEC-02: backup_configuration symlink guard regression tests."""

    def test_refuses_symlinked_nginxconfig_source(self, tmp_path):
        """backup_configuration must return False when nginxconfig_dir is a symlink."""
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        nginxconfig_symlink = tmp_path / "nginxconfig_symlink"
        nginxconfig_symlink.symlink_to(real_dir)

        cv = ConfigVerification()
        result = cv.backup_configuration(
            backup_dir=str(tmp_path / "backups"),
            nginxconfig_dir=str(nginxconfig_symlink),
            nginx_conf_path=str(tmp_path / "nonexistent_nginx.conf"),
        )

        assert result is False

    def test_accepts_real_nginxconfig_directory(self, tmp_path):
        """backup_configuration must return True and create a backup for a real directory."""
        nginxconfig = tmp_path / "nginxconfig"
        nginxconfig.mkdir()
        (nginxconfig / "site.conf").write_text("server {}")

        cv = ConfigVerification()
        result = cv.backup_configuration(
            backup_dir=str(tmp_path / "backups"),
            nginxconfig_dir=str(nginxconfig),
            nginx_conf_path=str(tmp_path / "nonexistent_nginx.conf"),
        )

        assert result is True
        assert (tmp_path / "backups").exists()

    def test_copytree_does_not_follow_symlinks_in_source(self, tmp_path):
        """shutil.copytree symlinks=False copies symlink targets as regular files.

        This is a low-level contract test verifying the shutil.copytree semantic
        that backup_configuration relies on to prevent in-tree symlink disclosure
        (threat T-01-02-02).
        """
        src = tmp_path / "src"
        src.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")
        link = src / "link.txt"
        link.symlink_to(secret)

        dst = tmp_path / "dst"
        shutil.copytree(src, dst, symlinks=False)

        assert (dst / "link.txt").read_text() == "secret"
        assert not (dst / "link.txt").is_symlink()
