"""Tests for the subcommand CLI and the flag-only legacy call form."""

from unittest.mock import patch

from click.testing import CliRunner

from nginx_set_conf import __version__
from nginx_set_conf import nginx_set_conf as cli
from nginx_set_conf.templates.all_templates import TEMPLATE_DESCRIPTIONS, TEMPLATES


def _invoke(*args):
    return CliRunner().invoke(cli.start_nginx_set_conf, list(args))


class TestOverviewHelp:
    def test_help_lists_commands_in_registration_order(self):
        result = _invoke("--help")
        assert result.exit_code == 0
        commands = result.output.split("Commands:")[1]
        positions = [commands.index(name) for name in ("deploy", "show", "templates", "verify", "sync", "backup")]
        assert positions == sorted(positions)

    def test_standard_call_is_on_one_line(self):
        """The call operators copy between servers must not be wrapped."""
        result = _invoke("--help")
        assert any(line.strip() == cli.STANDARD_CALL for line in result.output.splitlines())

    def test_no_arguments_shows_overview_not_interactive_prompt(self):
        with patch.object(cli, "_run_deploy") as deploy:
            result = _invoke()
        assert result.exit_code == 0
        assert "Commands:" in result.output
        deploy.assert_not_called()

    def test_legacy_command_is_hidden(self):
        assert "legacy" not in _invoke("--help").output

    def test_version(self):
        result = _invoke("--version")
        assert result.exit_code == 0
        assert __version__ in result.output


class TestDeployHelp:
    def test_options_are_grouped_in_sections(self):
        result = _invoke("deploy", "--help")
        assert result.exit_code == 0
        for title in cli.DEPLOY_SECTIONS:
            assert f"{title}:" in result.output

    def test_every_deploy_option_is_in_a_section(self):
        placed = {name for names in cli.DEPLOY_SECTIONS.values() for name in names}
        params = {p.name for p in cli.deploy_command.params}
        assert params == placed


class TestSubcommands:
    def test_deploy_passes_config_path(self):
        with patch.object(cli, "_run_deploy") as deploy:
            result = _invoke("deploy", "--config_path=/srv/ngx-conf", "--dry_run")
        assert result.exit_code == 0
        kwargs = deploy.call_args.kwargs
        assert kwargs["config_path"] == "/srv/ngx-conf"
        assert kwargs["dry_run"] is True

    def test_show_known_template(self):
        result = _invoke("show", "odoo_ssl")
        assert result.exit_code == 0
        assert TEMPLATES["odoo_ssl"] in result.output

    def test_show_unknown_template_fails(self):
        result = _invoke("show", "nope")
        assert result.exit_code == 1
        assert "Unknown template 'nope'" in result.output

    def test_templates_lists_every_registered_template(self):
        result = _invoke("templates")
        assert result.exit_code == 0
        for name in TEMPLATES:
            assert name in result.output

    def test_sync_passes_force(self):
        with patch.object(cli, "_run_verify", return_value=True) as verify:
            result = _invoke("sync", "--force")
        assert result.exit_code == 0
        verify.assert_called_once_with(sync=True, force=True)

    def test_failed_action_sets_exit_code(self):
        with patch.object(cli, "_run_backup", return_value=False):
            assert _invoke("backup").exit_code == 1

    def test_migrate_passes_target_and_dry_run(self):
        with patch.object(cli, "_run_migrate", return_value=True) as migrate:
            result = _invoke("migrate", "--target_path=/tmp/conf.d", "--dry_run")
        assert result.exit_code == 0
        migrate.assert_called_once_with("/tmp/conf.d", True)


class TestLegacyCallForm:
    """The flag-only form of versions before 1.19 must keep working unchanged."""

    def test_config_path_routes_to_deploy(self):
        with patch.object(cli, "_run_deploy") as deploy:
            result = _invoke("--config_path=/root/docker-builds/ngx-conf")
        assert result.exit_code == 0
        assert deploy.call_args.kwargs["config_path"] == "/root/docker-builds/ngx-conf"

    def test_sync_config_force(self):
        with patch.object(cli, "_run_verify") as verify:
            result = _invoke("--sync_config", "--force")
        assert result.exit_code == 0
        verify.assert_called_once_with(sync=True, force=True)

    def test_verify_config(self):
        with patch.object(cli, "_run_verify") as verify:
            _invoke("--verify_config")
        verify.assert_called_once_with(sync=False, force=False)

    def test_backup_wins_over_verify(self):
        with patch.object(cli, "_run_backup") as backup, patch.object(cli, "_run_verify") as verify:
            _invoke("--verify_config", "--backup_config")
        backup.assert_called_once()
        verify.assert_not_called()

    def test_migrate_wins_over_everything(self):
        with patch.object(cli, "_run_migrate") as migrate, patch.object(cli, "_run_setup_default") as setup:
            _invoke("--setup_default", "--migrate_to_wildcard", "--dry_run")
        migrate.assert_called_once_with(None, True)
        setup.assert_not_called()

    def test_show_template(self):
        result = _invoke("--show_template", "--config_template", "odoo_ssl")
        assert result.exit_code == 0
        assert TEMPLATES["odoo_ssl"] in result.output


def test_every_template_has_a_description():
    assert set(TEMPLATE_DESCRIPTIONS) == set(TEMPLATES)
