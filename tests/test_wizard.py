"""Tests for the interactive YAML wizard (nginx-set-conf wizard)."""

from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from nginx_set_conf import nginx_set_conf as cli
from nginx_set_conf import wizard
from nginx_set_conf.utils import parse_yaml_folder
from nginx_set_conf.validators import ValidationError

DEFAULT = object()  # take the prompt's default


class ScriptedPrompter:
    """Answers prompts from a list, in order, and records the questions.

    Text answers run through the prompt's validator, so a script cannot feed
    the wizard a value the real prompt would have refused.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.questions = []

    def _next(self, message):
        self.questions.append(message)
        if not self.answers:
            raise AssertionError(f"No scripted answer left for: {message}")
        answer = self.answers.pop(0)
        if answer is KeyboardInterrupt:
            raise wizard.WizardAborted
        return answer

    def select(self, message, choices, default=None):
        answer = self._next(message)
        answer = default if answer is DEFAULT else answer
        assert answer in [value for _, value in choices], f"{answer!r} not offered for {message}"
        return answer

    def text(self, message, default="", validate=None):
        answer = self._next(message)
        answer = default if answer is DEFAULT else answer
        if validate is not None:
            assert validate(answer) is True, f"{answer!r} rejected for {message}: {validate(answer)}"
        return answer

    def confirm(self, message, default=False):
        answer = self._next(message)
        return default if answer is DEFAULT else answer


@pytest.fixture(autouse=True)
def fixed_ip(monkeypatch):
    monkeypatch.setattr(wizard, "detect_server_ip", lambda: "203.0.113.10")


ODOO_ANSWERS = [
    "odoo_ssl",  # template
    DEFAULT,  # ip
    "erp.example.com",  # domain
    DEFAULT,  # port 11000
    DEFAULT,  # pollport 12000
    "letsencrypt",
    DEFAULT,  # cert name = domain
    False,  # advanced options
]


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class TestTemplateFields:
    def test_odoo_ssl_asks_both_ports_and_certificate(self):
        fields = wizard.template_fields("odoo_ssl")
        assert fields.port and fields.pollport and fields.certificate
        assert not fields.grpcport and not fields.redirect and not fields.root_path
        assert fields.http3

    def test_redirect_has_no_port_and_no_certificate(self):
        fields = wizard.template_fields("redirect")
        assert fields.redirect
        assert not fields.port and not fields.certificate and not fields.backend_ip

    def test_qdrant_asks_grpc_port(self):
        assert wizard.template_fields("qdrant").grpcport

    def test_static_asks_root_path_not_port(self):
        fields = wizard.template_fields("static_ssl")
        assert fields.root_path and not fields.port

    def test_http3_follows_exclusion_list(self):
        assert not wizard.template_fields("odoo_http").http3
        assert not wizard.template_fields("fast_report").http3

    def test_catch_all_is_not_offered(self):
        assert "default_ssl_reject" not in wizard.wizard_templates()

    @pytest.mark.parametrize("name", wizard.wizard_templates())
    def test_every_offered_template_resolves(self, name):
        wizard.template_fields(name)


class TestEntry:
    def test_build_entry_orders_keys_drops_empty_and_converts_ports(self):
        entry = wizard.build_entry(
            {
                "domain": "erp.example.com",
                "config_template": "odoo_ssl",
                "ip": "203.0.113.10",
                "port": "11000",
                "pollport": "12000",
                "cert_name": "erp.example.com",
                "cert_key": "",
                "enable_http3": False,
            }
        )
        assert list(entry) == ["config_template", "ip", "domain", "port", "pollport", "cert_name"]
        assert entry["port"] == 11000

    def test_validate_entry_rejects_redirect_without_target(self):
        with pytest.raises(ValidationError):
            wizard.validate_entry({"config_template": "redirect", "ip": "203.0.113.10", "domain": "a.example.com"})

    def test_validate_entry_rejects_http3_with_wildcard_listen(self):
        entry = wizard.build_entry(
            {
                "config_template": "n8n",
                "ip": "203.0.113.10",
                "domain": "n8n.example.com",
                "port": "5678",
                "cert_name": "n8n.example.com",
                "enable_http3": True,
                "disable_domain_listen": True,
            }
        )
        with pytest.raises(ValidationError):
            wizard.validate_entry(entry)

    def test_wildcard_domain_gets_glob_safe_file_name(self):
        assert wizard.config_filename("*.example.com") == "_wildcard.example.com.yaml"

    def test_written_file_is_read_back_by_the_deploy(self, tmp_path):
        entry = wizard.build_entry(
            {
                "config_template": "odoo_ssl",
                "ip": "203.0.113.10",
                "domain": "erp.example.com",
                "port": "11000",
                "pollport": "12000",
                "cert_name": "erp.example.com",
            }
        )
        path = wizard.write_entry(str(tmp_path), entry)
        assert path == str(tmp_path / "erp.example.com.yaml")
        assert open(path, encoding="utf-8").readline().startswith("# Created by nginx-set-conf")
        assert parse_yaml_folder(str(tmp_path)) == [{"erp.example.com": entry}]

    def test_find_domain_in_folder(self, tmp_path):
        (tmp_path / "old.yaml").write_text("Odoo:\n  config_template: odoo_ssl\n  domain: erp.example.com\n")
        (tmp_path / "other.yaml").write_text("backup:\n  path: /srv\n")
        (tmp_path / "broken.yaml").write_text(": : :\n")
        assert wizard.find_domain_in_folder(str(tmp_path), "erp.example.com") == ["old.yaml"]
        assert wizard.find_domain_in_folder(str(tmp_path / "missing"), "erp.example.com") == []


class TestFlow:
    def test_one_odoo_vhost_saved_and_not_deployed(self, tmp_path):
        deployed = []
        prompter = ScriptedPrompter([*ODOO_ANSWERS, "save", "finish", False])
        written = wizard.run_wizard(str(tmp_path), prompter, deployed.append)

        assert written == [str(tmp_path / "erp.example.com.yaml")]
        assert deployed == []
        assert _load(written[0]) == {
            "erp.example.com": {
                "config_template": "odoo_ssl",
                "ip": "203.0.113.10",
                "domain": "erp.example.com",
                "port": 11000,
                "pollport": 12000,
                "cert_name": "erp.example.com",
            }
        }

    def test_finish_with_confirmation_deploys_only_new_files(self, tmp_path):
        deployed = []
        answers = [
            *ODOO_ANSWERS,
            "save",
            "another",
            "redirect",
            DEFAULT,  # ip from previous vhost
            "old.example.com",
            "erp.example.com",  # redirect target
            False,  # advanced
            "save",
            "finish",
            True,  # deploy
        ]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), deployed.append)

        assert deployed == [written]
        assert [p.rsplit("/", 1)[1] for p in written] == ["erp.example.com.yaml", "old.example.com.yaml"]
        assert _load(written[1])["old.example.com"] == {
            "config_template": "redirect",
            "ip": "203.0.113.10",
            "domain": "old.example.com",
            "redirect_domain": "erp.example.com",
        }

    def test_another_vhost_does_not_inherit_domain_or_certificate(self, tmp_path):
        answers = [
            *ODOO_ANSWERS[:3],
            "8069",  # non-default port for the first vhost
            *ODOO_ANSWERS[4:],
            "save",
            "another",
            DEFAULT,  # template stays odoo_ssl
            "198.51.100.7",  # different IP
            "shop.example.com",
            DEFAULT,  # port: back to the template default, not 8069
            DEFAULT,
            DEFAULT,  # letsencrypt
            DEFAULT,  # cert name: the new domain
            False,
            "save",
            "cancel",
        ]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), lambda files: None)
        entry = _load(written[1])["shop.example.com"]
        assert entry["cert_name"] == "shop.example.com"
        assert entry["port"] == 11000
        assert entry["ip"] == "198.51.100.7"

    def test_only_template_specific_questions_are_asked(self, tmp_path):
        prompter = ScriptedPrompter(
            ["redirect", DEFAULT, "old.example.com", "erp.example.com", False, "save", "cancel"]
        )
        wizard.run_wizard(str(tmp_path), prompter, lambda files: None)
        asked = " ".join(prompter.questions)
        assert "port" not in asked.lower()
        assert "Certificate" not in asked

    def test_discard_writes_nothing(self, tmp_path):
        prompter = ScriptedPrompter([*ODOO_ANSWERS, "discard", "finish"])
        assert wizard.run_wizard(str(tmp_path), prompter, lambda files: None) == []
        assert list(tmp_path.iterdir()) == []

    def test_edit_again_prefills_previous_answers(self, tmp_path):
        answers = [
            *ODOO_ANSWERS,
            "edit",
            DEFAULT,  # template stays odoo_ssl
            DEFAULT,  # ip
            DEFAULT,  # domain stays erp.example.com
            "11001",  # port changed
            DEFAULT,  # pollport
            DEFAULT,  # letsencrypt
            DEFAULT,  # cert name
            False,
            "save",
            "cancel",
        ]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), lambda files: None)
        entry = _load(written[0])["erp.example.com"]
        assert entry["port"] == 11001
        assert entry["pollport"] == 12000

    def test_ctrl_c_keeps_saved_files_and_does_not_deploy(self, tmp_path):
        deployed = []
        answers = [*ODOO_ANSWERS, "save", "another", KeyboardInterrupt]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), deployed.append)
        assert len(written) == 1
        assert deployed == []

    def test_existing_domain_needs_confirmation(self, tmp_path):
        (tmp_path / "erp.example.com.yaml").write_text("x:\n  config_template: odoo_ssl\n  domain: erp.example.com\n")
        answers = [
            "odoo_ssl",
            DEFAULT,
            "erp.example.com",
            False,  # do not overwrite → asked again
            "erp2.example.com",
            *ODOO_ANSWERS[3:],
            "save",
            "cancel",
        ]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), lambda files: None)
        assert written == [str(tmp_path / "erp2.example.com.yaml")]

    def test_own_certificate_and_advanced_options(self, tmp_path):
        answers = [
            "n8n",
            DEFAULT,
            "n8n.example.com",
            DEFAULT,  # 5678
            "own",
            "/etc/ssl/n8n.crt",
            "/etc/ssl/n8n.key",
            True,  # advanced
            DEFAULT,  # backend 127.0.0.1 → left out
            "/etc/nginx/htpasswd",
            "192.168.1.0/24",
            True,  # http3 → wildcard question skipped
            "save",
            "cancel",
        ]
        written = wizard.run_wizard(str(tmp_path), ScriptedPrompter(answers), lambda files: None)
        assert _load(written[0])["n8n.example.com"] == {
            "config_template": "n8n",
            "ip": "203.0.113.10",
            "domain": "n8n.example.com",
            "port": 5678,
            "cert_name": "/etc/ssl/n8n.crt",
            "cert_key": "/etc/ssl/n8n.key",
            "auth_file": "/etc/nginx/htpasswd",
            "allowed_ips": "192.168.1.0/24",
            "enable_http3": True,
        }


class TestDeployFilter:
    def test_parse_yaml_folder_only_files(self, tmp_path):
        (tmp_path / "a.yaml").write_text("a:\n  config_template: n8n\n  domain: a.example.com\n")
        (tmp_path / "b.yaml").write_text("b:\n  config_template: n8n\n  domain: b.example.com\n")
        result = parse_yaml_folder(str(tmp_path), only_files=[str(tmp_path / "b.yaml")])
        assert [list(r) for r in result] == [["b"]]


class TestCommand:
    def test_listed_in_help(self):
        result = CliRunner().invoke(cli.start_nginx_set_conf, ["--help"])
        assert "wizard" in result.output

    def test_refuses_without_terminal(self):
        result = CliRunner().invoke(cli.start_nginx_set_conf, ["wizard"])
        assert result.exit_code == 1
        assert "interactive terminal" in result.output

    def test_deploy_callback_passes_files_and_options(self, tmp_path):
        calls = []

        def fake_run_wizard(folder, prompter, deploy):
            deploy([str(tmp_path / "a.yaml")])

        with (
            patch.object(cli, "_stdin_is_terminal", return_value=True),
            patch.object(cli, "run_wizard", fake_run_wizard),
            patch.object(cli, "_run_deploy", lambda **kw: calls.append(kw)),
        ):
            result = CliRunner().invoke(
                cli.start_nginx_set_conf, ["wizard", "--config_path", str(tmp_path), "--dry_run"]
            )
        assert result.exit_code == 0, result.output
        assert calls[0]["config_path"] == str(tmp_path)
        assert calls[0]["config_files"] == [str(tmp_path / "a.yaml")]
        assert calls[0]["dry_run"] is True
