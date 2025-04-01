"""
Template for NextCloud NGINX configuration with SSL/HTTP2 support.
"""

TEMPLATE = """# Template for NextCloud configuration nginx incl. SSL/http2
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
    add_header Referrer-Policy no-referrer always;

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

    # Path to the root of your installation
    #root /var/www/owncloud/;
    root /var/www/nextcloud/;
    index index.html;

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

    # Raise file upload size
    client_max_body_size 10G;
    # Limit download size
    proxy_max_temp_file_size 4096m;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Proxy for nextcloud docker
    location / {
        # Headers are already set via https://github.com/nextcloud/server under lib/private/legacy/response.php#L242 (addSecurityHeaders())
        # We only need to set headers that aren't already set via nextcloud's addSecurityHeaders()-function
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
        add_header Referrer-Policy "same-origin";
        # Secure Cookie / Allow cookies only over https
        # https://en.wikipedia.org/wiki/Secure_cookies
        # https://maximilian-boehm.com/hp2134/NGINX-as-Proxy-Rewrite-Set-Cookie-to-Secure-and-HttpOnly.htm
        #authentication
        proxy_cookie_path / "/; secure; HttpOnly";
        # And don't forget to include our proxy parameters
        #include /etc/nginx/proxy_params;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;        # Connect to local port
        proxy_pass http://127.0.0.1:{{PORT}};
    }
}
""" 