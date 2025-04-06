"""
nginx-set-conf - Ein Werkzeug zur Verwaltung von Nginx-Konfigurationen
"""

__version__ = '1.3.3'

from . import config_templates, utils

def replace_cache_path(template, service_name):
    """Replace the cache path in a template with a unique path based on service name."""
    return template.replace(
        'proxy_cache_path /tmp', 
        f'proxy_cache_path /var/cache/nginx/{service_name}'
    )
