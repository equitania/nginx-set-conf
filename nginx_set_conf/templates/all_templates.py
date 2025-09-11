"""
Central file for all NGINX configuration templates.

This module imports all individual template modules and provides 
a single dictionary for accessing them.
"""

from nginx_set_conf.templates.code_server import TEMPLATE as CODE_SERVER_TEMPLATE
from nginx_set_conf.templates.fast_report import TEMPLATE as FAST_REPORT_TEMPLATE
from nginx_set_conf.templates.nextcloud import TEMPLATE as NEXTCLOUD_TEMPLATE
from nginx_set_conf.templates.portainer import TEMPLATE as PORTAINER_TEMPLATE
from nginx_set_conf.templates.odoo_http import TEMPLATE as ODOO_HTTP_TEMPLATE
from nginx_set_conf.templates.odoo_ssl import TEMPLATE as ODOO_SSL_TEMPLATE
from nginx_set_conf.templates.pgadmin import TEMPLATE as PGADMIN_TEMPLATE
from nginx_set_conf.templates.pwa import TEMPLATE as PWA_TEMPLATE
from nginx_set_conf.templates.mailpit import TEMPLATE as MAILPIT_TEMPLATE
from nginx_set_conf.templates.redirect import TEMPLATE as REDIRECT_TEMPLATE
from nginx_set_conf.templates.redirect_ssl import TEMPLATE as REDIRECT_SSL_TEMPLATE
from nginx_set_conf.templates.n8n import TEMPLATE as N8N_TEMPLATE
from nginx_set_conf.templates.kasm import TEMPLATE as KASM_TEMPLATE
from nginx_set_conf.templates.qdrant import TEMPLATE as QDRANT_TEMPLATE
from nginx_set_conf.templates.supabase import TEMPLATE as SUPABASE_TEMPLATE
from nginx_set_conf.templates.flowise import TEMPLATE as FLOWISE_TEMPLATE
from nginx_set_conf.templates.guacamole import TEMPLATE as GUACAMOLE_TEMPLATE

# Replace cache paths to avoid conflicts
def replace_cache_path(template, service_name, domain=None):
    """Replace the cache path in a template with a unique path based on service name and domain.
    Also replace the zone name to be unique for each service.
    Also replace the limit_req_zone name to be unique per service.
    
    Args:
        template (str): The nginx config template
        service_name (str): Name of the service to create unique path
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
    cache_zone_name = f"{unique_id}_cache"
    limit_zone_name = f"{unique_id}_limit"
    
    # First replace the cache path
    updated_template = template.replace(
        'proxy_cache_path /tmp', 
        f'proxy_cache_path /var/cache/nginx/{unique_id}'
    )
    
    # Then replace the cache zone name
    updated_template = updated_template.replace(
        'keys_zone=my_cache:',
        f'keys_zone={cache_zone_name}:'
    )
    
    # Use regex to properly replace the limit_req_zone with size intact
    # Example: limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=iprl:16m rate=500r/m;
    # Changed to: limit_req_zone $binary_remote_addr$http_x_forwarded_for zone=service_name_limit:16m rate=500r/m;
    limit_req_pattern = r'limit_req_zone\s+\$binary_remote_addr\$http_x_forwarded_for\s+zone=iprl:(\d+[kKmMgG])\s+rate=(\d+[rR]/[mshd]);'
    
    def replace_limit_req(match):
        size = match.group(1)  # Captures the size (e.g., '16m')
        rate = match.group(2)  # Captures the rate (e.g., '500r/m')
        return f'limit_req_zone $binary_remote_addr$http_x_forwarded_for zone={limit_zone_name}:{size} rate={rate};'
    
    updated_template = re.sub(limit_req_pattern, replace_limit_req, updated_template)
    
    # Also replace any references to the zone in limit_req directives
    # Example: limit_req zone=iprl burst=500 nodelay;
    # Changed to: limit_req zone=service_name_limit burst=500 nodelay;
    updated_template = re.sub(
        r'limit_req\s+zone=iprl(\s+[^;]*);', 
        f'limit_req zone={limit_zone_name}\\1;', 
        updated_template
    )
    
    return updated_template

# Weitere Templates hier hinzufügen, wenn sie erstellt wurden

# Dictionary mit allen Templates für einfachen Zugriff
TEMPLATES = {
    "code_server": replace_cache_path(CODE_SERVER_TEMPLATE, "code_server"),
    "fast_report": replace_cache_path(FAST_REPORT_TEMPLATE, "fast_report"),
    "nextcloud": replace_cache_path(NEXTCLOUD_TEMPLATE, "nextcloud"),
    "portainer": replace_cache_path(PORTAINER_TEMPLATE, "portainer"),
    "odoo_http": replace_cache_path(ODOO_HTTP_TEMPLATE, "odoo_http"),
    "odoo_ssl": replace_cache_path(ODOO_SSL_TEMPLATE, "odoo_ssl"),
    "pgadmin": replace_cache_path(PGADMIN_TEMPLATE, "pgadmin"),
    "pwa": replace_cache_path(PWA_TEMPLATE, "pwa"),
    "mailpit": replace_cache_path(MAILPIT_TEMPLATE, "mailpit"),
    "redirect": replace_cache_path(REDIRECT_TEMPLATE, "redirect"),
    "redirect_ssl": replace_cache_path(REDIRECT_SSL_TEMPLATE, "redirect_ssl"),
    "n8n": replace_cache_path(N8N_TEMPLATE, "n8n"),
    "kasm": replace_cache_path(KASM_TEMPLATE, "kasm"),
    "qdrant": replace_cache_path(QDRANT_TEMPLATE, "qdrant"),
    "supabase": replace_cache_path(SUPABASE_TEMPLATE, "supabase"),
    "flowise": replace_cache_path(FLOWISE_TEMPLATE, "flowise"),
    "guacamole": replace_cache_path(GUACAMOLE_TEMPLATE, "guacamole"),
    # Weitere Templates hier hinzufügen, wenn sie erstellt wurden
}

def get_config_template(config_template_name, domain=None):
    """
    Get template by name.
    
    Args:
        config_template_name (str): Name of the template to retrieve
        domain (str, optional): Domain name to create unique cache paths
        
    Returns:
        str: Template content or empty string if not found
    """
    if config_template_name in TEMPLATES:
        # Get the base template
        base_template = TEMPLATES[config_template_name]
        
        # If domain is provided, create a domain-specific version
        if domain:
            # Service name is already clean without ngx_ prefix
            service_name = config_template_name
            return replace_cache_path(base_template, service_name, domain)
        
        return base_template
    else:
        return "" 