"""Tests for wildcard-listen migration helpers (v1.10.2)."""

from nginx_set_conf.utils import (
    _rewrite_listen_directives,
    migrate_configs_to_wildcard,
    setup_default_server,
)


class TestRewriteListenDirectives:
    """Regex rewrite: hostname-bound listen → wildcard."""

    def test_rewrites_hostname_port(self):
        new, count = _rewrite_listen_directives("    listen server.domain.de:80;\n")
        assert new == "    listen 80;\n"
        assert count == 1

    def test_rewrites_hostname_port_ssl(self):
        new, count = _rewrite_listen_directives("    listen equitania.de:443 ssl;\n")
        assert new == "    listen 443 ssl;\n"
        assert count == 1

    def test_rewrites_multiple_directives(self):
        src = "server {\n    listen server.domain.de:80;\n}\nserver {\n    listen server.domain.de:443 ssl;\n}\n"
        new, count = _rewrite_listen_directives(src)
        assert count == 2
        assert "listen server.domain.de" not in new
        assert "listen 80;" in new
        assert "listen 443 ssl;" in new

    def test_leaves_wildcard_listen_alone(self):
        src = "    listen 80;\n    listen 443 ssl;\n"
        new, count = _rewrite_listen_directives(src)
        assert count == 0
        assert new == src

    def test_leaves_ipv4_listen_alone(self):
        src = "    listen 127.0.0.1:80;\n    listen 1.2.3.4:443 ssl;\n"
        new, count = _rewrite_listen_directives(src)
        assert count == 0
        assert new == src

    def test_leaves_ipv6_listen_alone(self):
        src = "    listen [::]:80;\n    listen [::1]:443 ssl;\n"
        new, count = _rewrite_listen_directives(src)
        assert count == 0
        assert new == src

    def test_leaves_comments_alone(self):
        src = "# listen server.domain.de:80;\n    listen server.domain.de:443 ssl;\n"
        new, count = _rewrite_listen_directives(src)
        # Only the non-comment line is rewritten; the comment still contains
        # the original text — that is acceptable and matches other tools'
        # behaviour. The count must be 1, not 2.
        assert count == 1
        assert "listen 443 ssl;" in new


class TestMigrateConfigsToWildcard:
    """Integration tests for the atomic migration helper."""

    def test_empty_directory_is_ok(self, tmp_path):
        assert migrate_configs_to_wildcard(str(tmp_path), dry_run=True) is True

    def test_missing_directory_returns_false(self, tmp_path):
        assert migrate_configs_to_wildcard(str(tmp_path / "does-not-exist"), dry_run=True) is False

    def test_dry_run_leaves_files_untouched(self, tmp_path):
        conf = tmp_path / "equitania.de.conf"
        original = "server {\n    listen equitania.de:443 ssl;\n}\n"
        conf.write_text(original)

        assert migrate_configs_to_wildcard(str(tmp_path), dry_run=True) is True
        assert conf.read_text() == original

    def test_nothing_to_migrate(self, tmp_path):
        conf = tmp_path / "already-wildcard.conf"
        original = "server { listen 443 ssl; }\n"
        conf.write_text(original)

        assert migrate_configs_to_wildcard(str(tmp_path), dry_run=True) is True
        assert conf.read_text() == original

    def test_migration_rewrites_file_and_creates_backup(self, tmp_path, monkeypatch):
        """Full path: backup → rewrite → nginx -t → success."""
        conf_dir = tmp_path / "conf.d"
        conf_dir.mkdir()
        conf = conf_dir / "equitania.de.conf"
        conf.write_text("server {\n    listen equitania.de:443 ssl;\n}\n")

        backup_root = tmp_path / "backup"

        # Stub out `nginx -t` via _run_command so tests don't need nginx.
        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)

        ok = migrate_configs_to_wildcard(
            conf_dir=str(conf_dir),
            backup_root=str(backup_root),
            dry_run=False,
        )
        assert ok is True
        assert "listen 443 ssl;" in conf.read_text()
        assert "listen equitania.de:443 ssl;" not in conf.read_text()

        # Backup must exist with the original content
        backups = list(backup_root.glob("migrate_to_wildcard_*"))
        assert len(backups) == 1
        backed_up = (backups[0] / "equitania.de.conf").read_text()
        assert "listen equitania.de:443 ssl;" in backed_up

    def test_nginx_test_failure_rolls_back(self, tmp_path, monkeypatch):
        """If nginx -t fails, migrated files must be restored from backup."""
        conf_dir = tmp_path / "conf.d"
        conf_dir.mkdir()
        conf = conf_dir / "broken.conf"
        original = "server {\n    listen equitania.de:443 ssl;\n}\n"
        conf.write_text(original)

        backup_root = tmp_path / "backup"

        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: False)

        ok = migrate_configs_to_wildcard(
            conf_dir=str(conf_dir),
            backup_root=str(backup_root),
            dry_run=False,
        )
        assert ok is False
        # After rollback the file must be back to the original content
        assert conf.read_text() == original


class TestSetupDefaultServer:
    """Tests for the default_server catch-all installer."""

    def test_dry_run_makes_no_changes(self, tmp_path):
        ssl_dir = tmp_path / "ssl"
        conf_dir = tmp_path / "conf.d"
        ok = setup_default_server(
            target_path=str(conf_dir),
            ssl_dir=str(ssl_dir),
            dry_run=True,
        )
        assert ok is True
        assert not ssl_dir.exists()
        assert not conf_dir.exists()

    def test_writes_conf_and_generates_cert_on_first_run(self, tmp_path, monkeypatch):
        ssl_dir = tmp_path / "ssl"
        conf_dir = tmp_path / "conf.d"
        conf_dir.mkdir()

        calls: list[list[str]] = []

        def fake_run_command(args, *a, **kw):
            calls.append(list(args))
            # Simulate `openssl req` producing the cert and key files.
            if args and args[0] == "openssl":
                keyout = args[args.index("-keyout") + 1]
                certout = args[args.index("-out") + 1]
                with open(keyout, "w") as f:
                    f.write("FAKE KEY")
                with open(certout, "w") as f:
                    f.write("FAKE CERT")
            return True

        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", fake_run_command)

        ok = setup_default_server(
            target_path=str(conf_dir),
            ssl_dir=str(ssl_dir),
            dry_run=False,
        )
        assert ok is True
        assert (ssl_dir / "default.crt").read_text() == "FAKE CERT"
        assert (ssl_dir / "default.key").read_text() == "FAKE KEY"
        installed = (conf_dir / "00-default.conf").read_text()
        assert "default_server" in installed
        assert "return 444;" in installed
        # openssl must have been called at least once
        assert any(c and c[0] == "openssl" for c in calls)

    def test_skips_cert_generation_when_cert_exists(self, tmp_path, monkeypatch):
        ssl_dir = tmp_path / "ssl"
        ssl_dir.mkdir()
        (ssl_dir / "default.crt").write_text("existing")
        (ssl_dir / "default.key").write_text("existing")
        conf_dir = tmp_path / "conf.d"
        conf_dir.mkdir()

        calls: list[list[str]] = []

        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", lambda args, *a, **kw: calls.append(list(args)) or True)

        ok = setup_default_server(
            target_path=str(conf_dir),
            ssl_dir=str(ssl_dir),
            dry_run=False,
        )
        assert ok is True
        # openssl must NOT have been invoked since cert already exists
        assert not any(c and c[0] == "openssl" for c in calls)

    def test_openssl_failure_returns_false(self, tmp_path, monkeypatch):
        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: False)

        ok = setup_default_server(
            target_path=str(tmp_path / "conf.d"),
            ssl_dir=str(tmp_path / "ssl"),
            dry_run=False,
        )
        assert ok is False


class TestMigrateRollbackPaths:
    """Additional coverage for the rollback branches in migration."""

    def test_write_failure_triggers_rollback(self, tmp_path, monkeypatch):
        conf_dir = tmp_path / "conf.d"
        conf_dir.mkdir()
        conf = conf_dir / "will-fail.conf"
        original = "server {\n    listen example.com:443 ssl;\n}\n"
        conf.write_text(original)

        from nginx_set_conf import utils as utils_module

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)

        # Force the write to fail by making the file read-only AFTER backup.
        # Easier: monkey-patch Path.write_text to raise on this path once.
        from pathlib import Path as _Path

        real_write = _Path.write_text
        calls = {"count": 0}

        def failing_write(self, *args, **kwargs):
            if str(self) == str(conf):
                calls["count"] += 1
                raise OSError("simulated disk full")
            return real_write(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "write_text", failing_write)

        ok = migrate_configs_to_wildcard(
            conf_dir=str(conf_dir),
            backup_root=str(tmp_path / "backup"),
            dry_run=False,
        )
        assert ok is False
        # The simulated write failure was raised for the conf file
        assert calls["count"] == 1


class TestDisableDomainListenIntegration:
    """End-to-end test: --disable_domain_listen flag rewrites listen directives.

    Since v1.11.0, templates emit `listen ip.ip.ip.ip:PORT;` by default.
    The --disable_domain_listen flag (name kept for backward compatibility)
    strips the IP prefix, leaving a wildcard `listen PORT;`. This is only
    safe when default_ssl_reject is deployed as 00-default.conf.
    """

    def test_flag_strips_ip_from_listen(self, tmp_path, monkeypatch):
        from nginx_set_conf import utils as utils_module
        from nginx_set_conf.utils import execute_commands

        # Don't actually try to create /var/cache/nginx or call systemctl/certbot
        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)

        execute_commands(
            config_template="odoo_ssl",
            domain="example.com",
            ip="127.0.0.1",
            cert_name="example.com",
            cert_key=None,
            port="8069",
            pollport="8072",
            redirect_domain=None,
            auth_file=None,
            allowed_ips=None,
            target_path=str(tmp_path),
            dry_run=False,
            disable_domain_listen=True,
        )
        generated = (tmp_path / "example.com.conf").read_text()
        # Hostname was never in listen (v1.11.0+), IP prefix must be gone
        assert "listen example.com:" not in generated
        assert "listen 127.0.0.1:" not in generated
        assert "listen 80;" in generated
        assert "listen 443 ssl;" in generated
        # server_name stays intact for SNI routing
        assert "server_name example.com;" in generated

    def test_default_uses_ip_bound_listen(self, tmp_path, monkeypatch):
        from nginx_set_conf import utils as utils_module
        from nginx_set_conf.utils import execute_commands

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)

        execute_commands(
            config_template="odoo_ssl",
            domain="example.com",
            ip="127.0.0.1",
            cert_name="example.com",
            cert_key=None,
            port="8069",
            pollport="8072",
            redirect_domain=None,
            auth_file=None,
            allowed_ips=None,
            target_path=str(tmp_path),
            dry_run=False,
            disable_domain_listen=False,
        )
        generated = (tmp_path / "example.com.conf").read_text()
        # v1.11.0: listen binds to the --ip value, not the hostname
        assert "listen 127.0.0.1:80;" in generated
        assert "listen 127.0.0.1:443 ssl;" in generated
        assert "listen example.com:" not in generated
        # server_name still uses the domain for SNI-based routing
        assert "server_name example.com;" in generated

    def test_ipv6_listen_is_bracketed(self, tmp_path, monkeypatch):
        """IPv6 addresses must be wrapped in square brackets in listen directives.

        nginx syntax requires `listen [2001:db8::1]:443 ssl;` — the same
        bracketing already applied to proxy_pass/grpc_pass by _format_ip_for_nginx.
        """
        from nginx_set_conf import utils as utils_module
        from nginx_set_conf.utils import execute_commands

        monkeypatch.setattr(utils_module, "_run_command", lambda *a, **kw: True)

        execute_commands(
            config_template="odoo_ssl",
            domain="example.com",
            ip="2001:db8::1",
            cert_name="example.com",
            cert_key=None,
            port="8069",
            pollport="8072",
            redirect_domain=None,
            auth_file=None,
            allowed_ips=None,
            target_path=str(tmp_path),
            dry_run=False,
            disable_domain_listen=False,
        )
        generated = (tmp_path / "example.com.conf").read_text()
        assert "listen [2001:db8::1]:80;" in generated
        assert "listen [2001:db8::1]:443 ssl;" in generated
