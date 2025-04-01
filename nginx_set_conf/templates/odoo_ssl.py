"""
Template for Odoo NGINX configuration with SSL/HTTP2 support.
"""

TEMPLATE = """# Template for Odoo configuration nginx incl. SSL/HTTP2 support
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
    
    # Set max upload size
    client_max_body_size 10G;
    
    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_timeout  30m;

    # increase proxy buffer to handle some Odoo web requests
    proxy_buffers 16 64k;
    proxy_buffer_size 128k;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # error pages
    error_page 500 502 503 504 /custom_50x.html;
    location = /custom_50x.html {
        root /etc/nginx/html/;
        internal;
    }

    #location = /robots.txt {
    #    add_header Content-Type text/plain;
    #    return 200 "User-agent: *Disallow: /";
    #}

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    location / {
        # Add Headers for odoo proxy mode
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{{PORT}};

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure; 
        #authentication
    }

    # Chat Odoo
    location /websocket {
        proxy_pass http://127.0.0.1:{{POLL_PORT}};

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering    on;
        expires 864000;
        proxy_pass http://127.0.0.1:{{PORT}};
    }

}
""" 