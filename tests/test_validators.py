"""Tests for input validation module."""

import pytest

from nginx_set_conf.validators import (
    ValidationError,
    validate_all_inputs,
    validate_allowed_ips,
    validate_auth_file,
    validate_cert_key,
    validate_cert_name,
    validate_config_template,
    validate_domain,
    validate_ip,
    validate_port,
    validate_target_path,
)


class TestValidateDomain:
    def test_valid_domain(self):
        assert validate_domain("example.com") == "example.com"

    def test_valid_subdomain(self):
        assert validate_domain("sub.example.com") == "sub.example.com"

    def test_valid_deep_subdomain(self):
        assert validate_domain("a.b.c.example.com") == "a.b.c.example.com"

    def test_valid_wildcard(self):
        assert validate_domain("*.example.com") == "*.example.com"

    def test_valid_hyphen(self):
        assert validate_domain("my-site.example.com") == "my-site.example.com"

    def test_empty_domain(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_domain("")

    def test_domain_too_long(self):
        long_domain = "a" * 254 + ".com"
        with pytest.raises(ValidationError, match="too long"):
            validate_domain(long_domain)

    def test_domain_with_shell_injection(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("example.com; rm -rf /")

    def test_domain_with_spaces(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("example .com")

    def test_domain_with_backtick(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("example.com`whoami`")

    def test_domain_with_pipe(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("example.com|cat /etc/passwd")


class TestValidateIp:
    def test_valid_ipv4(self):
        assert validate_ip("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_localhost(self):
        assert validate_ip("127.0.0.1") == "127.0.0.1"

    def test_valid_ipv6(self):
        assert validate_ip("::1") == "::1"

    def test_valid_ipv6_full(self):
        assert validate_ip("2001:db8::1") == "2001:db8::1"

    def test_empty_ip(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_ip("")

    def test_invalid_ip(self):
        with pytest.raises(ValidationError, match="Invalid IP"):
            validate_ip("999.999.999.999")

    def test_ip_with_injection(self):
        with pytest.raises(ValidationError, match="Invalid IP"):
            validate_ip("127.0.0.1; rm -rf /")

    def test_ip_with_cidr(self):
        with pytest.raises(ValidationError, match="Invalid IP"):
            validate_ip("192.168.1.0/24")


class TestValidatePort:
    def test_valid_port(self):
        assert validate_port("8080") == "8080"

    def test_valid_port_min(self):
        assert validate_port("1") == "1"

    def test_valid_port_max(self):
        assert validate_port("65535") == "65535"

    def test_empty_port(self):
        assert validate_port("") == ""

    def test_port_zero(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_port("0")

    def test_port_too_high(self):
        with pytest.raises(ValidationError, match="out of range"):
            validate_port("65536")

    def test_port_not_a_number(self):
        with pytest.raises(ValidationError, match="Must be a number"):
            validate_port("abc")

    def test_port_with_injection(self):
        with pytest.raises(ValidationError, match="Must be a number"):
            validate_port("8080; rm -rf /")


class TestValidateAllowedIps:
    def test_single_ip(self):
        assert validate_allowed_ips("192.168.1.1") == "192.168.1.1"

    def test_cidr_block(self):
        assert validate_allowed_ips("192.168.1.0/24") == "192.168.1.0/24"

    def test_multiple_ips(self):
        result = validate_allowed_ips("192.168.1.1,10.0.0.0/8")
        assert result == "192.168.1.1,10.0.0.0/8"

    def test_empty(self):
        assert validate_allowed_ips("") == ""

    def test_invalid_ip(self):
        with pytest.raises(ValidationError, match="Invalid IP/CIDR"):
            validate_allowed_ips("999.999.999.999")

    def test_injection_attempt(self):
        with pytest.raises(ValidationError, match="Invalid IP/CIDR"):
            validate_allowed_ips("all;\n    include /etc/passwd;\n    #")

    def test_nginx_directive_injection(self):
        with pytest.raises(ValidationError, match="Invalid IP/CIDR"):
            validate_allowed_ips("192.168.1.1,all; deny")

    def test_ipv6_cidr(self):
        assert validate_allowed_ips("2001:db8::/32") == "2001:db8::/32"

    def test_ipv6_single(self):
        assert validate_allowed_ips("::1") == "::1"

    def test_mixed_ipv4_ipv6(self):
        result = validate_allowed_ips("192.168.1.0/24,2001:db8::/32")
        assert result == "192.168.1.0/24,2001:db8::/32"

    def test_mixed_ipv4_ipv6_with_single(self):
        result = validate_allowed_ips("10.0.0.1,::1,192.168.1.0/24")
        assert result == "10.0.0.1,::1,192.168.1.0/24"


class TestValidateTargetPath:
    def test_empty_path(self):
        assert validate_target_path("") == ""

    def test_valid_absolute_path(self):
        result = validate_target_path("/etc/nginx/conf.d")
        # On macOS /etc resolves to /private/etc
        assert result.endswith("/etc/nginx/conf.d")

    def test_path_traversal(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_target_path("/etc/nginx/../../../etc/shadow")

    def test_valid_tmp_path(self):
        result = validate_target_path("/tmp/nginx_test")
        assert "/tmp/nginx_test" in result


class TestValidateCertName:
    def test_valid_cert_name(self):
        assert validate_cert_name("example.com") == "example.com"

    def test_valid_cert_path(self):
        result = validate_cert_name("/etc/ssl/certs/my-cert.crt")
        assert result == "/etc/ssl/certs/my-cert.crt"

    def test_empty(self):
        assert validate_cert_name("") == ""

    def test_injection(self):
        with pytest.raises(ValidationError, match="Invalid certificate"):
            validate_cert_name("cert.pem; rm -rf /")

    def test_path_traversal(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_cert_name("../../etc/shadow")

    def test_path_traversal_absolute(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_cert_name("/etc/ssl/../../../etc/shadow")


class TestValidateCertKey:
    def test_valid_cert_key(self):
        assert validate_cert_key("/etc/ssl/private/my-key.key") == "/etc/ssl/private/my-key.key"

    def test_empty(self):
        assert validate_cert_key("") == ""

    def test_injection(self):
        with pytest.raises(ValidationError, match="Invalid certificate key"):
            validate_cert_key("key.pem; rm -rf /")

    def test_path_traversal(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_cert_key("../../etc/shadow")


class TestValidateAuthFile:
    def test_valid_auth_file(self):
        assert validate_auth_file("/etc/nginx/.htpasswd") == "/etc/nginx/.htpasswd"

    def test_empty(self):
        assert validate_auth_file("") == ""

    def test_injection(self):
        with pytest.raises(ValidationError, match="Invalid auth file"):
            validate_auth_file("/etc/passwd; cat /etc/shadow")

    def test_path_traversal(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_auth_file("../../etc/shadow")

    def test_path_traversal_mixed(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_auth_file("/etc/nginx/../../etc/shadow")


class TestValidateConfigTemplate:
    def test_valid_template(self):
        assert validate_config_template("odoo_ssl") == "odoo_ssl"

    def test_valid_template_with_prefix(self):
        assert validate_config_template("ngx_odoo_ssl") == "odoo_ssl"

    def test_all_valid_templates(self):
        templates = [
            "code_server",
            "fast_report",
            "flowise",
            "guacamole",
            "kasm",
            "mailpit",
            "n8n",
            "nextcloud",
            "odoo_http",
            "odoo_ssl",
            "pgadmin",
            "portainer",
            "pwa",
            "qdrant",
            "redirect",
            "redirect_ssl",
            "supabase",
        ]
        for t in templates:
            assert validate_config_template(t) == t

    def test_empty(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_config_template("")

    def test_invalid_template(self):
        with pytest.raises(ValidationError, match="Unknown template"):
            validate_config_template("not_a_template")


class TestValidateAllInputs:
    def test_valid_inputs(self):
        validate_all_inputs(
            config_template="odoo_ssl",
            domain="example.com",
            ip="192.168.1.1",
            port="8069",
            cert_name="example.com",
        )

    def test_invalid_domain_rejected(self):
        with pytest.raises(ValidationError):
            validate_all_inputs(
                config_template="odoo_ssl",
                domain="example.com; rm -rf /",
                ip="192.168.1.1",
                port="8069",
            )

    def test_invalid_ip_rejected(self):
        with pytest.raises(ValidationError):
            validate_all_inputs(
                config_template="odoo_ssl",
                domain="example.com",
                ip="not-an-ip",
                port="8069",
            )
