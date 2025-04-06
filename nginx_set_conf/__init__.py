"""
nginx-set-conf - Ein Werkzeug zur Verwaltung von Nginx-Konfigurationen
"""

__version__ = '1.3.4'

from . import config_templates, utils

def replace_cache_path(template, service_name):
    """Replace the cache path in a template with a unique path based on service name.
    Also replace the zone name to be unique for each service.
    
    Args:
        template (str): The nginx config template
        service_name (str): Name of the service for unique path and zone
        
    Returns:
        str: Template with updated cache path and zone name
    """
    # Create a unique zone name based on the service
    zone_name = f"{service_name}_cache"
    
    # First replace the cache path
    updated_template = template.replace(
        'proxy_cache_path /tmp', 
        f'proxy_cache_path /var/cache/nginx/{service_name}'
    )
    
    # Then replace the zone name
    updated_template = updated_template.replace(
        'keys_zone=my_cache:',
        f'keys_zone={zone_name}:'
    )
    
    return updated_template
