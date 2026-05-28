"""Tests for the service-command helper that orchestrates nginx reloads.

The helper underpins the deploy gate: callers rely on the returned
``CompletedProcess`` to check ``nginx -t`` before running
``systemctl reload``.
"""

import subprocess

from nginx_set_conf.nginx_set_conf import _run_service_command


class TestRunServiceCommand:
    def test_returns_completed_process_on_success(self):
        # `true` always exits 0 — safe on every CI / dev machine.
        result = _run_service_command(["true"])
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0

    def test_returns_completed_process_on_nonzero_exit(self):
        # Caller (deploy gate) MUST be able to see returncode != 0
        # so it can abort before reloading nginx.
        result = _run_service_command(["false"])
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode != 0

    def test_dry_run_returns_none(self):
        assert _run_service_command(["true"], dry_run=True) is None

    def test_missing_binary_returns_none(self):
        assert _run_service_command(["/no/such/binary/exists/xyzzy"]) is None
