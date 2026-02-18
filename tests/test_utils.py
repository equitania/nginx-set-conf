"""Tests for utility functions."""

import os

from nginx_set_conf.utils import (
    _format_ip_for_nginx,
    _insert_after_marker,
    _replace_placeholder,
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
        assert defaults["server_path"] == "/etc/nginx/conf.d"


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
        assert "192.168.1.1" in content
        assert "8069" in content
        assert "8072" in content
        # Template placeholders should be replaced
        assert "server.domain.de" not in content
        assert "ip.ip.ip.ip" not in content
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


class TestExecuteCommandsIPv6:
    def test_ipv6_in_proxy_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="odoo_ssl",
            domain="test.example.com",
            ip="::1",
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
            ip="2001:db8::1",
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
        assert "proxy_pass http://[2001:db8::1]:3000" in content

    def test_ipv4_still_works(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="flowise",
            domain="flowise.example.com",
            ip="192.168.1.10",
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
        assert "proxy_pass http://192.168.1.10:3000" in content

    def test_ipv6_grpc_pass(self, tmp_path):
        target = str(tmp_path / "nginx_conf")
        os.makedirs(target, exist_ok=True)
        execute_commands(
            config_template="qdrant",
            domain="qdrant.example.com",
            ip="::1",
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
        )
        config_file = os.path.join(target, "qdrant.example.com.conf")
        content = open(config_file).read()
        assert "proxy_pass http://[::1]:6333" in content
        assert "grpc_pass grpc://[::1]:6334" in content
