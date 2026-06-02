"""
Template for static website / file-download hosting NGINX configuration with SSL/HTTP2 support.

Serves files directly from a local document root ({{ROOT_PATH}}) — no upstream backend,
no proxy_pass. Intended for static sites and download servers.
"""

TEMPLATE = """# Template for static website / file download hosting nginx incl. SSL/HTTP2 support
# 02.06.2026

server {
    listen ip.ip.ip.ip:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen ip.ip.ip.ip:443 ssl;
    server_name server.domain.de;

    # HTTP/2 is enabled globally in nginx.conf
    # Security headers including HSTS are in nginxconfig.io/security.conf

    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings (global SSL settings are in nginx.conf)
    keepalive_timeout    60;

    #ip_restrictions

    # static document root
    root {{ROOT_PATH}};
    index index.html;

    # Discourage indexing of hosted files. Declared at server scope so it merges
    # with the security.conf headers (a location-level add_header would otherwise
    # cancel header inheritance for that location).
    add_header X-Robots-Tag "noindex, nofollow, nosnippet, noarchive" always;

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    location / {
        #authentication
        # Serve existing files, then a directory index, else 404 (autoindex off).
        try_files $uri $uri/ =404;
    }
}
"""
