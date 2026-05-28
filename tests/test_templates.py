"""Tests for template loading and cache path replacement."""

from nginx_set_conf.config_templates import get_config_template
from nginx_set_conf.config_verification import NGINX_CONF_TEMPLATE
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
            "default_ssl_reject",
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
                    # ip.ip.ip.ip is reserved for listen directives only (v1.11.0+);
                    # proxy_pass/grpc_pass must use {{BACKEND_IP}}.
                    assert "ip.ip.ip.ip" not in stripped, f"Template '{name}' has ip.ip.ip.ip in: {stripped}"

    def test_ip_placeholder_restricted_to_listen(self):
        """v1.11.0: ip.ip.ip.ip must only appear in `listen` directives.

        Before v1.11.0, templates bound the listen socket to the hostname
        (`listen server.domain.de:443 ssl;`), which forced nginx to resolve
        the hostname at config-parse time and aborted startup on transient
        DNS failures. v1.11.0 rewrites this to `listen ip.ip.ip.ip:443 ssl;`
        — the placeholder is substituted with the --ip value (IPv6 wrapped
        in brackets) by execute_commands. It must not leak into any other
        directive, especially not proxy_pass (checked separately above).
        """
        for name, content in TEMPLATES.items():
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#") or "ip.ip.ip.ip" not in stripped:
                    continue
                assert stripped.startswith("listen "), (
                    f"Template '{name}' uses ip.ip.ip.ip outside a listen directive: {stripped}"
                )

    def test_default_ssl_reject_not_in_proxy_list(self):
        """default_ssl_reject must NOT be treated as a proxy template.

        It has no backend to proxy to — it exists specifically to close
        connections with unknown SNI/Host. It therefore must not be in the
        proxy_templates list used by test_all_proxy_templates_use_backend_ip_placeholder.
        """
        content = TEMPLATES["default_ssl_reject"]
        assert "{{BACKEND_IP}}" not in content
        assert "proxy_pass" not in content


class TestIpBoundListen:
    """v1.11.0 regression tests for IP-bound listen directives.

    All service templates (everything except default_ssl_reject, which
    intentionally uses wildcard listens with default_server) must emit
    `listen ip.ip.ip.ip:PORT[ ssl];`. Hostname-bound listens (v1.9.x
    default) are forbidden because they make nginx fail to start on
    transient DNS issues; wildcard listens without default_server leak
    certificates via SNI fallback (see v1.10.2 RELEASE_NOTES).
    """

    SERVICE_TEMPLATES = [
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

    def test_all_service_templates_use_ip_bound_listen_80(self):
        for name in self.SERVICE_TEMPLATES:
            content = TEMPLATES[name]
            assert "listen ip.ip.ip.ip:80;" in content, f"Template '{name}' missing `listen ip.ip.ip.ip:80;`"

    def test_ssl_templates_use_ip_bound_listen_443(self):
        ssl_templates = [t for t in self.SERVICE_TEMPLATES if t not in ("odoo_http", "redirect")]
        for name in ssl_templates:
            content = TEMPLATES[name]
            assert "listen ip.ip.ip.ip:443 ssl;" in content, f"Template '{name}' missing `listen ip.ip.ip.ip:443 ssl;`"

    def test_no_hostname_bound_listen(self):
        for name in self.SERVICE_TEMPLATES:
            content = TEMPLATES[name]
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("listen "):
                    assert "server.domain.de" not in stripped, (
                        f"Template '{name}' still has hostname-bound listen: {stripped}"
                    )

    def test_server_name_still_uses_domain_placeholder(self):
        """server_name must still reference server.domain.de (that's how SNI
        matching works). Only the listen binding changed; name-based vhost
        routing is unaffected."""
        for name in self.SERVICE_TEMPLATES:
            content = TEMPLATES[name]
            assert "server_name server.domain.de;" in content, f"Template '{name}' lost its server_name placeholder"


class TestDefaultSslReject:
    """v1.10.2 tests for the default_ssl_reject catch-all block.

    Background: without an explicit default_server on port 443, nginx falls
    back to the first loaded server block for unmatched SNI. This caused the
    wrong certificate to be presented in production on 2026-04-21
    (equitania.de served the designer.odoo2fast.report cert). This template
    closes such connections with HTTP 444 before any data is exchanged.
    """

    TEMPLATE_NAME = "default_ssl_reject"

    def test_template_registered(self):
        assert self.TEMPLATE_NAME in TEMPLATES
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert content
        assert len(content) > 100

    def test_declares_default_server_on_80_and_443(self):
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert "listen 80 default_server;" in content
        assert "listen 443 ssl default_server;" in content

    def test_ipv6_default_server_present(self):
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert "listen [::]:80 default_server;" in content
        assert "listen [::]:443 ssl default_server;" in content

    def test_returns_444_to_close_connection(self):
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert content.count("return 444;") >= 2

    def test_uses_wildcard_server_name(self):
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert "server_name _;" in content

    def test_ssl_cert_paths_reference_default_pair(self):
        content = TEMPLATES[self.TEMPLATE_NAME]
        assert "/etc/nginx/ssl/default.crt" in content
        assert "/etc/nginx/ssl/default.key" in content


class TestHttp2Enabled:
    """Regression guard: NGINX_CONF_TEMPLATE must carry `http2 on;` inside the http{} block.

    Option B (single source of truth at http{} scope) means the directive lives
    in NGINX_CONF_TEMPLATE only. All SSL service templates inherit HTTP/2 via
    the base config. Future changes that drop the directive will fail these tests
    before reaching production.
    """

    def test_nginx_conf_template_has_http2_directive(self):
        assert "http2" in NGINX_CONF_TEMPLATE and "on;" in NGINX_CONF_TEMPLATE, (
            "NGINX_CONF_TEMPLATE missing http2 on; directive — run --sync_config to propagate to operator nginx.conf"
        )
        # Accept any whitespace between http2 and on; (alignment-padded variant)
        import re
        assert re.search(r'http2\s+on;', NGINX_CONF_TEMPLATE), (
            "NGINX_CONF_TEMPLATE missing http2 on; directive — run --sync_config to propagate to operator nginx.conf"
        )

    def test_http2_directive_is_in_http_scope(self):
        http_block_start = NGINX_CONF_TEMPLATE.index("http {")
        http_block = NGINX_CONF_TEMPLATE[http_block_start : NGINX_CONF_TEMPLATE.rfind("}")]
        import re
        assert re.search(r'http2\s+on;', http_block), (
            "http2 on; found in template but not inside the http {} block — check scope"
        )
