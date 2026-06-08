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
        """backup_configuration must return None when nginxconfig_dir is a symlink."""
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

        assert result is None

    def test_accepts_real_nginxconfig_directory(self, tmp_path):
        """backup_configuration must return the backup path and create a backup for a real directory."""
        nginxconfig = tmp_path / "nginxconfig"
        nginxconfig.mkdir()
        (nginxconfig / "site.conf").write_text("server {}")

        cv = ConfigVerification()
        result = cv.backup_configuration(
            backup_dir=str(tmp_path / "backups"),
            nginxconfig_dir=str(nginxconfig),
            nginx_conf_path=str(tmp_path / "nonexistent_nginx.conf"),
        )

        assert isinstance(result, str)
        assert Path(result).is_dir()
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


class TestRestoreConfiguration:
    """restore_configuration round-trip and symlink-refusal."""

    def test_backup_restore_round_trip(self, tmp_path):
        """A backup followed by a restore returns files to their original content."""
        nginxconfig = tmp_path / "nginxconfig"
        nginxconfig.mkdir()
        (nginxconfig / "security.conf").write_text("original")
        nginx_conf = tmp_path / "nginx.conf"
        nginx_conf.write_text("orig-main")

        cv = ConfigVerification()
        backup_path = cv.backup_configuration(
            backup_dir=str(tmp_path / "backups"),
            nginxconfig_dir=str(nginxconfig),
            nginx_conf_path=str(nginx_conf),
        )
        assert isinstance(backup_path, str)

        # Simulate a bad change that we want to roll back.
        (nginxconfig / "security.conf").write_text("changed")
        nginx_conf.write_text("changed-main")

        assert cv.restore_configuration(
            backup_path,
            nginx_conf_path=str(nginx_conf),
            nginxconfig_dir=str(nginxconfig),
        )

        assert (nginxconfig / "security.conf").read_text() == "original"
        assert nginx_conf.read_text() == "orig-main"

    def test_restore_refuses_symlinked_target_dir(self, tmp_path):
        """restore_configuration must refuse to write over a symlinked target dir."""
        backup = tmp_path / "backup"
        (backup / "nginxconfig.io").mkdir(parents=True)
        (backup / "nginxconfig.io" / "security.conf").write_text("x")

        real_dir = tmp_path / "real"
        real_dir.mkdir()
        symlinked_target = tmp_path / "target"
        symlinked_target.symlink_to(real_dir)

        cv = ConfigVerification()
        assert (
            cv.restore_configuration(
                str(backup),
                nginx_conf_path=str(tmp_path / "nonexistent.conf"),
                nginxconfig_dir=str(symlinked_target),
            )
            is False
        )
