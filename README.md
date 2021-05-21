# Nginx-set-conf
====================================================================================    
This is a simple python library that helps you to create configurations for different docker based applications with nginx as reverse proxy.

## Installation

### Nginx-set-conf requires:

- Python (>= 3.6)
- click (>= 7.1.2)
- PyYaml (>= 3.12)

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install nginx-set-conf.

```bash
pip install nginx-set-conf-equitania
```

---

## Usage

```bash
$ nginx-set-conf --help
usage: nginx-set-conf [--help] [--config_template] [--ip] [--domain] [--port] [--cert_name] [--pollport] [--config_path]
```
```bash
Optional arguments:
  --config_template          The config template
  --ip                       IP address of the server
  --domain                   Name of the domain
  --port                     Primary port for the Docker container
  --cert_name                Name of certificate
  --pollport                 Secondary Docker container port for odoo pollings
  --config_path              Configuration folder
  --help                     Show this message and exit.
```
---

## Example
```bash
# Execution with config file
nginx-set-conf --config_path server_config
# Execution without config file
nginx-set-conf --config_template ngx_odoo_ssl_pagespeed --ip 1.2.3.4 --domain equitania --port 443 --cert_name cert1 --pollport 8099
```

This project is licensed under the terms of the **AGPLv3** license.
