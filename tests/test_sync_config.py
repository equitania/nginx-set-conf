"""
Tests for Q-02: --force gate on sync_configurations.

Covers:
- Warn-and-abort without --force when server files differ (T-04-01)
- Successful no-op when nothing needs updating
- Proceed path with --force when server files differ
- Warning output emitted with --force
- Abort message emitted without --force
"""

from unittest.mock import patch

import pytest

from nginx_set_conf.config_verification import ConfigVerification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results(*, needs_update: bool, server_exists: bool, file_name: str = "nginx.conf") -> dict:
    """Build a minimal results dict that sync_configurations understands.

    Args:
        needs_update: Whether this file needs to be synced.
        server_exists: Whether the server file already exists on disk.
        file_name: Key to use in the results dict.
    """
    return {
        file_name: {
            "needs_update": needs_update,
            "consistent": not needs_update,
            "server": {
                "exists": server_exists,
                "path": f"/etc/nginx/nginxconfig.io/{file_name}",
            },
            "template": {
                "content": "# template content\n",
                "size": 20,
            },
        }
    }


def _make_all_consistent_results() -> dict:
    """Build a results dict where no file requires updating."""
    result = {}
    for name in ("nginx.conf", "general.conf", "security.conf"):
        result[name] = {
            "needs_update": False,
            "consistent": True,
            "server": {
                "exists": True,
                "path": f"/etc/nginx/nginxconfig.io/{name}",
            },
            "template": {
                "content": "# content\n",
                "size": 10,
            },
        }
    return result


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestSyncConfigForceGate:
    """Q-02 safety gate: --force required to overwrite existing server files."""

    def test_sync_without_force_aborts_when_files_differ(self, monkeypatch):
        """Without --force, sync_configurations must return False and not call _perform_sync."""
        results = _make_results(needs_update=True, server_exists=True)
        cv = ConfigVerification()

        with patch.object(cv, "_perform_sync") as mock_perform_sync:
            return_value = cv.sync_configurations(results, force=False)

        assert return_value is False
        mock_perform_sync.assert_not_called()

    def test_sync_without_force_succeeds_when_nothing_to_update(self):
        """When all files are consistent, sync_configurations returns False (nothing to do).

        The real return value for the empty/nothing-to-update path is False
        (see sync_configurations lines ~336-338): the method echoes
        "All configuration files are already up to date. Nothing to sync."
        and returns False regardless of force.
        """
        results = _make_all_consistent_results()
        cv = ConfigVerification()

        return_value = cv.sync_configurations(results, force=False)

        assert return_value is False

    def test_sync_with_force_calls_perform_sync(self, monkeypatch):
        """With --force and differing files, _perform_sync must be called once."""
        results = _make_results(needs_update=True, server_exists=True)
        cv = ConfigVerification()

        with (
            patch.object(cv, "_perform_sync", return_value=True) as mock_perform_sync,
            patch.object(cv, "backup_configuration", return_value=True),
        ):
            cv.sync_configurations(results, force=True)

        mock_perform_sync.assert_called_once()

    def test_sync_with_force_emits_warning(self, capsys):
        """With --force, the output must warn about operator customisations being overwritten."""
        results = _make_results(needs_update=True, server_exists=True)
        cv = ConfigVerification()

        with (
            patch.object(cv, "_perform_sync", return_value=True),
            patch.object(cv, "backup_configuration", return_value=True),
        ):
            cv.sync_configurations(results, force=True)

        captured = capsys.readouterr()
        output = captured.out

        # Must mention either "customis" (customisation/customizations) or "overwrite"
        assert "customis" in output.lower() or "overwrite" in output.lower(), (
            f"Expected data-loss warning in output. Got:\n{output}"
        )

    def test_sync_without_force_emits_abort_message(self, capsys):
        """Without --force and with differing files, output must reference --force or 'Aborting'."""
        results = _make_results(needs_update=True, server_exists=True)
        cv = ConfigVerification()

        cv.sync_configurations(results, force=False)

        captured = capsys.readouterr()
        output = captured.out

        assert "force" in output.lower() or "aborting" in output.lower(), (
            f"Expected abort message referencing --force or 'Aborting'. Got:\n{output}"
        )
