# -*- coding: utf-8 -*-
# Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .utils import parse_yaml_folder
import click
import os


def welcome():
    click.echo("Welcome to the nginx_set_conf!")


def get_default_vars():
    return {
        "server_path": "/etc/nginx/conf.d/",
        "old_domain": "server.domain.de",
        "old_ip": "ip.ip.ip.ip",
        "old_port": "oldport",
        "old_pollport": "oldpollport",
        "old_crt": "zertifikat.crt",
        "old_key": "zertifikat.key"
    }


# Help text conf
eq_config_support = """
Insert the conf-template.
\f
We support:\f
\b
- ngx_odoo_ssl_pagespeed (Odoo with ssl and PageSpeed)
- ngx_fast_report (FastReport with ssl)
- ngx_code_server (code-server with ssl)
- ngx_nextcloud (NextCloud with ssl)
- ngx_odoo_http (Odoo only http)
- ngx_odoo_ssl (Odoo with ssl)
- ngx_pgadmin (pgAdmin4 with ssl)
- ngx_pwa (Progressive Web App with ssl)
- ngx_redirect_ssl (Redirect Domain with ssl)
- ngx_redirect (Redirect Domain without ssl) 
\f
Files with the same name + .conf has to be stored in the same folder.
"""


@click.command()
@click.option('--config_template',
              help=eq_config_support)
@click.option('--ip',
              help='IP address of the server')
@click.option('--domain',
              help='Name of the domain')
@click.option('--port',
              help='Primary port for the Docker container')
@click.option('--cert_name',
              help='Name of certificate')
@click.option('--pollport',
              help='Secondary Docker container port for odoo pollings')
@click.option('--config_path', help='Configuration folder',
              prompt='Please enter the path to your configuration folder')
def start_nginx_set_conf(config_template, ip, domain, port, cert_name, pollport, config_path):
    # Get relative path
    script_path = os.path.dirname(os.path.realpath(__file__)) + "/config_templates"
    if config_path or (config_template and ip and domain and port and cert_name and pollport):
        # Get vars from yaml file
        if config_path:
            yaml_config = parse_yaml_folder(config_path)[0]
            default_vars = yaml_config["Server"]
            config_template = yaml_config["config_template"]
            ip = yaml_config["ip"]
            domain = yaml_config["domain"]
            port = str(yaml_config["port"])
            cert_name = yaml_config["cert_name"]
            pollport = str(yaml_config["pollport"])
        else:
            default_vars = get_default_vars()

        server_path = default_vars["server_path"]
        old_domain = default_vars["old_domain"]
        old_ip = default_vars["old_ip"]
        old_crt = default_vars["old_crt"]
        old_key = default_vars["old_key"]
        old_port = default_vars["old_port"]
        old_pollport = default_vars["old_pollport"]

        # copy command
        eq_display_message = "Copy " + script_path + "/" + config_template + ".conf " + server_path + "/" + domain + ".conf"
        eq_copy_command = "cp " + script_path + "/" + config_template + ".conf " + server_path + "/" + domain + ".conf"
        click.echo(eq_display_message.rstrip("\n"))
        os.system(eq_copy_command)

        # sed command - domain
        eq_display_message = "Set domain name in conf to " + domain
        eq_set_domain_cmd = "sed -i s/" + old_domain + "/" + domain + "/g " + server_path + "/" + domain + ".conf"
        click.echo(eq_display_message.rstrip("\n"))
        os.system(eq_set_domain_cmd)

        # sed command - ip
        eq_display_message = "Set ip in conf to " + ip
        eq_set_ip_cmd = "sed -i s/" + old_ip + "/" + ip + "/g " + server_path + "/" + domain + ".conf"
        click.echo(eq_display_message.rstrip("\n"))
        os.system(eq_set_ip_cmd)

        # sed command - cert, key
        eq_display_message = "Set cert name in conf to " + cert_name
        eq_set_cert_cmd = "sed -i s/" + old_crt + "/" + cert_name + "/g " + server_path + "/" + domain + ".conf"
        eq_set_key_cmd = "sed -i s/" + old_key + "/" + cert_name + "/g " + server_path + "/" + domain + ".conf"
        click.echo(eq_display_message.rstrip("\n"))
        os.system(eq_set_cert_cmd)
        os.system(eq_set_key_cmd)

        # sed command - port
        eq_display_message = "Set port in conf to " + port
        eq_set_port_cmd = "sed -i s/" + old_port + "/" + port + "/g " + server_path + "/" + domain + ".conf"
        click.echo(eq_display_message.rstrip("\n"))
        os.system(eq_set_port_cmd)

        if "odoo" in config_template and pollport != "":
            # sed command - polling port
            eq_display_message = "Set polling port in conf to " + pollport
            eq_set_port_cmd = "sed -i s/" + old_pollport + "/" + pollport + "/g " + server_path + "/" + domain + ".conf"
            click.echo(eq_display_message.rstrip("\n"))
            os.system(eq_set_port_cmd)
    else:
        click.echo("Not enough parameters!")


if __name__ == "__main__":
    welcome()
    start_nginx_set_conf()
