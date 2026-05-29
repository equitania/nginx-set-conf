"""
Tests for the removal of the deprecated config_templates.py shim.

Phase 03-01: These tests document the intended post-removal state:
  - nginx_set_conf.config_templates must NOT be importable (ModuleNotFoundError)
  - nginx_set_conf.nginx_set_conf must still import successfully
  - get_config_template from all_templates returns correct results
"""

import importlib

import pytest


class TestConfigTemplatesRemoved:
    """Verify that the deprecated config_templates.py shim has been deleted."""

    def test_config_templates_module_not_importable(self):
        """After deletion, importing nginx_set_conf.config_templates must raise ModuleNotFoundError."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("nginx_set_conf.config_templates")

    def test_nginx_set_conf_module_imports_successfully(self):
        """nginx_set_conf.nginx_set_conf must still import without error after the shim is removed."""
        # This must not raise; the import now resolves via all_templates directly
        import nginx_set_conf.nginx_set_conf  # noqa: F401

    def test_get_config_template_callable_from_all_templates(self):
        """get_config_template imported from all_templates must be callable and return results."""
        from nginx_set_conf.templates.all_templates import get_config_template

        result = get_config_template("odoo_ssl")
        assert result != "", "get_config_template('odoo_ssl') must return a non-empty string"
        assert "server" in result, "odoo_ssl template must contain 'server'"

    def test_get_config_template_unknown_returns_empty(self):
        """get_config_template must return empty string for unknown template names."""
        from nginx_set_conf.templates.all_templates import get_config_template

        result = get_config_template("nonexistent")
        assert result == "", "get_config_template with unknown name must return empty string"
