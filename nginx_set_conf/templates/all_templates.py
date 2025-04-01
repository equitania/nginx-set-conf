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

# Weitere Templates hier hinzufügen, wenn sie erstellt wurden

# Dictionary mit allen Templates für einfachen Zugriff
TEMPLATES = {
    "ngx_code_server": CODE_SERVER_TEMPLATE,
    "ngx_fast_report": FAST_REPORT_TEMPLATE,
    "ngx_nextcloud": NEXTCLOUD_TEMPLATE,
    "ngx_portainer": PORTAINER_TEMPLATE,
    "ngx_odoo_http": ODOO_HTTP_TEMPLATE,
    "ngx_odoo_ssl": ODOO_SSL_TEMPLATE,
    "ngx_pgadmin": PGADMIN_TEMPLATE,
    "ngx_pwa": PWA_TEMPLATE,
    "ngx_mailpit": MAILPIT_TEMPLATE,
    "ngx_redirect": REDIRECT_TEMPLATE,
    "ngx_redirect_ssl": REDIRECT_SSL_TEMPLATE,
    "ngx_n8n": N8N_TEMPLATE,
    "ngx_kasm": KASM_TEMPLATE,
    "ngx_qdrant": QDRANT_TEMPLATE,
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