"""Tests for template loading and cache path replacement."""

from nginx_set_conf.config_templates import get_config_template
from nginx_set_conf.templates.all_templates import (
    TEMPLATES,
    replace_cache_path,
)
from nginx_set_conf.templates.all_templates import (
    get_config_template as all_get_config_template,
)


class TestTemplateRegistry:
    def test_all_templates_loaded(self):
        expected = {
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
        }
        assert set(TEMPLATES.keys()) == expected

    def test_all_templates_non_empty(self):
        for name, content in TEMPLATES.items():
            assert content, f"Template {name} is empty"
            assert len(content) > 100, f"Template {name} seems too short"

    def test_unknown_template_returns_empty(self):
        result = get_config_template("nonexistent_template")
        assert result == ""

    def test_backward_compat_ngx_prefix(self):
        result = get_config_template("ngx_odoo_ssl")
        assert result != ""
        assert "server" in result


class TestCachePathReplacement:
    def test_replaces_cache_path(self):
        template = "proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m"
        result = replace_cache_path(template, "test_service")
        assert "/var/cache/nginx/test_service" in result
        assert "/tmp" not in result

    def test_domain_specific_cache(self):
        template = "proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m"
        result = replace_cache_path(template, "odoo_ssl", "example.com")
        assert "odoo_ssl_example_com" in result

    def test_zone_name_replaced(self):
        template = "proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m"
        result = replace_cache_path(template, "test")
        assert "keys_zone=test_cache:" in result

    def test_limit_req_zone_replaced(self):
        template = "limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m rate=500r/m;"
        result = replace_cache_path(template, "test")
        assert "zone=test_limit:" in result
        assert "16m" in result
        assert "500r/m" in result

    def test_limit_req_directive_replaced(self):
        template = "limit_req zone=iprl burst=500 nodelay;"
        result = replace_cache_path(template, "test")
        assert "zone=test_limit" in result


class TestGetConfigTemplate:
    def test_get_odoo_ssl(self):
        result = get_config_template("odoo_ssl")
        assert result
        assert "ssl" in result.lower()

    def test_get_with_domain(self):
        result = all_get_config_template("odoo_ssl", "mysite.com")
        assert result
        # Template is returned (domain-specific path replacement is
        # handled by execute_commands in utils.py via regex, not here)
        assert len(result) > 100

    def test_templates_contain_placeholders(self):
        for name in ["odoo_ssl", "flowise", "n8n", "qdrant"]:
            result = get_config_template(name)
            assert "server.domain.de" in result or "{{BACKEND_IP}}" in result, (
                f"Template {name} missing expected placeholders"
            )


class TestTemplateBackendIpPlaceholder:
    """Regression test: templates should use {{BACKEND_IP}} placeholder in proxy_pass/grpc_pass."""

    def test_all_proxy_templates_use_backend_ip_placeholder(self):
        proxy_templates = [
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
            "supabase",
        ]
        for name in proxy_templates:
            content = TEMPLATES[name]
            assert "{{BACKEND_IP}}" in content, f"Template '{name}' missing {{{{BACKEND_IP}}}} placeholder"

    def test_no_hardcoded_ip_in_proxy_pass(self):
        for name, content in TEMPLATES.items():
            # Check that proxy_pass/grpc_pass lines do not contain hardcoded IPs
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "proxy_pass" in stripped or "grpc_pass" in stripped:
                    assert "127.0.0.1" not in stripped, f"Template '{name}' has hardcoded 127.0.0.1 in: {stripped}"
                    # ip.ip.ip.ip should not be in active proxy_pass
                    assert "ip.ip.ip.ip" not in stripped, f"Template '{name}' has ip.ip.ip.ip in: {stripped}"

    def test_no_ip_placeholder_anywhere(self):
        """Ensure ip.ip.ip.ip is completely removed from all templates (including comments)."""
        for name, content in TEMPLATES.items():
            assert "ip.ip.ip.ip" not in content, f"Template '{name}' still contains 'ip.ip.ip.ip'"
