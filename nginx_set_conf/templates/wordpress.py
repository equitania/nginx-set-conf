"""
Template for WordPress (official Docker image, Apache variant) behind NGINX with SSL/HTTP2.
"""

TEMPLATE = """# Template for WordPress configuration nginx incl. SSL/HTTP2 support
# 05.11.2026
#
# Backend: the official wordpress image (Apache variant), published on
# {{BACKEND_IP}}:{{PORT}}. WordPress itself must know it runs behind HTTPS:
# WP_HOME/WP_SITEURL on the https URL; the image already maps
# X-Forwarded-Proto to $_SERVER['HTTPS'].
# Redirect the bare domain to this vhost with a redirect_ssl entry.

map $http_upgrade $connection_upgrade {
  default upgrade;
  '' close;
}

proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m use_temp_path=off;
# Keyed on the client address only: X-Forwarded-For is set by the client and
# would let it pick a fresh bucket for every request.
limit_req_zone $binary_remote_addr zone=wplogin:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=wpmcp:10m rate=60r/m;

server {
    listen ip.ip.ip.ip:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen ip.ip.ip.ip:443 ssl;
    server_name server.domain.de;

    # Must match upload_max_filesize/post_max_size of the PHP container
    client_max_body_size 64M;

    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings (global SSL settings are in nginx.conf)
    keepalive_timeout    60;

    #ip_restrictions

    # Basic auth is server-wide: the regex locations below do not inherit
    # from location /. The MCP and REST endpoints switch it off because they
    # carry their own Authorization header (application passwords).
    #authentication

    limit_req_status 429;

    # Proxy headers, inherited by every location below (none sets its own)
    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;
    proxy_set_header X-Forwarded-Port  $server_port;
    proxy_set_header Upgrade           $http_upgrade;
    proxy_set_header Connection        $connection_upgrade;
    proxy_redirect off;
    proxy_buffers 16 32k;
    proxy_buffer_size 32k;

    #general proxy settings
    proxy_connect_timeout 10s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # error pages
    error_page 500 502 503 504 /custom_50x.html;
    location = /custom_50x.html {
        root /etc/nginx/html/;
        internal;
    }

    # security (headers, deny dot files except .well-known)
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    # --- Blocked paths ------------------------------------------------------
    # XML-RPC: brute force and pingback abuse. Remove for Jetpack or apps
    # that still need it.
    location = /xmlrpc.php {
        return 403;
    }

    # No PHP execution from the uploads directory
    location ~* ^/wp-content/uploads/.*\\.(?:php|phar|phtml)$ {
        return 403;
    }

    # Files that reveal configuration or version
    location ~* /(?:wp-config\\.php|readme\\.html|license\\.txt)$ {
        return 403;
    }

    # --- Login, rate limited ------------------------------------------------
    location = /wp-login.php {
        limit_req zone=wplogin burst=5 nodelay;
        proxy_pass http://{{BACKEND_IP}}:{{PORT}};
    }

    # --- REST API -----------------------------------------------------------
    location ^~ /wp-json/ {
        auth_basic off;
        proxy_pass http://{{BACKEND_IP}}:{{PORT}};
    }

    # --- MCP endpoint (MCP Adapter: /wp-json/mcp/<server>) ------------------
    # Streamable HTTP: no buffering, long timeouts.
    location ^~ /wp-json/mcp/ {
        # mcp_allowed_ips: only these clients reach the endpoint (403 otherwise)
        #mcp_ip_restrictions
        auth_basic off;
        limit_req zone=wpmcp burst=20 nodelay;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_pass http://{{BACKEND_IP}}:{{PORT}};
    }

    # --- Static files: cache in the browser ---------------------------------
    # `expires` instead of add_header, so the headers of security.conf stay
    # in effect (an add_header here would drop all of them).
    location ~* \\.(?:css|js|mjs|map|jpg|jpeg|gif|png|webp|avif|svg|ico|woff2?|ttf|eot|mp4|webm)$ {
        expires 30d;
        access_log off;
        proxy_pass http://{{BACKEND_IP}}:{{PORT}};
    }

    location / {
        proxy_pass http://{{BACKEND_IP}}:{{PORT}};
    }
}
"""
