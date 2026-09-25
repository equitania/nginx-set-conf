"""Tests for the self-serve `capability-card` command."""

from click.testing import CliRunner

from nginx_set_conf import __version__
from nginx_set_conf import capability_card as card_module
from nginx_set_conf import nginx_set_conf as cli


def _invoke(*args):
    return CliRunner().invoke(cli.start_nginx_set_conf, list(args))


def test_prints_card():
    result = _invoke("capability-card")
    assert result.exit_code == 0
    assert "nginx-set-conf — Agent Capability Card" in result.output


def test_injects_live_version(tmp_path, monkeypatch):
    stale = tmp_path / "AGENT.md"
    stale.write_text("# Card\n\n- **Version:** 0.0.1\n", encoding="utf-8")
    monkeypatch.setattr(card_module, "_find_card", lambda: stale)
    result = _invoke("capability-card")
    assert result.exit_code == 0
    assert f"**Version:** {__version__}" in result.output
    assert "0.0.1" not in result.output


def test_listed_in_help():
    result = _invoke("--help")
    assert "capability-card" in result.output.split("Commands:")[1]


def test_missing_card_fails(monkeypatch):
    monkeypatch.setattr(card_module, "_find_card", lambda: None)
    result = _invoke("capability-card")
    assert result.exit_code == 1
    assert "capability card not found" in result.output
