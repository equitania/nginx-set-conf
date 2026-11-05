"""Tests for the wordpress template and per-vhost rate-limit zone names."""

import re

import pytest

from nginx_set_conf.templates.all_templates import TEMPLATES
from nginx_set_conf.utils import execute_commands


def _render(tmp_path, domain="www.example.com", **overrides):
    kwargs = {
        "config_template": "wordpress",
        "domain": domain,
        "ip": "192.0.2.10",
        "cert_name": domain,
        "cert_key": "/etc/ssl/test.key",  # own cert pair: no certbot run
        "port": "8180",
        "pollport": "",
        "redirect_domain": "",
        "auth_file": "",
        "allowed_ips": "",
        "target_path": str(tmp_path),
        "dry_run": False,
    }
    kwargs.update(overrides)
    assert execute_commands(**kwargs) is True
    return (tmp_path / f"{domain}.conf").read_text()


class TestWordpressTemplate:
    def test_ip_bound_listens_only(self):
        listens = [ln.strip() for ln in TEMPLATES["wordpress"].splitlines() if ln.strip().startswith("listen ")]
        assert listens == ["listen ip.ip.ip.ip:80;", "listen ip.ip.ip.ip:443 ssl;"]

    def test_includes_shared_security_and_general_conf(self):
        content = TEMPLATES["wordpress"]
        assert "include                 nginxconfig.io/security.conf;" in content
        assert "include                 nginxconfig.io/general.conf;" in content

    def test_no_add_header_that_would_drop_security_headers(self):
        # Any add_header in the template would cancel the inherited headers of
        # security.conf for that block.
        active = [ln for ln in TEMPLATES["wordpress"].splitlines() if not ln.strip().startswith("#")]
        assert not any("add_header" in ln for ln in active)

    def test_no_ssl_stapling_or_own_upstream(self):
        content = TEMPLATES["wordpress"]
        assert "ssl_stapling" not in content
        assert not re.search(r"^\s*upstream\s", content, re.M)

    def test_connection_upgrade_map_matches_other_templates(self):
        # The map is http-level: a different value here would change it for
        # every vhost on the server.
        assert "map $http_upgrade $connection_upgrade {\n  default upgrade;\n  '' close;\n}" in TEMPLATES["wordpress"]
        assert "map $http_upgrade $connection_upgrade {\n  default upgrade;\n  '' close;\n}" in TEMPLATES["odoo_ssl"]

    def test_rate_limit_keyed_on_client_address_only(self):
        zones = re.findall(r"limit_req_zone (\S+) zone=", TEMPLATES["wordpress"])
        assert zones == ["$binary_remote_addr", "$binary_remote_addr"]

    def test_rendered_config(self, tmp_path):
        content = _render(tmp_path)
        assert "server_name www.example.com;" in content
        assert "listen 192.0.2.10:443 ssl;" in content
        assert "proxy_pass http://127.0.0.1:8180;" in content
        assert "ssl_certificate_key /etc/ssl/test.key;" in content
        for placeholder in ("{{", "server.domain.de", "ip.ip.ip.ip", "zertifikat."):
            assert placeholder not in content

    def test_rendered_blocks_and_mcp_location(self, tmp_path):
        content = _render(tmp_path)
        assert "location = /xmlrpc.php {\n        return 403;" in content
        assert r"location ~* ^/wp-content/uploads/.*\.(?:php|phar|phtml)$" in content
        mcp = content.split("location ^~ /wp-json/mcp/ {", 1)[1].split("}", 1)[0]
        assert "proxy_buffering off;" in mcp
        assert "proxy_read_timeout 300s;" in mcp
        assert "auth_basic off;" in mcp

    def test_basic_auth_is_server_wide(self, tmp_path):
        content = _render(tmp_path, auth_file="/etc/nginx/.htpasswd")
        server_443 = content.split("listen 192.0.2.10:443 ssl;", 1)[1]
        auth_pos = server_443.index("auth_basic_user_file  /etc/nginx/.htpasswd;")
        assert auth_pos < server_443.index("\n    location ")
        assert content.count("auth_basic       ") == 1

    def test_http3_injected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("nginx_set_conf.utils.get_nginx_version", lambda: (1, 27, 0))
        content = _render(tmp_path, enable_http3=True)
        assert "listen 192.0.2.10:443 quic" in content
        assert "http3 on;" in content


class TestRateLimitZoneNames:
    def test_two_zones_get_distinct_per_vhost_names(self, tmp_path):
        content = _render(tmp_path)
        declared = re.findall(r"limit_req_zone \S+ zone=([^:]+):", content)
        assert declared == ["wordpress_www_example_com_wplogin", "wordpress_www_example_com_wpmcp"]
        used = re.findall(r"limit_req zone=(\S+)", content)
        assert used == declared

    @pytest.mark.parametrize("domain", ["www.example.com", "blog.example.com"])
    def test_two_wordpress_vhosts_do_not_share_zones(self, tmp_path, domain):
        content = _render(tmp_path, domain=domain)
        assert f"wordpress_{domain.replace('.', '_')}_wplogin" in content

    def test_classic_iprl_zone_keeps_historic_name(self, tmp_path):
        execute_commands(
            config_template="odoo_ssl",
            domain="erp.example.com",
            ip="192.0.2.10",
            cert_name="erp.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=str(tmp_path),
            dry_run=False,
        )
        content = (tmp_path / "erp.example.com.conf").read_text()
        assert "zone=odoo_ssl_erp_example_com_ratelimit:16m" in content


class TestMcpAllowedIps:
    def test_restriction_lands_inside_mcp_location_only(self, tmp_path):
        content = _render(tmp_path, mcp_allowed_ips="192.0.2.20, 198.51.100.0/24")
        mcp = content.split("location ^~ /wp-json/mcp/ {", 1)[1].split("}", 1)[0]
        assert "        allow 192.0.2.20;\n        allow 198.51.100.0/24;\n        deny all;" in mcp
        assert content.count("deny all;") == 1

    def test_combines_with_site_wide_allowlist(self, tmp_path):
        content = _render(tmp_path, allowed_ips="203.0.113.0/24", mcp_allowed_ips="192.0.2.20")
        assert "    allow 203.0.113.0/24;" in content
        assert "        allow 192.0.2.20;" in content

    def test_invalid_entry_skips_vhost(self, tmp_path):
        kwargs = {
            "config_template": "wordpress",
            "domain": "www.example.com",
            "ip": "192.0.2.10",
            "cert_name": "www.example.com",
            "cert_key": "/etc/ssl/test.key",
            "port": "8180",
            "pollport": "",
            "redirect_domain": "",
            "auth_file": "",
            "allowed_ips": "",
            "target_path": str(tmp_path),
            "dry_run": False,
            "mcp_allowed_ips": "all;\n    include /etc/passwd;\n    #",
        }
        assert execute_commands(**kwargs) is False
        assert list(tmp_path.glob("*.conf")) == []

    def test_rejected_for_template_without_mcp_endpoint(self, tmp_path):
        result = execute_commands(
            config_template="odoo_ssl",
            domain="erp.example.com",
            ip="192.0.2.10",
            cert_name="erp.example.com",
            cert_key="/etc/ssl/test.key",
            port="8069",
            pollport="8072",
            redirect_domain="",
            auth_file="",
            allowed_ips="",
            target_path=str(tmp_path),
            dry_run=False,
            mcp_allowed_ips="192.0.2.20",
        )
        assert result is False
        assert list(tmp_path.glob("*.conf")) == []

    def test_wizard_asks_only_for_wordpress(self):
        from nginx_set_conf.wizard import template_fields

        assert template_fields("wordpress").mcp_allowed_ips is True
        assert template_fields("odoo_ssl").mcp_allowed_ips is False
