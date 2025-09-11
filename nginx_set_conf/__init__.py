"""
nginx-set-conf - Ein Werkzeug zur Verwaltung von Nginx-Konfigurationen
"""

__version__ = '1.8.0'

from . import config_templates, utils

def replace_cache_path(template, service_name, domain=None):
    """Replace the cache path in a template with a unique path based on service name and domain.
    Also replace the zone name to be unique for each service.
    Also replace the limit_req_zone name to be unique per service.
    
    Args:
        template (str): The nginx config template
        service_name (str): Name of the service for unique path and zone
        domain (str, optional): Domain name to ensure unique cache paths when 
                               multiple instances of the same service are running
        
    Returns:
        str: Template with updated cache path and zone name
    """
    import re
    
    # If domain is provided, create a unique identifier using domain
    if domain:
        # Convert domain to a valid directory name by replacing dots with underscores
        domain_id = domain.replace('.', '_')
        unique_id = f"{service_name}_{domain_id}"
    else:
        unique_id = service_name
    
    # Create unique names based on the service and optional domain
    # Use different suffixes for cache and rate limiting to avoid conflicts
    cache_zone_name = f"{unique_id}_cache"
    rate_limit_zone_name = f"{unique_id}_ratelimit"
    
    # First replace the cache path
    updated_template = template.replace(
        'proxy_cache_path /tmp', 
        f'proxy_cache_path /var/cache/nginx/{unique_id}'
    )
    
    # Then specifically replace the keys_zone parameter in proxy_cache_path directives
    updated_template = re.sub(
        r'(proxy_cache_path\s+[^\s]+\s+[^;]*keys_zone=)[^\s:]+:', 
        f'\\1{cache_zone_name}:',
        updated_template
    )
    
    # Use regex to properly replace the limit_req_zone with size intact
    # Example: limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m rate=500r/m;
    # Changed to: limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=service_name_ratelimit:16m rate=500r/m;
    limit_req_pattern = r'(limit_req_zone\s+\$binary_remote_addr\$http_x_forwarded_for\s+zone=)[^\s:]+:(\d+[kKmMgG])\s+rate=(\d+[rR]/[mshd]);'
    
    def replace_limit_req(match):
        prefix = match.group(1)  # The part before the zone name
        size = match.group(2)    # Captures the size (e.g., '16m')
        rate = match.group(3)    # Captures the rate (e.g., '500r/m')
        return f'{prefix}{rate_limit_zone_name}:{size} rate={rate};'
    
    updated_template = re.sub(limit_req_pattern, replace_limit_req, updated_template)
    
    # Also replace any references to the zone in limit_req directives
    # Example: limit_req zone=iprl burst=500 nodelay;
    # Changed to: limit_req zone=service_name_ratelimit burst=500 nodelay;
    updated_template = re.sub(
        r'(limit_req\s+zone=)[^\s;]+', 
        f'\\1{rate_limit_zone_name}', 
        updated_template
    )
    
    return updated_template
