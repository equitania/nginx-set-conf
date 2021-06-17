config_template_dict = {
"ngx_code_server": """# Template for code-server configuration nginx incl. SSL/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;

    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.1 TLSv1.2;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    pagespeed off;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
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
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",

"ngx_fast_report": """# Template for FastReport configuration nginx incl. SSL/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;

    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    index index.html;

    # set max upload size
    client_max_body_size 10G;
    fastcgi_buffers 64 4K;

    pagespeed off;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Proxy for docker
    location / {
        # Connect to local port
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",

"ngx_nextcloud": """# Template for NextCloud configuration nginx incl. SSL/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;
    add_header Referrer-Policy no-referrer always;

    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_timeout  5m;

    # Path to the root of your installation
    #root /var/www/owncloud/;
    root /var/www/nextcloud/;
    index index.html;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    # Raise file upload size
    client_max_body_size 10G;
    # Limit download size
    proxy_max_temp_file_size 4096m;

    pagespeed off;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
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
        proxy_cookie_path / "/; secure; HttpOnly";
        # And don't forget to include our proxy parameters
        #include /etc/nginx/proxy_params;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;        # Connect to local port
        proxy_pass http://127.0.0.1:oldport;
    }
}""",

"ngx_odoo_http": """# Template for Odoo configuration nginx
# version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    client_max_body_size 8192m;
    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # increase proxy buffer to handle some Odoo web requests
    proxy_buffers 16 64k;
    proxy_buffer_size 128k;
    proxy_headers_hash_max_size 76800;
    proxy_headers_hash_bucket_size 9600;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # error pages
    error_page 500 502 503 504 /custom_50x.html;
        location = /custom_50x.html {
        root /etc/nginx/html/;
        internal;
    }

    pagespeed off;

    # set headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;

    #location = /robots.txt {
    #    add_header Content-Type text/plain;
    #    return 200 "User-agent: *Disallow: /";
    #}

    location / {
        proxy_pass http://127.0.0.1:oldport;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }

    # Chat Odoo
    location /longpolling {
        proxy_pass http://127.0.0.1:oldpollport;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering    on;
        expires 864000;
        proxy_pass http://127.0.0.1:oldport;
    }
}""",

"ngx_odoo_ssl": """# Template for Odoo configuration nginx incl. SSL
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;
    client_max_body_size 8192m;
    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    # increase proxy buffer to handle some Odoo web requests
    proxy_buffers 16 64k;
    proxy_buffer_size 128k;
    proxy_headers_hash_max_size 76800;
    proxy_headers_hash_bucket_size 9600;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
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

    pagespeed off;

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    location / {
        proxy_pass http://127.0.0.1:oldport;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }

    # Chat Odoo
    location /longpolling {
        proxy_pass http://127.0.0.1:oldpollport;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering    on;
        expires 864000;
        proxy_pass http://127.0.0.1:oldport;
    }
}

""",

"ngx_odoo_ssl_pagespeed": """# Template for Odoo configuration nginx incl. SSL/http2 and Google PageSpeed
# source: https://github.com/apache/incubator-pagespeed-ngx/blob/master/scripts/build_ngx_pagespeed.sh
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;
    client_max_body_size 8192m;
    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    # increase proxy buffer to handle some Odoo web requests
    proxy_buffers 16 64k;
    proxy_buffer_size 128k;
    proxy_headers_hash_max_size 76800;
    proxy_headers_hash_bucket_size 9600;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
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

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    location / {
        proxy_pass http://127.0.0.1:oldport;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        #auth_basic       "Restricted Area";
        #auth_basic_user_file  htpasswd/testmyodoo;
    }

    # Chat Odoo
    location /longpolling {
        proxy_pass http://127.0.0.1:oldpollport;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering    on;
        expires 864000;
        proxy_pass http://127.0.0.1:oldport;
    }

    # let's speed up PageSpeed by storing it in the super duper fast memcached
    pagespeed MemcachedThreads 1;
    pagespeed MemcachedServers "localhost:11211";

    # Filter settings
    pagespeed RewriteLevel OptimizeForBandwidth;
    pagespeed EnableFilters remove_quotes,collapse_whitespace,remove_comments,extend_cache;
    pagespeed ForbidFilters inline_javascript,rewrite_javascript,combine_javascript;
    pagespeed DisableFilters inline_javascript,rewrite_javascript,combine_javascript;

    #  Ensure requests for pagespeed optimized resources go to the pagespeed
    #  handler and no extraneous headers get set.
    location ~ "\.pagespeed\.([a-z]\.)?[a-z]{2}\.[^.]{10}\.[^.]+" {
        add_header "" "";
    }

    location ~ "^/ngx_pagespeed_static/" {
    }

    location ~ "^/ngx_pagespeed_beacon$" {
    }

    location /ngx_pagespeed_statistics {
        allow 127.0.0.1;
        deny all;
    }

    location /ngx_pagespeed_global_statistics {
        allow 127.0.0.1;
        deny all;
    }

    location /ngx_pagespeed_message {
        allow 127.0.0.1;
        deny all;
    }

    location /pagespeed_console {
        allow 127.0.0.1;
        deny all;
    }
}""",

"ngx_pgadmin": """# Template for pgAdmin configuration nginx incl. SSL/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;

    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    pagespeed off;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Proxy for docker
    location / {
        # Connect to local port
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass http://127.0.0.1:oldport;
    }
}
""",

"ngx_pwa": """# Template for Progressive Web App .NET Core configuration nginx incl. SSL/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ https://$host$request_uri? permanent;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;

    add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;

    access_log /var/log/nginx/server.domain.de-access.log;
    error_log /var/log/nginx/server.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;

    index index.html;

    pagespeed off;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *Disallow: /";
    }

    # Add Headers for odoo proxy mode
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Proxy for docker
    location / {
        # Connect to local port
        proxy_pass http://127.0.0.1:oldport;
    }
}""",

"ngx_redirect": """# Template for Redirect Domain configuration nginx
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log;
    error_log /var/log/nginx/target.domain.de-error.log;
}""",

"ngx_redirect_ssl": """# Template for Redirect domain configuration nginx ssl/http2
# Version 3.1 from 26.05.2021
upstream server.domain.de {
    server ip.ip.ip.ip weight=1 fail_timeout=0;
}

server {
    listen server.domain.de:80;
    server_name server.domain.de;
    rewrite ^/.*$ http://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log;
    error_log /var/log/nginx/target.domain.de-error.log;
}

server {
    listen server.domain.de:443 ssl http2;
    server_name server.domain.de;
    rewrite ^/.*$ https://target.domain.de$request_uri? permanent;
    access_log /var/log/nginx/target.domain.de-access.log;
    error_log /var/log/nginx/target.domain.de-error.log;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    #general proxy settings
    # force timeouts if the backend dies
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_read_timeout 720s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # add ssl specific settings
    keepalive_timeout    60;
    ssl_protocols        TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # limit ciphers
    ssl_session_cache    shared:SSL:1m;
    ssl_session_timeout  5m;
}"""
}


def get_config_template(config_template_name):
    if config_template_name in config_template_dict:
        return config_template_dict[config_template_name]
    else:
        return ""