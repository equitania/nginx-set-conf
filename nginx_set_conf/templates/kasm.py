"""
Template for Kasm Workspaces NGINX configuration with SSL/HTTP2 support.
"""

TEMPLATE = """# Template for Kasm Workspaces NGINX configuration with SSL/HTTP2 support
# 01.04.2025
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

map $http_upgrade $connection_upgrade {
  default upgrade;
  '' close;
}

proxy_cache_path /tmp levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m use_temp_path=off;
limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m rate=500r/m;

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl;
    http2 on;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;

    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log warn;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_timeout  30m;

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    # error pages
    error_page 500 502 503 504 /custom_50x.html;
        location = /custom_50x.html {
        root /etc/nginx/html/;
        internal;
    }

    location / {
        #authentication
        
        # WebSocket Support
        proxy_set_header        Upgrade $http_upgrade;
        proxy_set_header        Connection "upgrade";

        # Host and X headers
        proxy_set_header        Host $host;
        proxy_set_header        X-Real-IP $remote_addr;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Forwarded-Proto $scheme;

        # Connectivity Options
        proxy_http_version      1.1;
        proxy_read_timeout      1800s;
        proxy_send_timeout      1800s;
        proxy_connect_timeout   1800s;
        proxy_buffering         off;

        # Allow large requests to support file uploads to sessions
        client_max_body_size    10M;

        # Connect to local port with SSL
        proxy_pass             https://127.0.0.1:{{PORT}};
    }
}
""" 