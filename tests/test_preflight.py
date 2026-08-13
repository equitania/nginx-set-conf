"""
Tests for the pre-flight base-config check (preflight_check_and_repair).

The pre-flight runs before every real vhost deploy and brings the three
managed base configs (nginx.conf, general.conf, security.conf) back in line
with the embedded templates — fixing e.g. an Odoo-breaking CSP in security.conf
that lacks 'unsafe-eval'. These tests mock the underlying building blocks
(verify/backup/sync/restore and nginx -t) to assert the orchestration logic.
"""

from unittest.mock import patch

from nginx_set_conf.config_verification import ConfigVerification


def _results(drift: bool):
    """Synthetic verify_configuration_consistency() result."""
    return {
        "nginx.conf": {"needs_update": False},
        "nginxconfig.io/general.conf": {"needs_update": False},
        "nginxconfig.io/security.conf": {"needs_update": drift},
    }


class TestPreflightCheckAndRepair:
    def test_no_drift_is_noop(self):
        """Consistent base configs: no backup, no sync, returns True."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(False)),
            patch.object(cv, "backup_configuration") as mock_backup,
            patch.object(cv, "_perform_sync") as mock_sync,
        ):
            assert cv.preflight_check_and_repair() is True
        mock_backup.assert_not_called()
        mock_sync.assert_not_called()

    def test_drift_repaired_and_validated(self):
        """Drift + backup + sync + nginx -t ok: returns True, no rollback."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True) as mock_sync,
            patch.object(cv, "restore_configuration") as mock_restore,
            patch.object(cv, "_nginx_test", return_value=(True, "")),
        ):
            assert cv.preflight_check_and_repair() is True
        mock_sync.assert_called_once()
        mock_restore.assert_not_called()

    def test_drift_only_syncs_divergent_files(self):
        """_perform_sync must receive exactly the divergent file names."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True) as mock_sync,
            patch.object(cv, "_nginx_test", return_value=(True, "")),
        ):
            cv.preflight_check_and_repair()
        _, divergent = mock_sync.call_args.args
        assert divergent == ["nginxconfig.io/security.conf"]

    def test_repair_breaks_config_but_rollback_is_valid_continues(self):
        """The host is simply not on this version's templates.

        nginx -t fails with the templates applied, but the rolled-back config
        validates on its own — that is a server whose base config is newer or
        locally extended (e.g. an extra load_module), not a broken one. It must
        stay deployable, otherwise this gate locks out every host ahead of the
        package.
        """
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "restore_configuration", return_value=True) as mock_restore,
            patch.object(cv, "_nginx_test", side_effect=[(False, 'unknown directive "js_periodic"'),
                                                         (True, "syntax is ok")]),
        ):
            assert cv.preflight_check_and_repair() is True
        mock_restore.assert_called_once_with("/var/backups/x")

    def test_config_broken_after_rollback_aborts(self):
        """Invalid even after the rollback: the fault predates the repair."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "restore_configuration", return_value=True) as mock_restore,
            patch.object(cv, "_nginx_test", return_value=(False, "host not found in upstream")),
        ):
            assert cv.preflight_check_and_repair() is False
        mock_restore.assert_called_once_with("/var/backups/x")

    def test_unbindable_listen_address_continues_with_a_diagnosis(self, capsys):
        """The 13.08.2026 case: a customer's DNS change, not a base-config fault.

        Aborting here would block the very deploy that rewrites hostname-bound
        listens into IP-bound ones — the repair for exactly this situation.
        """
        emerg = ("nginx: [emerg] bind() to 94.130.186.22:443 failed "
                 "(99: Cannot assign requested address)")
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "restore_configuration", return_value=True),
            patch.object(cv, "_nginx_test", return_value=(False, emerg)),
        ):
            assert cv.preflight_check_and_repair() is True
        out = capsys.readouterr().out
        assert "94.130.186.22" in out
        assert "not an address of this host" in out
        assert "nginx-cert-guard.py" in out

    def test_genuine_base_config_error_still_aborts(self):
        """Classification must not become a blanket 'continue anyway'."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "restore_configuration", return_value=True),
            patch.object(cv, "_nginx_test",
                         return_value=(False, 'nginx: [emerg] unknown directive "blah"')),
        ):
            assert cv.preflight_check_and_repair() is False

    def test_nginx_test_output_is_shown(self, capsys):
        """The nginx -t message must reach the operator, not just logger.debug."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "restore_configuration", return_value=True),
            patch.object(cv, "_nginx_test", side_effect=[(False, 'unknown directive "js_periodic"'),
                                                         (True, "syntax is ok")]),
        ):
            cv.preflight_check_and_repair()
        assert "js_periodic" in capsys.readouterr().out

    def test_backup_failure_aborts_without_sync(self):
        """Backup fails: no sync attempted, returns False."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value=None),
            patch.object(cv, "_perform_sync") as mock_sync,
        ):
            assert cv.preflight_check_and_repair() is False
        mock_sync.assert_not_called()

    def test_sync_failure_rolls_back(self):
        """Resync fails: restore from backup, returns False."""
        cv = ConfigVerification()
        with (
            patch.object(cv, "verify_configuration_consistency", return_value=_results(True)),
            patch.object(cv, "backup_configuration", return_value="/var/backups/x"),
            patch.object(cv, "_perform_sync", return_value=False),
            patch.object(cv, "restore_configuration", return_value=True) as mock_restore,
        ):
            assert cv.preflight_check_and_repair() is False
        mock_restore.assert_called_once_with("/var/backups/x")
