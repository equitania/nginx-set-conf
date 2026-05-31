"""
Default SSL reject template — catches requests with unknown SNI.

This template is deployed as `00-default.conf` so nginx loads it before any
domain-specific config. It acts as the explicit `default_server` on port 80
and 443 and returns `444` (connection closed without response) for every
request whose Host header or SNI does not match any other server_name.

Why this matters:
    Without an explicit default_server, nginx picks the first matching server
    block as fallback. When multiple vhosts listen on `0.0.0.0:443` and the
    SNI does not match any of them, the client receives the certificate of
    whatever block nginx evaluated first — which is both wrong and a security
    incident waiting to happen (bad-cert browser warnings, potential phishing
    surface, accidental information disclosure).

The self-signed cert at the paths below is only used for the initial TLS
handshake on unmatched SNI; the connection is reset immediately via `return
444` before any application data is exchanged. The cert is intentionally
untrusted and must never be used as a real cert.
"""

TEMPLATE = """# Default SSL reject — catches unknown SNI / Host
# 31.05.2026
#
# Deploy as /etc/nginx/conf.d/00-default.conf (alphabetical ordering ensures
# nginx loads it before domain-specific configs, so it wins the default_server
# election).
#
# For every request whose Host header or SNI does not match any other server
# block, this block closes the connection with HTTP 444. That prevents nginx
# from falling back to the first domain-specific server block and leaking its
# certificate.

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;

    # Self-signed sacrificial cert — never presented to legitimate clients.
    # Generate via: nginx-set-conf --setup_default
    ssl_certificate /etc/nginx/ssl/default.crt;
    ssl_certificate_key /etc/nginx/ssl/default.key;

    # Close the connection the moment the TLS handshake is done.
    return 444;
}

server {
    # QUIC/HTTP3 catch-all — mirrors the TCP 443 catch-all above for UDP/443.
    #
    # SAFETY NOTE: wildcard listen (no IP prefix) + default_server + reuseport
    # is intentional and correct here. This IS the explicit default_server for
    # QUIC; it does not introduce SNI fallback — it IS the fallback (returns 444).
    # Vhost configs must omit reuseport on their QUIC listen lines because this
    # block already claims the UDP/443 socket (_quic_reuseport_already_claimed
    # detects this at deploy time and suppresses reuseport in vhost configs).
    listen 443 quic default_server reuseport;
    listen [::]:443 quic default_server reuseport;
    server_name _;

    ssl_certificate /etc/nginx/ssl/default.crt;
    ssl_certificate_key /etc/nginx/ssl/default.key;

    # Drop QUIC connections for unknown SNI before any data is exchanged.
    return 444;
}
"""
