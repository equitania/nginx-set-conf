# Nginx-set-conf
====================================================================================  
This is a simple python library that helps you to create configurations for different docker based applications with nginx as reverse proxy.  
  
## Installation
  
### Nginx-set-conf requires:
  
- Python (>= 3.6)  
- click (>= 8.1.3)  
- PyYaml (>= 5.4.1)  
  
Use the package manager [pip](https://pip.pypa.io/en/stable/) to install nginx-set-conf.
  
```bash
pip install nginx-set-conf-equitania
```

---

## Usage

```bash
$ nginx-set-conf --help
usage: nginx-set-conf [--help] [--config_template] [--ip] [--domain] [--port] [--cert_name] [--pollport] [--redirect_domain] [--config_path]
```
```bash
Options:
  --config_template TEXT  Insert the conf-template.  
  
                          We support:

                          - ngx_code_server (code-server with ssl)
                          - ngx_fast_report (FastReport with ssl)
                          - ngx_nextcloud (NextCloud with ssl)
                          - ngx_odoo_http (Odoo only http)
                          - ngx_odoo_ssl (Odoo with ssl)
                          - ngx_pgadmin (pgAdmin4 with ssl)
                          - ngx_portainer (NextCloud with ssl)
                          - ngx_pwa (Progressive Web App with ssl)
                          - ngx_redirect (Redirect Domain without ssl)
                          - ngx_redirect_ssl (Redirect Domain with ssl)
  --ip TEXT               IP address of the server
  --domain TEXT           Name of the domain
  --port TEXT             Primary port for the Docker container
  --cert_name TEXT        Name of certificate
  --pollport TEXT         Secondary Docker container port for odoo pollings
  --redirect_domain TEXT  Redirect domain
  --auth_file TEXT         Use authfile for htAccess 
  --config_path TEXT      Yaml configuration folder
  --help                  Show this message and exit.
```
---

## Example
```bash
# Execution with config file
nginx-set-conf --config_path server_config
f.e.
nginx-set-conf --config_path=$HOME/docker-builds/ngx-conf
  
# Execution without config file
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.equitania.de --port 8069 --cert_name www.equitania.de --pollport 8072 

# Create your cert with
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.equitania.de
# Install certbot on Debian/Ubuntu with
apt-get install certbot
```
  
## nginx template settings  
  
You can download our settings: [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)  
and the : [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)  
based on [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)  
  
This project is licensed under the terms of the **AGPLv3** license.  