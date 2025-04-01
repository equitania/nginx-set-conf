"""
Template for Odoo NGINX configuration (HTTP only version).
"""

TEMPLATE = """# Template for Odoo configuration nginx
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
    
    # Set max upload size
    client_max_body_size 10G;
    
    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

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

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

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