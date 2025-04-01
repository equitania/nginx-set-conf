"""
Template for Domain Redirect NGINX configuration (HTTP only).
"""

TEMPLATE = """# Template for Redirect Domain configuration nginx
# 01.04.2025
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

map $http_upgrade $connection_upgrade {
  default upgrade;
  '' close;
}

proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m use_temp_path=off;
limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m rate=500r/m;

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/target.domain.de-error.log;
}
""" 