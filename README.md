# Nginx-set-conf

====================================================================================  
This is a simple python library that helps you to create configurations for different docker based applications with nginx as reverse proxy.  
  
## Installation
  
### Nginx-set-conf requires
  
- Python (>= 3.8)  
- click (>= 8.1.3)  
- PyYaml (>= 5.4.1)  
  
Use the package manager [pip](https://pip.pypa.io/en/stable/) to install nginx-set-conf.
  
```bash
pip install nginx-set-conf
```

---

## Usage

```bash
$ nginx-set-conf --help
usage: nginx-set-conf [--help] [--config_template] [--ip] [--domain] [--port] [--cert_name] [--pollport] [--redirect_domain] [--auth_file] [--config_path] [--target_path] [--dry_run]
```

```bash
Options:
  --config_template TEXT  Insert the conf-template.  
  --show_template        Show the template configuration without applying it
  
                          We support:
                          - ngx_code_server (code-server with ssl)
                          - ngx_fast_report (FastReport with ssl)
                          - ngx_kasm (Kasm Workspaces with ssl/http2)
                          - ngx_mailpit (Mailpit with ssl/http2)
                          - ngx_n8n (n8n with ssl/http2)
                          - ngx_nextcloud (NextCloud with ssl)
                          - ngx_odoo_http (Odoo only http)
                          - ngx_odoo_ssl (Odoo with ssl)
                          - ngx_pgadmin (pgAdmin4 with ssl)
                          - ngx_portainer (Portainer with ssl)
                          - ngx_pwa (Progressive Web App with ssl)
                          - ngx_qdrant (Qdrant vector database with ssl/http2 and gRPC support)
                          - ngx_redirect (Redirect Domain without ssl)
                          - ngx_redirect_ssl (Redirect Domain with ssl)
  --ip TEXT               IP address of the server
  --domain TEXT           Name of the domain
  --port TEXT             Primary port for the Docker container
  --cert_name TEXT        Name of certificate if you want to use letsencrypt - complete path for self signed or purchased certificates
  --cert_key TEXT         Name and path of certificate key - for self signed or purchased certificates - leave empty for letsencrypt
  --pollport TEXT         Secondary Docker container port for odoo pollings
  --grpcport TEXT         Secondary Docker container port for gRPC services (used by Qdrant)
  --redirect_domain TEXT  Redirect domain
  --auth_file TEXT        Use authfile for htAccess 
  --config_path TEXT      Yaml configuration folder
  --target_path TEXT      Target path where the configuration files will be saved (default: /etc/nginx/conf.d)
  --dry_run               Run configuration generation without applying changes or creating certificates
  --help                  Show this message and exit.
```

---

## Example

```bash
# Execution with config file
nginx-set-conf --config_path server_config
```

f.e.

```bash
nginx-set-conf --config_path=$HOME/docker-builds/ngx-conf
```  

### Execution without config file

```bash
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.equitania.de --port 8069 --cert_name www.equitania.de --pollport 8072
```

### Using custom target path

```bash
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.equitania.de --port 8069 --cert_name www.equitania.de --target_path /tmp/nginx-test
```

### Dry run mode

```bash
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.equitania.de --port 8069 --cert_name www.equitania.de --dry_run
```

### Create your cert

```bash
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.equitania.de
```

### Install certbot on Debian/Ubuntu with

```bash
apt-get install certbot
```

### Create your auth file

#### Install htpasswd on Debian/Ubuntu with

```bash
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htaccess/.htpasswd-user USER
```  

## nginx template settings  
  
You can download our settings: [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)  
and the : [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)  
based on [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)  
  
This project is licensed under the terms of the **AGPLv3** license.  

```bash
# Show template configuration
nginx-set-conf --config_template ngx_odoo_ssl --show_template

# Show kasm template
nginx-set-conf --config_template ngx_kasm --show_template

# Test configuration without applying changes
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain example.com --port 8069 --cert_name example.com --dry_run

# Use custom target path for configuration files
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain example.com --port 8069 --cert_name example.com --target_path /tmp/nginx-configs
```

### Qdrant Vector Database Example

```bash
# Qdrant with gRPC support
nginx-set-conf --config_template ngx_qdrant --ip 1.2.3.4 --domain vector.example.com --port 6333 --grpcport 6334 --cert_name vector.example.com

# Show qdrant template configuration
nginx-set-conf --config_template ngx_qdrant --show_template
```
