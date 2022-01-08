# -*- coding: utf-8 -*-
# Copyright 2014-now Equitania Software GmbH - Pforzheim - Germany
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml
import os
from .config_templates import get_config_template

def fire_all_functions(function_list: list):
    """
        Execute each function in a list
        :param function_list: List of functions
    """
    for func in function_list:
        func()


def self_clean(input_dictionary: dict) -> dict:
    """
        Remove duplicates in dictionary
        :param: input_dictionary
        :return: return_dict
    """
    return_dict = input_dictionary.copy()
    for key, value in input_dictionary.items():
        return_dict[key] = list(dict.fromkeys(value))
    return return_dict


def parse_yaml(yaml_file):
    """
        Parse yaml file to object and return it
        :param: yaml_file: path to yaml file
        :return: yaml_object
    """
    with open(yaml_file, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return False


def parse_yaml_folder(path):
    """
        Parse multiple yaml files to list of objects and return them
        :param: yaml_file: path to yaml files
        :return: yaml_objects
    """
    yaml_objects = []
    for file in os.listdir(path):
        if file.endswith(".yaml") or file.endswith(".yml"):
            yaml_object = parse_yaml(os.path.join(path, file))
            if yaml_object:
                yaml_objects.append(yaml_object)
    return yaml_objects


def get_default_vars():
    return {
        #"server_path": "/etc/nginx/conf.d",
        "server_path": "$HOME/Public",
        "old_domain": "server.domain.de",
        "old_ip": "ip.ip.ip.ip",
        "old_port": "oldport",
        "old_pollport": "oldpollport",
        "old_crt": "zertifikat.crt",
        "old_key": "zertifikat.key",
        "old_redirect_domain" : "target.domain.de"
    }


def retrieve_valid_input(message):
    user_input = input(message)
    if user_input:
        return user_input
    else:
        return retrieve_valid_input(message)


def execute_commands(config_template, domain, ip, cert_name, port, pollport, redirect_domain):
    # Get default vars
    default_vars = get_default_vars()
    server_path = default_vars["server_path"]
    old_domain = default_vars["old_domain"]
    old_ip = default_vars["old_ip"]
    old_crt = default_vars["old_crt"]
    old_key = default_vars["old_key"]
    old_port = default_vars["old_port"]
    old_pollport = default_vars["old_pollport"]
    old_redirect_domain = default_vars["old_redirect_domain"]
    # Get config templates
    config_template_content = get_config_template(config_template)
    if config_template_content:
        current_path = os.path.dirname(os.path.realpath(__file__))
        file_path = current_path + "/" + config_template + ".conf"
        with open(file_path, 'w') as f:
            f.write(config_template_content)
        # copy command
        eq_display_message = "Copy " + file_path + " " + server_path + "/" + domain + ".conf"
        eq_copy_command = "cp " + file_path + " " + server_path + "/" + domain + ".conf"
        print(eq_display_message.rstrip("\n"))
        os.system(eq_copy_command)
        os.remove(file_path)
    else:
        print("No valid config template")

    # send command - domain
    eq_display_message = "Set domain name in conf to " + domain
    eq_set_domain_cmd = "sed -i s/" + old_domain + "/" + domain + "/g " + server_path + "/" + domain + ".conf"
    print(eq_display_message.rstrip("\n"))
    os.system(eq_set_domain_cmd)

    # send command - ip
    eq_display_message = "Set ip in conf to " + ip
    eq_set_ip_cmd = "sed -i s/" + old_ip + "/" + ip + "/g " + server_path + "/" + domain + ".conf"
    print(eq_display_message.rstrip("\n"))
    os.system(eq_set_ip_cmd)

    # send command - cert, key
    eq_display_message = "Set cert name in conf to " + cert_name
    eq_set_cert_cmd = "sed -i s/" + old_crt + "/" + cert_name + "/g " + server_path + "/" + domain + ".conf"
    eq_set_key_cmd = "sed -i s/" + old_key + "/" + cert_name + "/g " + server_path + "/" + domain + ".conf"
    print(eq_display_message.rstrip("\n"))
    os.system(eq_set_cert_cmd)
    os.system(eq_set_key_cmd)

    # Search for certificate and create it when it does not exist
    cert_exists = os.path.isfile("/etc/letsencrypt/live/" + cert_name + "/fullchain.pem") and os.path.isfile("/etc/letsencrypt/live/" + cert_name + "/privkey.pem")
    if not cert_exists:
        os.system("systemctl stop nginx.service")
        eq_create_cert = "certbot certonly --standalone --agree-tos --register-unsafely-without-email -d " + cert_name
        os.system(eq_create_cert)

    # send command - port
    eq_display_message = "Set port in conf to " + port
    eq_set_port_cmd = "sed -i s/" + old_port + "/" + port + "/g " + server_path + "/" + domain + ".conf"
    print(eq_display_message.rstrip("\n"))
    os.system(eq_set_port_cmd)

    if "odoo" in config_template and pollport:
        # send command - polling port
        eq_display_message = "Set polling port in conf to " + pollport
        eq_set_port_cmd = "sed -i s/" + old_pollport + "/" + pollport + "/g " + server_path + "/" + domain + ".conf"
        print(eq_display_message.rstrip("\n"))
        os.system(eq_set_port_cmd)

    if "redirect" in config_template and redirect_domain:
        # send command - redirect domain
        eq_display_message = "Set redirect domain in conf to " + redirect_domain
        eq_set_redirect_cmd = "sed -i s/" + old_redirect_domain + "/" + redirect_domain + "/g " + server_path + "/" + domain + ".conf"
        print(eq_display_message.rstrip("\n"))
        os.system(eq_set_redirect_cmd)

    # Search for certificate and create it when it does not exist
    if "redirect_ssl" in config_template and redirect_domain:
        cert_exists = os.path.isfile("/etc/letsencrypt/live/" + redirect_domain + "/fullchain.pem") and os.path.isfile("/etc/letsencrypt/live/" + redirect_domain + "/privkey.pem")
        if not cert_exists:
            os.system("systemctl stop nginx.service")
            eq_create_cert = "certbot certonly --standalone --agree-tos --register-unsafely-without-email -d " + redirect_domain
            os.system(eq_create_cert)
