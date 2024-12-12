"""
Nginx configuration templates for various services.

This module contains predefined Nginx configuration templates for different
services like code-server, FastReport, MailHog, NextCloud, Odoo, pgAdmin4,
Portainer, and PWA. Each template includes SSL/TLS and HTTP/2 configurations
where applicable.

Available templates:
    - ngx_code_server: Code-server with SSL/HTTP2
    - ngx_fast_report: FastReport with SSL
    - ngx_mailhog: MailHog with SSL
    - ngx_nextcloud: NextCloud with SSL
    - ngx_odoo_http: Odoo HTTP only
    - ngx_odoo_ssl: Odoo with SSL
    - ngx_pgadmin: pgAdmin4 with SSL
    - ngx_portainer: Portainer with SSL
    - ngx_pwa: Progressive Web App with SSL
    - ngx_redirect: Domain redirect without SSL
    - ngx_redirect_ssl: Domain redirect with SSL
"""

config_template_dict = {
    "ngx_code_server": """# Template for code-server configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

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

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Raise file upload size
    client_max_body_size 10G;
    # Limit download size
    proxy_max_temp_file_size 4096m;

    proxy_buffering off;
    proxy_http_version 1.1;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    access_log off;

    location ~ ^/(.*)
    {
        # Connect to local port
        #authentication
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_fast_report": """# Template for FastReport configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

    index index.html;

    # set max upload size
    client_max_body_size 10G;
    fastcgi_buffers 64 4K;

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

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Proxy for docker
    location / {
        # Connect to local port
        #authentication
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_nextcloud": """# Template for NextCloud configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

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
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_portainer": """# Template for Portainer configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

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

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Proxy for portainer docker
    location / {
        #authentication
        proxy_http_version         1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Real-PORT $remote_port;
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_odoo_http": """# Template for Odoo configuration nginx
# 12.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }
upstream odoo {
  server 127.0.0.1:oldport;
}
upstream odoochat {
  server 127.0.0.1:oldpollport;
}
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}
map $sent_http_content_type $content_type_csp {
    default "";
    ~image/ "default-src 'none'";
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    #client_max_body_size 8192m;
    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

    # increase proxy buffer to handle some Odoo web requests
    # proxy_buffers 16 64k;
    # proxy_buffer_size 128k;
    # proxy_headers_hash_max_size 76800;
    # proxy_headers_hash_bucket_size 9600;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 3000s;
    proxy_send_timeout 3000s;
    proxy_read_timeout 3000s;
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
        proxy_pass http://odoo;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure; 
        #authentication
    }

    # Chat Odoo
    location /websocket {
        proxy_pass http://odoochat;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure;
    }

    root /opt/odoo;
    try_files /odoo-server/odoo/addons$uri @odoo;

    # Serve static files right away
    location ~ ^/[^/]+/static/.+$ {
        # root and try_files both depend on your addons paths
        root ...;
        try_files ... @odoo;
        expires 24h;
        add_header Content-Security-Policy $content_type_csp;
    }
}
""",
    "ngx_odoo_ssl": """# Template for Odoo configuration nginx incl. SSL
# 12.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }
upstream odoo {
  server 127.0.0.1:oldport;
}
upstream odoochat {
  server 127.0.0.1:oldpollport;
}
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}
map $sent_http_content_type $content_type_csp {
    default "";
    ~image/ "default-src 'none'";
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl;
    http2 on;
    server_name server.domain.de;
    client_max_body_size 8192m;
    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_session_timeout 30m;
    ssl_protocols TLSv1.2;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # increase proxy buffer to handle some Odoo web requests
    # proxy_buffers 16 64k;
    # proxy_buffer_size 128k;
    # proxy_headers_hash_max_size 76800;
    # proxy_headers_hash_bucket_size 9600;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 3000s;
    proxy_send_timeout 3000s;
    proxy_read_timeout 3000s;
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
        proxy_pass http://odoo;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure; 
        #authentication
    }

    # Chat Odoo
    location /websocket {
        proxy_pass http://odoochat;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        proxy_cookie_flags session_id samesite=lax secure;
    }

    root /opt/odoo;
    try_files /odoo-server/odoo/addons$uri @odoo;

    # Serve static files right away
    location ~ ^/[^/]+/static/.+$ {
        # root and try_files both depend on your addons paths
        root ...;
        try_files ... @odoo;
        expires 24h;
        add_header Content-Security-Policy $content_type_csp;
    }
}
""",
    "ngx_pgadmin": """# Template for pgAdmin configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

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

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Proxy for pgadmin
    location / {
        # Connect to local port
        #authentication
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_pwa": """# Template for Progressive Web App .NET Core configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

    index index.html;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

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

        # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Proxy for docker
    location / {
        # Connect to local port
        #authentication
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_mailhog": """# Template for mailhog https://github.com/mailhog/MailHog/tree/master configuration nginx incl. SSL/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

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
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

    index index.html;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

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

        # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Proxy for docker
    location / {
        #authentication
        # Connect to local port
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",
    "ngx_redirect": """# Template for Redirect Domain configuration nginx
# 10.12.2024
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/target.domain.de-error.log;
}
""",
    "ngx_redirect_ssl": """# Template for Redirect domain configuration nginx ssl/http2
# 10.12.2024
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/target.domain.de-error.log;

    # additional config
    include                 nginxconfig.io/general.conf;
}

server {
    listen server.domain.de:443 ssl;
    http2 on;
    server_name server.domain.de;
    rewrite ^/.*$ https://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log;
    error_log /var/log/nginx/target.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # security
    include                 nginxconfig.io/security.conf;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 1200s;
    proxy_send_timeout 1200s;
    proxy_read_timeout 1200s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_timeout  5m;

    # additional config
    include                 nginxconfig.io/general.conf;
}
""",
}


def get_config_template(config_template_name):
    if config_template_name in config_template_dict:
        return config_template_dict[config_template_name]
    else:
        return ""
