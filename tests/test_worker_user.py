"""
Tests for the host-specific nginx worker user.

The embedded nginx.conf follows the nginx.org package and runs its workers as
``nginx``. Debian's and Ubuntu's own nginx package creates no such user and
runs as ``www-data`` instead; writing ``user nginx;`` there makes ``nginx -t``
fail with ``getpwnam("nginx") failed`` and the pre-flight rolls back on every
deploy (seen on Debian 13).
"""

import hashlib
from unittest.mock import patch

from nginx_set_conf.config_verification import NGINX_CONF_TEMPLATE, ConfigVerification, adapt_worker_user


def _getpwnam_for(*existing):
    def fake(name):
        if name in existing:
            return object()
        raise KeyError(name)

    return fake


class TestAdaptWorkerUser:
    def test_keeps_nginx_when_it_exists(self):
        with patch("nginx_set_conf.config_verification.pwd.getpwnam", _getpwnam_for("nginx", "www-data")):
            assert adapt_worker_user(NGINX_CONF_TEMPLATE) == NGINX_CONF_TEMPLATE

    def test_switches_to_www_data_on_debian_package(self):
        with patch("nginx_set_conf.config_verification.pwd.getpwnam", _getpwnam_for("www-data")):
            adapted = adapt_worker_user(NGINX_CONF_TEMPLATE)
        assert "user  www-data;" in adapted
        assert "user  nginx;" not in adapted
        # Nothing but the user line changes.
        assert adapted.replace("user  www-data;", "user  nginx;") == NGINX_CONF_TEMPLATE

    def test_keeps_template_when_neither_user_exists(self):
        """No guessing: nginx -t then names the missing user and the
        classifier tells the operator how to create it."""
        with patch("nginx_set_conf.config_verification.pwd.getpwnam", _getpwnam_for()):
            assert adapt_worker_user(NGINX_CONF_TEMPLATE) == NGINX_CONF_TEMPLATE


class TestVerifyUsesHostTemplate:
    def test_hash_matches_adapted_template(self):
        """After a repair on a www-data host, verify must report consistent —
        otherwise the pre-flight rewrites nginx.conf on every deploy."""
        cv = ConfigVerification()
        with patch("nginx_set_conf.config_verification.pwd.getpwnam", _getpwnam_for("www-data")):
            expected = hashlib.sha256(adapt_worker_user(NGINX_CONF_TEMPLATE).encode("utf-8")).hexdigest()
            assert cv.get_template_hash("nginx.conf") == expected

    def test_sync_writes_adapted_template(self, tmp_path):
        target = tmp_path / "nginx.conf"
        cv = ConfigVerification()
        results = {"nginx.conf": {"server": {"path": str(target)}}}
        with patch("nginx_set_conf.config_verification.pwd.getpwnam", _getpwnam_for("www-data")):
            assert cv._perform_sync(results, ["nginx.conf"])
        assert "user  www-data;" in target.read_text(encoding="utf-8")


class TestClassifyMissingUser:
    def test_getpwnam_failure_is_named(self):
        output = 'nginx: [emerg] getpwnam("nginx") failed in /etc/nginx/nginx.conf:3'
        cause, remedy = ConfigVerification._classify_nginx_error(output)
        assert "nginx" in cause
        assert "useradd" in remedy
