"""
Tests for carrying host-specific ``load_module`` lines through a config sync.

Dynamic modules (njs, brotli, geoip2, ...) are installed per host, so the
embedded nginx.conf template cannot know about them. Overwriting the server
file without them makes every vhost using that module's directives fail
``nginx -t`` — and with the pre-flight in place, that failure used to block
every deploy on the affected host.
"""

from pathlib import Path

from nginx_set_conf.config_verification import ConfigVerification

NJS = "load_module modules/ngx_http_js_module.so;"
BROTLI = "load_module modules/ngx_http_brotli_filter_module.so;"
TEMPLATE = "# nginx.conf\nuser nginx;\nevents { }\n"


class TestPreserveLoadModules:
    def test_carries_over_module_from_server_file(self, tmp_path: Path):
        server = tmp_path / "nginx.conf"
        server.write_text(f"{NJS}\nuser nginx;\n", encoding="utf-8")
        result = ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server)
        assert NJS in result
        assert result.endswith(TEMPLATE)

    def test_carries_over_several_modules(self, tmp_path: Path):
        server = tmp_path / "nginx.conf"
        server.write_text(f"{NJS}\n{BROTLI}\nuser nginx;\n", encoding="utf-8")
        result = ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server)
        assert NJS in result and BROTLI in result

    def test_is_idempotent(self, tmp_path: Path):
        """A second sync must not stack the same line up again."""
        server = tmp_path / "nginx.conf"
        server.write_text(f"{NJS}\nuser nginx;\n", encoding="utf-8")
        once = ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server)
        server.write_text(once, encoding="utf-8")
        twice = ConfigVerification._preserve_load_modules("nginx.conf", once, server)
        assert twice.count(NJS) == 1

    def test_template_without_modules_is_unchanged(self, tmp_path: Path):
        server = tmp_path / "nginx.conf"
        server.write_text("user nginx;\n", encoding="utf-8")
        assert ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server) == TEMPLATE

    def test_missing_server_file_is_unchanged(self, tmp_path: Path):
        server = tmp_path / "absent.conf"
        assert ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server) == TEMPLATE

    def test_only_applies_to_nginx_conf(self, tmp_path: Path):
        """load_module is a main-context directive; it must never be prepended
        to an include file, where it would be a syntax error."""
        server = tmp_path / "security.conf"
        server.write_text(f"{NJS}\n", encoding="utf-8")
        result = ConfigVerification._preserve_load_modules(
            "nginxconfig.io/security.conf", TEMPLATE, server
        )
        assert result == TEMPLATE

    def test_indented_and_quoted_forms_are_matched(self, tmp_path: Path):
        server = tmp_path / "nginx.conf"
        server.write_text('  load_module "modules/ngx_http_js_module.so";\n', encoding="utf-8")
        result = ConfigVerification._preserve_load_modules("nginx.conf", TEMPLATE, server)
        assert "ngx_http_js_module.so" in result
