"""
Template for Apache Guacamole NGINX configuration with SSL/HTTP2 and WebSocket support.
"""

TEMPLATE = """# Template for Apache Guacamole NGINX configuration with SSL/HTTP2 and WebSocket support
# 10.09.2025
# upstream server.domain.de {
#     server ip.ip.ip.ip weight=1 fail_timeout=0;
# }

# WebSocket upgrade mapping - required for Guacamole
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

# Connection header mapping for WebSocket compatibility
map $http_upgrade $http_connection {
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
    server_name server.domain.de;

    # HTTP/2 is enabled globally in nginx.conf
    # Security headers including HSTS are in nginxconfig.io/security.conf

    access_log /var/log/nginx/server.domain.de-access.log combined buffer=512k flush=1m;
    error_log /var/log/nginx/server.domain.de-error.log warn;

    # ssl certificate files
    ssl_certificate /etc/letsencrypt/live/zertifikat.crt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zertifikat.key/privkey.pem;

    # SSL settings are defined globally in /etc/nginx/nginx.conf
    keepalive_timeout    60;
    
    #ip_restrictions
    
    # security
    include                 nginxconfig.io/security.conf;

    # additional config
    include                 nginxconfig.io/general.conf;

    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *\nDisallow: /";
    }

    # error pages
    error_page 500 502 503 504 /custom_50x.html;
        location = /custom_50x.html {
        root /etc/nginx/html/;
        internal;
    }

    # Guacamole-specific proxy settings
    # Extended timeouts for long RDP/SSH/VNC sessions
    proxy_connect_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_read_timeout 3600s;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

    # Main Guacamole location block
    location / {
        #authentication
        proxy_pass http://127.0.0.1:{{PORT}}/guacamole/;
        proxy_http_version 1.1;

        # Critical WebSocket headers for Guacamole
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;

        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Disable buffering for real-time communication
        proxy_buffering off;
        proxy_request_buffering off;

        # Increase upload limit for file transfers via RDP/SSH
        client_max_body_size 100M;
        client_body_buffer_size 16M;

        # WebSocket specific settings
        proxy_cache_bypass $http_upgrade;

        # Prevent timeout disconnections
        send_timeout 3600s;
        client_body_timeout 3600s;

        # Cookie path adjustment for Guacamole
        proxy_cookie_path /guacamole/ /;

        # Disable access logging for performance (optional)
        access_log off;
    }

    # Alternative path configuration (if serving from subpath)
    # Uncomment and modify if needed
    # location /remote/ {
    #     proxy_pass http://127.0.0.1:{{PORT}}/guacamole/;
    #     proxy_http_version 1.1;
    #     proxy_set_header Upgrade $http_upgrade;
    #     proxy_set_header Connection $connection_upgrade;
    #     proxy_set_header Host $host;
    #     proxy_set_header X-Real-IP $remote_addr;
    #     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #     proxy_set_header X-Forwarded-Proto $scheme;
    #     proxy_buffering off;
    #     proxy_cookie_path /guacamole/ /remote/;
    #     client_max_body_size 100M;
    #     access_log off;
    # }
}
"""