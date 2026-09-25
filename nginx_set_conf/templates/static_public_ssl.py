"""
Template for a public, search-engine and AI-agent friendly static site with SSL/HTTP2 support.

Counterpart to static_ssl (which marks everything noindex): this template is meant to be
found. It serves a static document root ({{ROOT_PATH}}) with

- clean URLs: /page serves page.html
- markdown as a first-class format: text/markdown with charset, gzip, CORS, and the markdown
  variant of a page when the client sends "Accept: text/markdown"
- Link headers: a canonical link on .html/.md files, and for PDFs under /pdf/<name>.pdf an
  alternate link to /<name>.md plus a describedby link to /<name>

Expected layout of the document root (pages without a markdown twin work, too):
    /index.html  /<name>.html  /<name>.md  /pdf/<name>.pdf  /llms.txt  /robots.txt  /sitemap.xml

No location block sets add_header: that would cancel the security.conf headers for that
location. Per-file headers are set as variables and emitted by server-level add_header;
nginx omits a header whose value is empty.
"""

TEMPLATE = """# Template for a public static site (indexable, markdown-aware) nginx incl. SSL/HTTP2 support
# 25.09.2026

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

    # Basic auth is server-wide here: the regex locations below do not inherit from location /.
    #authentication

    # static document root
    root {{ROOT_PATH}};
    index index.html;

    # markdown is text: charset and compression (server-level lists replace the http-level ones)
    charset_types text/xml text/plain text/markdown text/css application/javascript application/xml application/rss+xml application/atom+xml;
    gzip_types text/plain text/markdown text/css text/xml application/json application/javascript application/rss+xml application/atom+xml application/xml image/svg+xml;

    # Per-file headers, filled in by the locations below; empty values are not sent.
    set $static_link "";
    set $static_cors "";
    set $static_vary "";
    add_header Link $static_link always;
    add_header Access-Control-Allow-Origin $static_cors always;
    add_header Vary $static_vary always;

    # Agents asking for markdown get /<name>.md on the clean URL /<name>.
    set $static_variant ".html";
    if ($http_accept ~* "text/markdown") {
        set $static_variant ".md";
    }

    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    location / {
        # try_files serves the matched file inside this location, so .md needs its type here.
        include mime.types;
        types { text/markdown md; }
        set $static_vary "Accept";
        try_files $uri $uri$static_variant $uri.html $uri/ =404;
    }

    location ~ ^/(?<static_page>[A-Za-z0-9._-]+)\\.html$ {
        set $static_link "<https://server.domain.de/$static_page>; rel=\\"canonical\\"";
    }

    location = /index.html {
    }

    location ~ ^/(?<static_page>[A-Za-z0-9._-]+)\\.md$ {
        types { }
        default_type text/markdown;
        set $static_cors "*";
        set $static_link "<https://server.domain.de/$static_page>; rel=\\"canonical\\"";
    }

    location ~ ^/pdf/(?<static_page>[A-Za-z0-9._-]+)\\.pdf$ {
        set $static_cors "*";
        set $static_link "<https://server.domain.de/$static_page.md>; rel=\\"alternate\\"; type=\\"text/markdown\\", <https://server.domain.de/$static_page>; rel=\\"describedby\\"";
    }

    location ~ ^/llms(-full)?\\.txt$ {
        types { }
        default_type text/markdown;
        set $static_cors "*";
    }
}
"""
