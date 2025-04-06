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

# Replace cache paths to avoid conflicts
def replace_cache_path(template, service_name):
    """Replace the cache path in a template with a unique path based on service name.
    
    Args:
        template (str): The nginx config template
        service_name (str): Name of the service to create unique path
        
    Returns:
        str: Template with updated cache path
    """
    return template.replace(
        'proxy_cache_path /tmp', 
        f'proxy_cache_path /var/cache/nginx/{service_name}'
    )

# Weitere Templates hier hinzufügen, wenn sie erstellt wurden

# Dictionary mit allen Templates für einfachen Zugriff
TEMPLATES = {
    "ngx_code_server": replace_cache_path(CODE_SERVER_TEMPLATE, "code_server"),
    "ngx_fast_report": replace_cache_path(FAST_REPORT_TEMPLATE, "fast_report"),
    "ngx_nextcloud": replace_cache_path(NEXTCLOUD_TEMPLATE, "nextcloud"),
    "ngx_portainer": replace_cache_path(PORTAINER_TEMPLATE, "portainer"),
    "ngx_odoo_http": replace_cache_path(ODOO_HTTP_TEMPLATE, "odoo_http"),
    "ngx_odoo_ssl": replace_cache_path(ODOO_SSL_TEMPLATE, "odoo_ssl"),
    "ngx_pgadmin": replace_cache_path(PGADMIN_TEMPLATE, "pgadmin"),
    "ngx_pwa": replace_cache_path(PWA_TEMPLATE, "pwa"),
    "ngx_mailpit": replace_cache_path(MAILPIT_TEMPLATE, "mailpit"),
    "ngx_redirect": replace_cache_path(REDIRECT_TEMPLATE, "redirect"),
    "ngx_redirect_ssl": replace_cache_path(REDIRECT_SSL_TEMPLATE, "redirect_ssl"),
    "ngx_n8n": replace_cache_path(N8N_TEMPLATE, "n8n"),
    "ngx_kasm": replace_cache_path(KASM_TEMPLATE, "kasm"),
    "ngx_qdrant": replace_cache_path(QDRANT_TEMPLATE, "qdrant"),
    # Weitere Templates hier hinzufügen, wenn sie erstellt wurden
}

def get_config_template(config_template_name):
    """
    Get template by name.
    
    Args:
        config_template_name (str): Name of the template to retrieve
        
    Returns:
        str: Template content or empty string if not found
    """
    if config_template_name in TEMPLATES:
        return TEMPLATES[config_template_name]
    else:
        return "" 