"""Tests for the deploy orchestration in ``_run_deploy``.

The deploy path decides when nginx is started, tested and reloaded. Every
system call is replaced by a recorder, so the tests check the order of the
service commands and how YAML entries reach ``execute_commands`` without
touching a real nginx.
"""

import subprocess

import click
import pytest

from nginx_set_conf import nginx_set_conf as cli


def _deploy_params(**overrides):
    params = {
        "config_template": "odoo_ssl",
        "ip": "1.2.3.4",
        "domain": "example.com",
        "port": "8069",
        "cert_name": "example.com",
        "cert_key": "",
        "pollport": "8072",
        "grpcport": "",
        "redirect_domain": "",
        "auth_file": "",
        "allowed_ips": "",
        "backend_ip": None,
        "root_path": None,
        "disable_domain_listen": False,
        "enable_http3": False,
        "config_path": None,
        "target_path": "/etc/nginx/conf.d",
        "dry_run": False,
    }
    params.update(overrides)
    return params


class _Recorder:
    """Stands in for the system: service commands, pre-flight, vhost writes."""

    def __init__(self, monkeypatch, preflight_ok=True, nginx_test_rc=0, failing_domains=()):
        self.service_calls = []
        self.deployed = []
        self.failing_domains = set(failing_domains)
        self.preflight_ok = preflight_ok
        self.nginx_test_rc = nginx_test_rc
        monkeypatch.setattr(cli, "_run_service_command", self._service)
        monkeypatch.setattr(cli, "execute_commands", self._execute)
        recorder = self

        class _FakeVerification:
            def preflight_check_and_repair(self):
                recorder.service_calls.append("preflight")
                return recorder.preflight_ok

        monkeypatch.setattr(cli, "ConfigVerification", _FakeVerification)

    def _service(self, args, dry_run=False):
        self.service_calls.append(" ".join(args))
        rc = self.nginx_test_rc if args == ["nginx", "-t"] else 0
        return subprocess.CompletedProcess(args, rc)

    def _execute(self, config_template, domain, ip, *args, **kwargs):
        self.service_calls.append(f"deploy {domain}")
        self.deployed.append({"config_template": config_template, "domain": domain, "ip": ip, "args": args, **kwargs})
        # Like the real execute_commands: an empty domain fails validation.
        return bool(domain) and domain not in self.failing_domains


class TestDeployOrder:
    def test_full_sequence(self, monkeypatch):
        rec = _Recorder(monkeypatch)
        cli._run_deploy(**_deploy_params())
        assert rec.service_calls == [
            "systemctl start nginx.service",
            "preflight",
            "deploy example.com",
            "nginx -t",
            "systemctl reload-or-restart nginx.service",
            "systemctl status nginx.service",
            "nginx -V",
        ]

    def test_final_step_starts_a_stopped_nginx(self, monkeypatch):
        # 1.19.5: certbot --standalone stops nginx; a plain `reload` is refused
        # by systemd on a stopped unit and left every vhost offline.
        rec = _Recorder(monkeypatch)
        cli._run_deploy(**_deploy_params())
        assert "systemctl reload nginx.service" not in rec.service_calls
        assert "systemctl restart nginx.service" not in rec.service_calls
        assert "systemctl reload-or-restart nginx.service" in rec.service_calls

    def test_failed_preflight_aborts_before_any_vhost(self, monkeypatch):
        rec = _Recorder(monkeypatch, preflight_ok=False)
        with pytest.raises(click.ClickException, match="Pre-flight"):
            cli._run_deploy(**_deploy_params())
        assert rec.deployed == []
        assert rec.service_calls == ["systemctl start nginx.service", "preflight"]

    def test_failed_nginx_test_refuses_reload(self, monkeypatch):
        rec = _Recorder(monkeypatch, nginx_test_rc=1)
        with pytest.raises(click.ClickException, match="refusing to reload"):
            cli._run_deploy(**_deploy_params())
        assert rec.service_calls[-1] == "nginx -t"
        assert not any("reload" in call for call in rec.service_calls)

    def test_dry_run_touches_no_service(self, monkeypatch):
        rec = _Recorder(monkeypatch)
        cli._run_deploy(**_deploy_params(dry_run=True))
        assert rec.service_calls == ["deploy example.com"]


class TestYamlBatch:
    def _write_yaml(self, tmp_path, text):
        (tmp_path / "vhosts.yaml").write_text(text, encoding="utf-8")
        return str(tmp_path)

    def test_numbers_and_empty_keys_become_text(self, monkeypatch, tmp_path):
        rec = _Recorder(monkeypatch)
        config_path = self._write_yaml(
            tmp_path,
            "site:\n"
            "  config_template: odoo_ssl\n"
            "  ip: 1.2.3.4\n"
            "  domain: example.com\n"
            "  port: 8069\n"
            "  cert_name: 12345\n"
            "  cert_key:\n",
        )
        cli._run_deploy(**_deploy_params(config_path=config_path))
        (entry,) = rec.deployed
        cert_name, cert_key, port = entry["args"][:3]
        assert (cert_name, cert_key, port) == ("12345", "", "8069")
        # An empty key must not become the string "None".
        assert "None" not in [a for a in entry["args"] if isinstance(a, str)]

    def test_entry_without_domain_does_not_abort_the_batch(self, monkeypatch, tmp_path):
        rec = _Recorder(monkeypatch)
        config_path = self._write_yaml(
            tmp_path,
            "broken:\n"
            "  config_template: odoo_ssl\n"
            "  ip: 1.2.3.4\n"
            "good:\n"
            "  config_template: odoo_ssl\n"
            "  ip: 1.2.3.4\n"
            "  domain: example.com\n"
            "  port: 8069\n"
            "  cert_name: example.com\n",
        )
        with pytest.raises(click.ClickException, match=r"1 vhost\(s\) skipped: broken \(no domain\)"):
            cli._run_deploy(**_deploy_params(config_path=config_path))
        assert [e["domain"] for e in rec.deployed] == ["", "example.com"]
        # The good vhost still goes live before the run reports the failure.
        assert rec.service_calls[-3:] == [
            "systemctl reload-or-restart nginx.service",
            "systemctl status nginx.service",
            "nginx -V",
        ]

    def _flag_yaml(self, tmp_path, value):
        return self._write_yaml(
            tmp_path,
            "site:\n"
            "  config_template: odoo_ssl\n"
            "  ip: 1.2.3.4\n"
            "  domain: example.com\n"
            "  port: 8069\n"
            "  cert_name: example.com\n"
            f"  enable_http3: {value}\n"
            f"  disable_domain_listen: {value}\n",
        )

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ('"false"', False),
            ("'False'", False),
            ('"no"', False),
            ('""', False),
            ("false", False),
            ("0", False),
            ('"true"', True),
            ("yes", True),
            ("true", True),
            ("1", True),
        ],
    )
    def test_quoted_flag_words(self, monkeypatch, tmp_path, value, expected):
        rec = _Recorder(monkeypatch)
        cli._run_deploy(**_deploy_params(config_path=self._flag_yaml(tmp_path, value)))
        (entry,) = rec.deployed
        assert entry["enable_http3"] is expected
        assert entry["args"][-1] is expected  # disable_domain_listen, positional

    def test_unknown_flag_word_skips_the_entry(self, monkeypatch, tmp_path, capsys):
        rec = _Recorder(monkeypatch)
        with pytest.raises(click.ClickException, match="skipped: site"):
            cli._run_deploy(**_deploy_params(config_path=self._flag_yaml(tmp_path, '"maybe"')))
        assert rec.deployed == []
        assert "'disable_domain_listen' must be true or false" in capsys.readouterr().out


class TestExitCode:
    """A skipped vhost must reach the shell as exit code 1 — in both call forms."""

    def test_single_call_skip_raises_after_reload(self, monkeypatch):
        rec = _Recorder(monkeypatch, failing_domains={"example.com"})
        with pytest.raises(click.ClickException, match="skipped: example.com"):
            cli._run_deploy(**_deploy_params())
        assert "systemctl reload-or-restart nginx.service" in rec.service_calls

    def test_dry_run_skip_raises_too(self, monkeypatch):
        _Recorder(monkeypatch, failing_domains={"example.com"})
        with pytest.raises(click.ClickException, match="skipped"):
            cli._run_deploy(**_deploy_params(dry_run=True))

    @pytest.mark.parametrize("form", ["legacy", "subcommand"])
    def test_cli_exit_code(self, monkeypatch, form):
        from click.testing import CliRunner

        _Recorder(monkeypatch, failing_domains={"example.com"})
        args = [
            "--config_template=odoo_ssl",
            "--ip=1.2.3.4",
            "--domain=example.com",
            "--port=8069",
            "--cert_name=example.com",
        ]
        if form == "subcommand":
            args = ["deploy", *args]
        result = CliRunner().invoke(cli.start_nginx_set_conf, args)
        assert result.exit_code == 1, result.output
        assert "skipped: example.com" in result.output

    def test_cli_exit_code_zero_when_all_written(self, monkeypatch):
        from click.testing import CliRunner

        _Recorder(monkeypatch)
        result = CliRunner().invoke(
            cli.start_nginx_set_conf,
            [
                "--config_template=odoo_ssl",
                "--ip=1.2.3.4",
                "--domain=example.com",
                "--port=8069",
                "--cert_name=example.com",
            ],
        )
        assert result.exit_code == 0, result.output


class TestBadEntryIsSkipped:
    """execute_commands itself must skip an invalid entry, not raise."""

    @pytest.mark.parametrize(
        "overrides",
        [
            {"domain": ""},
            {"domain": "example.com\n"},
            {"cert_name": 12345},
            {"port": "1_0"},
        ],
    )
    def test_invalid_entry_writes_nothing(self, tmp_path, overrides, capsys):
        from nginx_set_conf.utils import execute_commands

        values = {
            "config_template": "odoo_ssl",
            "domain": "example.com",
            "ip": "1.2.3.4",
            "cert_name": "example.com",
            "cert_key": "",
            "port": "8069",
            "pollport": "8072",
            "redirect_domain": "",
            "auth_file": "",
            "allowed_ips": "",
            "target_path": str(tmp_path),
            "dry_run": False,
        }
        values.update(overrides)
        assert execute_commands(**values) is False
        assert list(tmp_path.iterdir()) == []
        assert "ERROR:" in capsys.readouterr().out
