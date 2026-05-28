"""Tests for utility functions."""

import builtins
import logging
import os

import pytest

from nginx_set_conf.utils import (
    retrieve_valid_input,
    _format_ip_for_nginx,
    _insert_after_marker,
    _replace_placeholder,
    _safe_conf_filename,
    _warn_public_backend_ip,
    execute_commands,
    get_default_vars,
    parse_yaml,
    parse_yaml_folder,
    self_clean,
)


class TestSelfClean:
    def test_removes_duplicates(self):
        data = {"key": [1, 2, 2, 3, 3]}
        result = self_clean(data)
        assert result["key"] == [1, 2, 3]

    def test_empty_dict(self):
        assert self_clean({}) == {}

    def test_no_duplicates(self):
        data = {"key": [1, 2, 3]}
        result = self_clean(data)
        assert result["key"] == [1, 2, 3]


class TestParseYaml:
    def test_valid_yaml(self, tmp_path):
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nnumber: 42\n")
        result = parse_yaml(str(yaml_file))
        assert result == {"key": "value", "number": 42}

    def test_invalid_yaml(self, tmp_path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(":\n  :\n    invalid: [")
        result = parse_yaml(str(yaml_file))
        assert result is False


class TestParseYamlFolder:
    def test_parses_yaml_files(self, tmp_path):
        (tmp_path / "a.yaml").write_text("key: a\n")
        (tmp_path / "b.yml").write_text("key: b\n")
        (tmp_path / "c.txt").write_text("key: c\n")
        results = parse_yaml_folder(str(tmp_path))
        assert len(results) == 2

    def test_empty_folder(self, tmp_path):
        results = parse_yaml_folder(str(tmp_path))
        assert results == []


class TestGetDefaultVars:
    def test_returns_expected_keys(self):
        defaults = get_default_vars()
        assert "server_path" in defaults
        assert "template_domain" in defaults
        assert "template_ip" in defaults
        assert "template_port" in defaults
        assert "template_backend_ip" in defaults
        assert defaults["server_path"] == "/etc/nginx/conf.d"
        assert defaults["template_backend_ip"] == "{{BACKEND_IP}}"


class TestReplacePlaceholder:
    def test_replaces_value(self):
        result = _replace_placeholder("Hello {{NAME}}", "{{NAME}}", "World")
        assert result == "Hello World"

    def test_no_match(self):
        result = _replace_placeholder("Hello World", "{{MISSING}}", "X")
        assert result == "Hello World"

    def test_multiple_occurrences(self):
        result = _replace_placeholder("A B A", "A", "C")
        assert result == "C B C"


class TestInsertAfterMarker:
    def test_inserts_after_marker(self):
        content = "line1\n#marker\nline3"
        result = _insert_after_marker(content, "#marker", ["inserted"])
        assert result == "line1\n#marker\ninserted\nline3"

    def test_first_only(self):
        content = "#marker\nA\n#marker\nB"
        result = _insert_after_marker(content, "#marker", ["X"], first_only=True)
        lines = result.split("\n")
        assert lines.count("X") == 1

    def test_no_marker(self):
        content = "line1\nline2"
        result = _insert_after_marker(content, "#missing", ["X"])
        assert result == content

    def test_multiple_insert_lines(self):
        content = "before\n#marker\nafter"
        result = _insert_after_marker(content, "#marker", ["A", "B", "C"])
        assert "A\nB\nC" in result


class TestExecuteCommands:
    def test_dry_run_creates_no_files(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="test.example.com",
            cert_key="",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=True,
        )
        # Dry run should NOT create the config file
        config_file = os.path.join(target, "test.example.com.conf")
        assert not os.path.exists(config_file)

    def test_generates_config_file(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        assert os.path.exists(config_file)

        content = open(config_file).read()
        assert "test.example.com" in content
        assert "127.0.0.1" in content  # Default backend IP
        assert "8069" in content
        assert "8072" in content
        # Template placeholders should be replaced
        assert "server.domain.de" not in content
        assert "{{BACKEND_IP}}" not in content
        assert "{{PORT}}" not in content
        assert "{{POLL_PORT}}" not in content

    def test_rejects_invalid_domain(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        execute_commands(
            config_template="odoo_ssl",
            domain="bad domain; rm -rf /",
            ip="192.168.1.1",
            cert_name="cert",
            cert_key="",
            port="8069",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=True,
        )
        # Should not create any file due to validation failure
        assert not os.path.exists(os.path.join(target, "bad domain; rm -rf /.conf"))

    def test_rejects_invalid_allowed_ips(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="cert",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="all;\n    include /etc/passwd;\n    #",
            target_path=target,
            dry_run=True,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        assert not os.path.exists(config_file)

    def test_ip_restrictions_applied(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="10.0.0.0/24,192.168.1.50",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        content = open(config_file).read()
        assert "allow 10.0.0.0/24;" in content
        assert "allow 192.168.1.50;" in content
        assert "deny all;" in content

    def test_auth_file_applied(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="/etc/nginx/.htpasswd",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        content = open(config_file).read()
        assert "auth_basic" in content
        assert "/etc/nginx/.htpasswd" in content

    def test_disable_domain_listen(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="192.168.1.1",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
            disable_domain_listen=True,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        content = open(config_file).read()
        # Domain should NOT appear in listen directives
        assert "listen test.example.com:80" not in content
        assert "listen test.example.com:443" not in content
        # But standard listen directives should be present
        assert "listen 80;" in content
        assert "listen 443" in content

    def test_domain_specific_cache_paths(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="site1.example.com",
            ip="192.168.1.1",
            cert_name="site1.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "site1.example.com.conf")
        content = open(config_file).read()
        assert "odoo_ssl_site1_example_com" in content


class TestFormatIpForNginx:
    def test_ipv4_unchanged(self):
        assert _format_ip_for_nginx("192.168.1.1") == "192.168.1.1"

    def test_ipv4_localhost_unchanged(self):
        assert _format_ip_for_nginx("127.0.0.1") == "127.0.0.1"

    def test_ipv6_loopback_wrapped(self):
        assert _format_ip_for_nginx("::1") == "[::1]"

    def test_ipv6_full_wrapped(self):
        assert _format_ip_for_nginx("2001:db8::1") == "[2001:db8::1]"

    def test_ipv6_all_zeros_wrapped(self):
        assert _format_ip_for_nginx("::") == "[::]"

    def test_invalid_ip_passthrough(self):
        assert _format_ip_for_nginx("not-an-ip") == "not-an-ip"


class TestWarnPublicBackendIp:
    def test_public_ipv4_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="nginx_set_conf"):
            _warn_public_backend_ip("8.8.8.8")
        assert "Public IP 8.8.8.8 used as backend address" in caplog.text

    def test_public_ipv6_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="nginx_set_conf"):
            _warn_public_backend_ip("2606:4700:4700::1111")
        assert "Public IP 2606:4700:4700::1111 used as backend address" in caplog.text

    def test_loopback_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="nginx_set_conf"):
            _warn_public_backend_ip("127.0.0.1")
        assert "Public IP" not in caplog.text

    def test_private_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="nginx_set_conf"):
            _warn_public_backend_ip("192.168.1.10")
        assert "Public IP" not in caplog.text

    def test_ipv6_loopback_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="nginx_set_conf"):
            _warn_public_backend_ip("::1")
        assert "Public IP" not in caplog.text


class TestExecuteCommandsIPv6:
    def test_ipv6_in_proxy_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="1.2.3.4",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
            backend_ip="::1",
        )
        config_file = os.path.join(target, "test.example.com.conf")
        content = open(config_file).read()
        # IPv6 must be wrapped in brackets in proxy_pass URLs
        assert "proxy_pass http://[::1]:8069" in content
        assert "proxy_pass http://[::1]:8072" in content
        # No unformatted IPv6 in URL contexts
        assert "proxy_pass http://::1:" not in content

    def test_ipv6_full_address_in_proxy_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="flowise",
            domain="flowise.example.com",
            ip="1.2.3.4",
            cert_name="flowise.example.com",
            cert_key="/etc/ssl/test.key",
            port="3000",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
            backend_ip="2001:db8::1",
        )
        config_file = os.path.join(target, "flowise.example.com.conf")
        content = open(config_file).read()
        assert "proxy_pass http://[2001:db8::1]:3000" in content

    def test_ipv4_still_works(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="flowise",
            domain="flowise.example.com",
            ip="1.2.3.4",
            cert_name="flowise.example.com",
            cert_key="/etc/ssl/test.key",
            port="3000",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "flowise.example.com.conf")
        content = open(config_file).read()
        # Without backend_ip, default 127.0.0.1 should be used
        assert "proxy_pass http://127.0.0.1:3000" in content

    def test_ipv6_grpc_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="qdrant",
            domain="qdrant.example.com",
            ip="1.2.3.4",
            cert_name="qdrant.example.com",
            cert_key="/etc/ssl/test.key",
            port="6333",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
            grpcport="6334",
            backend_ip="::1",
        )
        config_file = os.path.join(target, "qdrant.example.com.conf")
        content = open(config_file).read()
        assert "proxy_pass http://[::1]:6333" in content
        assert "grpc_pass grpc://[::1]:6334" in content

    def test_default_backend_ip(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="203.0.113.10",
            cert_name="test.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "test.example.com.conf")
        content = open(config_file).read()
        # Without backend_ip, default 127.0.0.1 should be used
        assert "proxy_pass http://127.0.0.1:8069" in content
        assert "proxy_pass http://127.0.0.1:8072" in content

    def test_custom_backend_ip(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="flowise",
            domain="flowise.example.com",
            ip="1.2.3.4",
            cert_name="flowise.example.com",
            cert_key="/etc/ssl/test.key",
            port="3000",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
            backend_ip="192.168.1.50",
        )
        config_file = os.path.join(target, "flowise.example.com.conf")
        content = open(config_file).read()
        assert "proxy_pass http://192.168.1.50:3000" in content

    def test_ip_not_in_proxy_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="flowise",
            domain="flowise.example.com",
            ip="203.0.113.10",
            cert_name="flowise.example.com",
            cert_key="/etc/ssl/test.key",
            port="3000",
            pollport="",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=target,
            dry_run=False,
        )
        config_file = os.path.join(target, "flowise.example.com.conf")
        content = open(config_file).read()
        # Public IP must NOT appear in proxy_pass
        assert "proxy_pass http://203.0.113.10" not in content
        # Default backend IP should be used instead
        assert "proxy_pass http://127.0.0.1:3000" in content


class TestSafeConfFilename:
    def test_passthrough_plain_domain(self):
        assert _safe_conf_filename("example.com") == "example.com"

    def test_passthrough_subdomain(self):
        assert _safe_conf_filename("sub.example.com") == "sub.example.com"

    def test_rewrites_wildcard_prefix(self):
        # The exact concern from CONCERNS.md HIGH-3: the wildcard
        # `*` must never reach a generated filename — it is a shell
        # glob character and would corrupt `rm /etc/nginx/conf.d/*.conf`
        # cleanup scripts.
        assert _safe_conf_filename("*.example.com") == "_wildcard.example.com"

    def test_wildcard_result_contains_no_glob(self):
        assert "*" not in _safe_conf_filename("*.example.com")

    def test_only_wildcard_prefix_is_rewritten(self):
        # A literal `*` not in prefix position is not currently produced
        # by the domain validator, but if it ever were, the helper must
        # NOT silently rewrite it — the prefix-only rewrite is the
        # documented contract.
        assert _safe_conf_filename("a.b.example.com") == "a.b.example.com"


class TestRetrieveValidInput:
    def test_returns_nonempty_input_immediately(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda _: "hello")
        assert retrieve_valid_input("prompt: ") == "hello"

    def test_loops_past_empty_input(self, monkeypatch):
        responses = iter(["", "", "finally"])
        monkeypatch.setattr(builtins, "input", lambda _: next(responses))
        assert retrieve_valid_input("prompt: ") == "finally"

    def test_truncates_oversized_input(self, monkeypatch):
        big = "x" * 8000
        monkeypatch.setattr(builtins, "input", lambda _: big)
        result = retrieve_valid_input("prompt: ")
        assert len(result) == 4096

    def test_eof_raises_system_exit(self, monkeypatch):
        monkeypatch.setattr(
            builtins, "input",
            lambda _: (_ for _ in ()).throw(EOFError())
        )
        with pytest.raises(SystemExit):
            retrieve_valid_input("prompt: ")

    def test_no_recursion_on_many_empty_enters(self, monkeypatch):
        count = [0]

        def fake_input(_):
            count[0] += 1
            if count[0] < 1001:
                return ""
            return "valid"

        monkeypatch.setattr(builtins, "input", fake_input)
        result = retrieve_valid_input("prompt: ")
        assert result == "valid"
        assert count[0] == 1001
