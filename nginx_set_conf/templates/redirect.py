"""
Template for Domain Redirect NGINX configuration (HTTP only).
"""

TEMPLATE = """# Template for Redirect Domain configuration nginx
# 22.04.2026
upstream server.domain.de {
    server {{BACKEND_IP}} weight=1 fail_timeout=0;
}

map $http_upgrade $connection_upgrade {
  default upgrade;
  '' close;
}

server {
    listen ip.ip.ip.ip:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/target.domain.de-error.log;
}
"""
