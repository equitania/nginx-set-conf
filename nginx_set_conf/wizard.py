"""Interactive wizard that writes one YAML vhost file per domain.

The wizard asks only for the values the chosen template actually uses — the
fields are derived from the placeholders in the template itself, so a new
template gets the right questions without touching this module. Every answer
is checked with the same validators the deploy uses, and each vhost is saved
as ``<domain>.yaml`` in the config folder, ready for
``nginx-set-conf --config_path=<folder>``.

All terminal I/O goes through a prompter object (``QuestionaryPrompter`` in
real use), so the flow can be driven by a scripted prompter in tests.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import click
import questionary
import yaml

from . import __version__
from .templates.all_templates import TEMPLATE_DESCRIPTIONS, get_config_template
from .utils import _safe_conf_filename, atomic_write_text
from .validators import (
    HTTP3_EXCLUDED_TEMPLATES,
    VALID_TEMPLATES,
    ValidationError,
    validate_all_inputs,
    validate_allowed_ips,
    validate_auth_file,
    validate_cert_key,
    validate_cert_name,
    validate_domain,
    validate_ip,
    validate_port,
    validate_redirect_domain,
    validate_root_path,
)

DEFAULT_CONFIG_PATH = "/root/docker-builds/ngx-conf"
DEFAULT_BACKEND_IP = "127.0.0.1"
DEFAULT_ROOT_PATH = "/opt/www"

# Suggested container ports, taken from yaml_examples/server_config/config.yaml.
DEFAULT_PORTS = {
    "odoo_ssl": "11000",
    "odoo_http": "11000",
    "fast_report": "8899",
    "n8n": "5678",
    "kasm": "8443",
    "mailpit": "8025",
    "qdrant": "6333",
    "flowise": "3000",
    "guacamole": "8080",
}
DEFAULT_POLLPORT = "12000"
DEFAULT_GRPCPORT = "6334"

# Key order of a written entry — the same order as the YAML examples.
ENTRY_KEYS = (
    "config_template",
    "ip",
    "domain",
    "port",
    "pollport",
    "grpcport",
    "cert_name",
    "cert_key",
    "redirect_domain",
    "root_path",
    "backend_ip",
    "auth_file",
    "allowed_ips",
    "enable_http3",
    "disable_domain_listen",
)
_PORT_KEYS = {"port", "pollport", "grpcport"}

# Answers of the menu shown after a vhost was saved.
NEXT_ANOTHER = "another"
NEXT_FINISH = "finish"
NEXT_CANCEL = "cancel"

# Answers of the summary menu.
SUMMARY_SAVE = "save"
SUMMARY_EDIT = "edit"
SUMMARY_DISCARD = "discard"


class WizardAborted(Exception):
    """Raised when the user cancels a prompt (Ctrl-C)."""


@dataclass(frozen=True)
class TemplateFields:
    """Which values a template needs, read from its placeholders."""

    port: bool
    pollport: bool
    grpcport: bool
    certificate: bool
    redirect: bool
    root_path: bool
    backend_ip: bool
    auth: bool
    allowed_ips: bool
    http3: bool


def template_fields(name: str) -> TemplateFields:
    """Derive the questions for a template from the placeholders it carries."""
    content = get_config_template(name)
    if not content:
        raise ValueError(f"Unknown template: {name}")
    certificate = "zertifikat" in content
    return TemplateFields(
        port="{{PORT}}" in content,
        pollport="{{POLL_PORT}}" in content,
        grpcport="{{GRPC_PORT}}" in content,
        certificate=certificate,
        redirect=name.startswith("redirect"),
        root_path="{{ROOT_PATH}}" in content,
        backend_ip="{{BACKEND_IP}}" in content and "{{PORT}}" in content,
        auth="#authentication" in content,
        allowed_ips="#ip_restrictions" in content,
        http3=certificate and name not in HTTP3_EXCLUDED_TEMPLATES,
    )


def wizard_templates() -> list[str]:
    """Templates offered by the wizard (the catch-all is installed by 'setup-default')."""
    return sorted(VALID_TEMPLATES)


def detect_server_ip() -> str:
    """Return the IPv4 address of the interface that holds the default route.

    Connecting a UDP socket sends no packet; it only makes the kernel pick the
    outgoing interface. Returns "" when there is no route (offline host).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return ""


def config_filename(domain: str) -> str:
    """File name of the YAML that holds the vhost for ``domain``."""
    return f"{_safe_conf_filename(domain)}.yaml"


def find_domain_in_folder(folder: str, domain: str) -> list[str]:
    """Return the YAML files in ``folder`` that already define a vhost for ``domain``."""
    if not os.path.isdir(folder):
        return []
    found = []
    for file in sorted(os.listdir(folder)):
        if not file.endswith((".yaml", ".yml")):
            continue
        try:
            with open(os.path.join(folder, file), encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        for entry in data.values():
            if isinstance(entry, dict) and "config_template" in entry and str(entry.get("domain")) == domain:
                found.append(file)
                break
    return found


def build_entry(values: dict) -> dict:
    """Return the YAML entry: fixed key order, empty values and off-flags left out, ports as numbers."""
    entry: dict = {}
    for key in ENTRY_KEYS:
        value = values.get(key)
        if value in (None, "", False):
            continue
        if key in _PORT_KEYS:
            value = int(value)
        entry[key] = value
    return entry


def validate_entry(entry: dict) -> None:
    """Run the deploy's own validation on a finished entry; raises ValidationError."""

    def text(key: str) -> str:
        value = entry.get(key)
        return "" if value is None else str(value)

    validate_all_inputs(
        config_template=text("config_template"),
        domain=text("domain"),
        ip=text("ip"),
        port=text("port"),
        cert_name=text("cert_name"),
        cert_key=text("cert_key"),
        pollport=text("pollport"),
        grpcport=text("grpcport"),
        redirect_domain=text("redirect_domain"),
        auth_file=text("auth_file"),
        allowed_ips=text("allowed_ips"),
        backend_ip=text("backend_ip"),
        enable_http3=bool(entry.get("enable_http3")),
        root_path=text("root_path"),
    )
    if entry.get("enable_http3") and entry.get("disable_domain_listen"):
        raise ValidationError("enable_http3 and disable_domain_listen cannot be combined")


def render_entry(entry: dict) -> str:
    """YAML text of a vhost file, with a header naming its origin."""
    header = f"# Created by nginx-set-conf {__version__} wizard on {date.today().strftime('%d.%m.%Y')}\n"
    body = yaml.safe_dump({entry["domain"]: entry}, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return header + body


def write_entry(folder: str, entry: dict) -> str:
    """Write the entry to ``<folder>/<domain>.yaml`` atomically and return the path."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, config_filename(entry["domain"]))
    atomic_write_text(path, render_entry(entry))
    return path


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------


def _validator(check: Callable[[str], object], required: bool = True) -> Callable[[str], bool | str]:
    """Adapt a validators.py function to questionary: True or the error message."""

    def validate(value: str) -> bool | str:
        value = value.strip()
        if not value:
            return "A value is required" if required else True
        try:
            check(value)
        except ValidationError as e:
            return str(e)
        return True

    return validate


class Prompter(Protocol):
    """What the wizard needs from a terminal: a menu, a text field, a yes/no."""

    def select(self, message: str, choices: list[tuple[str, str]], default: str | None = None) -> str: ...

    def text(self, message: str, default: str = "", validate: Callable[[str], bool | str] | None = None) -> str: ...

    def confirm(self, message: str, default: bool = False) -> bool: ...


class QuestionaryPrompter:
    """Prompter backed by questionary (arrow-key menus, inline validation)."""

    @staticmethod
    def _answer(question: questionary.Question):
        answer = question.ask()
        if answer is None:
            raise WizardAborted
        return answer

    def select(self, message: str, choices: list[tuple[str, str]], default: str | None = None) -> str:
        q_choices = [questionary.Choice(title, value=value) for title, value in choices]
        default_choice = next((c for c in q_choices if c.value == default), None)
        return str(
            self._answer(
                questionary.select(
                    message,
                    choices=q_choices,
                    default=default_choice,
                    use_search_filter=len(q_choices) > 5,
                    use_jk_keys=False,
                )
            )
        )

    def text(self, message: str, default: str = "", validate: Callable[[str], bool | str] | None = None) -> str:
        return str(self._answer(questionary.text(message, default=default, validate=validate))).strip()

    def confirm(self, message: str, default: bool = False) -> bool:
        return bool(self._answer(questionary.confirm(message, default=default)))


def _ask_domain(prompter: Prompter, folder: str, default: str) -> str:
    """Ask for the domain; warn when a YAML in the folder already defines it."""
    while True:
        domain = prompter.text("Domain (server_name):", default=default, validate=_validator(validate_domain))
        existing = find_domain_in_folder(folder, domain)
        target = config_filename(domain)
        if not existing and not os.path.exists(os.path.join(folder, target)):
            return domain
        others = [f for f in existing if f != target]
        if os.path.exists(os.path.join(folder, target)):
            click.secho(f"  {target} already exists and would be overwritten.", fg="yellow")
        if others:
            click.secho(f"  {domain} is also defined in: {', '.join(others)}", fg="yellow")
        if prompter.confirm("Continue with this domain anyway?", default=False):
            return domain
        default = ""


def ask_vhost(prompter: Prompter, folder: str, previous: dict | None = None) -> dict:
    """Ask for one vhost and return its values (not yet built into an entry).

    ``previous`` pre-fills the answers: the values just entered for "edit
    again", or only template and IP of the last vhost for "another one".
    """
    prev = previous or {}
    template_width = max(len(name) for name in wizard_templates())
    template = prompter.select(
        "What do you want to set up?",
        [(f"{name.ljust(template_width)}  {TEMPLATE_DESCRIPTIONS.get(name, '')}", name) for name in wizard_templates()],
        default=prev.get("config_template", "odoo_ssl"),
    )
    fields = template_fields(template)
    same_template = prev.get("config_template") == template
    values: dict = {"config_template": template}

    values["ip"] = prompter.text(
        "Server IP the vhost listens on:",
        default=prev.get("ip") or detect_server_ip(),
        validate=_validator(validate_ip),
    )
    values["domain"] = _ask_domain(prompter, folder, prev.get("domain", "") if same_template else "")

    if fields.redirect:
        values["redirect_domain"] = prompter.text(
            "Redirect target domain:",
            default=prev.get("redirect_domain", "") if same_template else "",
            validate=_validator(validate_redirect_domain),
        )

    kept = prev if same_template else {}
    if fields.port:
        default_port = kept.get("port") or DEFAULT_PORTS.get(template, "")
        values["port"] = prompter.text("Container port:", default=default_port, validate=_validator(validate_port))
    if fields.pollport:
        values["pollport"] = prompter.text(
            "Odoo longpolling port:",
            default=kept.get("pollport") or DEFAULT_POLLPORT,
            validate=_validator(validate_port),
        )
    if fields.grpcport:
        values["grpcport"] = prompter.text(
            "Qdrant gRPC port:",
            default=kept.get("grpcport") or DEFAULT_GRPCPORT,
            validate=_validator(validate_port),
        )

    if fields.root_path:
        values["root_path"] = prompter.text(
            "Document root:",
            default=prev.get("root_path") or DEFAULT_ROOT_PATH,
            validate=_validator(validate_root_path),
        )

    if fields.certificate:
        _ask_certificate(prompter, values, kept)

    click.secho(f"  Advanced: {_advanced_options(fields)}", dim=True)
    if prompter.confirm("Set advanced options?", default=False):
        _ask_advanced(prompter, fields, values, kept)
    return values


def _ask_certificate(prompter: Prompter, values: dict, prev: dict) -> None:
    kind = prompter.select(
        "Certificate:",
        [
            ("Let's Encrypt (created on deploy if missing)", "letsencrypt"),
            ("Own certificate (.crt and .key files)", "own"),
        ],
        default="own" if prev.get("cert_key") else "letsencrypt",
    )
    if kind == "letsencrypt":
        default = str(prev.get("cert_name") or "") if not prev.get("cert_key") else ""
        default = default or values["domain"]
        values["cert_name"] = prompter.text(
            "Certificate name:", default=default, validate=_validator(validate_cert_name)
        )
        values["cert_key"] = ""
    else:
        values["cert_name"] = prompter.text(
            "Path to the certificate (.crt):",
            default=prev.get("cert_name", "") if prev.get("cert_key") else "",
            validate=_validator(validate_cert_name),
        )
        values["cert_key"] = prompter.text(
            "Path to the private key (.key):",
            default=prev.get("cert_key", ""),
            validate=_validator(validate_cert_key),
        )


def _advanced_options(fields: TemplateFields) -> str:
    names = []
    if fields.backend_ip:
        names.append("backend IP")
    if fields.auth:
        names.append("basic auth")
    if fields.allowed_ips:
        names.append("IP allowlist")
    if fields.http3:
        names.append("HTTP/3")
    names.append("wildcard listen")
    return ", ".join(names)


def _ask_advanced(prompter: Prompter, fields: TemplateFields, values: dict, prev: dict) -> None:
    if fields.backend_ip:
        backend_ip = prompter.text(
            "Backend IP of the container:",
            default=prev.get("backend_ip") or DEFAULT_BACKEND_IP,
            validate=_validator(validate_ip),
        )
        values["backend_ip"] = "" if backend_ip == DEFAULT_BACKEND_IP else backend_ip
    if fields.auth:
        values["auth_file"] = prompter.text(
            "htpasswd file for basic auth (empty = none):",
            default=prev.get("auth_file", ""),
            validate=_validator(validate_auth_file, required=False),
        )
    if fields.allowed_ips:
        values["allowed_ips"] = prompter.text(
            "Allowed IPs/CIDR, comma-separated (empty = everyone):",
            default=prev.get("allowed_ips", ""),
            validate=_validator(validate_allowed_ips, required=False),
        )
    if fields.http3:
        values["enable_http3"] = prompter.confirm(
            "Enable HTTP/3 (needs nginx >= 1.25 and UDP/443 open)?", default=bool(prev.get("enable_http3"))
        )
    if not values.get("enable_http3"):
        values["disable_domain_listen"] = prompter.confirm(
            "Wildcard listen instead of IP-bound (only safe after 'setup-default')?",
            default=bool(prev.get("disable_domain_listen")),
        )


def show_summary(folder: str, entry: dict) -> None:
    """Print the entry and the file it goes to."""
    path = os.path.join(folder, config_filename(entry["domain"]))
    width = max(len(key) for key in entry)
    click.echo()
    click.secho(f"  {path}", bold=True)
    for key, value in entry.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        click.echo(f"    {key.ljust(width)}  {value}")
    if os.path.exists(path):
        click.secho("  The existing file will be overwritten.", fg="yellow")
    click.echo()


def run_wizard(folder: str, prompter: Prompter, deploy: Callable[[list[str]], None]) -> list[str]:
    """Ask for vhosts until the user finishes; return the files written.

    ``deploy`` is called with the written files only after the user confirmed
    it on "finish". Ctrl-C discards the vhost being entered; files already
    saved stay in place and are not deployed.
    """
    written: list[str] = []
    deployed = False
    previous: dict | None = None
    click.secho(f"nginx-set-conf wizard — vhost files go to {folder}", bold=True)
    click.echo("Ctrl-C cancels at any time; vhosts saved so far are kept.\n")
    try:
        while True:
            values = ask_vhost(prompter, folder, previous)
            while True:
                entry = build_entry(values)
                try:
                    validate_entry(entry)
                except ValidationError as e:
                    click.secho(f"  {e}", fg="red")
                    action = prompter.select(
                        "This vhost cannot be saved:",
                        [("Edit again", SUMMARY_EDIT), ("Discard", SUMMARY_DISCARD)],
                        default=SUMMARY_EDIT,
                    )
                else:
                    show_summary(folder, entry)
                    action = prompter.select(
                        "Save this vhost?",
                        [("Save", SUMMARY_SAVE), ("Edit again", SUMMARY_EDIT), ("Discard", SUMMARY_DISCARD)],
                        default=SUMMARY_SAVE,
                    )
                if action != SUMMARY_EDIT:
                    break
                values = ask_vhost(prompter, folder, values)
            if action == SUMMARY_SAVE:
                path = write_entry(folder, entry)
                if path not in written:
                    written.append(path)
                click.secho(f"  Saved {path}", fg="green")
                # The next vhost is a different domain: carry over only what
                # is shared on one server.
                previous = {"config_template": values["config_template"], "ip": values["ip"]}

            choice = prompter.select(
                "What next?",
                [
                    ("Add another vhost", NEXT_ANOTHER),
                    ("Finish (offers to deploy)", NEXT_FINISH),
                    ("Cancel (no deploy)", NEXT_CANCEL),
                ],
                default=NEXT_ANOTHER,
            )
            if choice == NEXT_ANOTHER:
                continue
            if choice == NEXT_FINISH and written:
                deployed = _offer_deploy(prompter, written, deploy)
            break
    except WizardAborted:
        click.secho("\nCancelled — the vhost being entered was discarded.", fg="yellow")
    if not written:
        click.echo("No vhost file was written.")
    elif not deployed:
        click.echo(f"\n{len(written)} vhost file(s) saved, not deployed. Deploy the whole folder with:")
        click.echo(f"  nginx-set-conf --config_path={folder}")
    return written


def _offer_deploy(prompter: Prompter, written: list[str], deploy: Callable[[list[str]], None]) -> bool:
    """Ask before deploying the new files; True if the deploy ran."""
    click.echo("\nNew vhost files:")
    for path in written:
        click.echo(f"  {path}")
    if not prompter.confirm(f"Deploy these {len(written)} vhost(s) now (nginx -t, then reload)?", default=False):
        return False
    deploy(written)
    return True
