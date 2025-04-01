"""
Nginx configuration templates for various services.

This module contains predefined Nginx configuration templates for different
services like code-server, FastReport, MailHog, NextCloud, Odoo, pgAdmin4,
Portainer, and PWA. Each template includes SSL/TLS and HTTP/2 configurations
where applicable.

Available templates:
    - ngx_code_server: Code-server with SSL/HTTP2
    - ngx_fast_report: FastReport with SSL
    - ngx_mailpit: Mailpit with SSL
    - ngx_nextcloud: NextCloud with SSL
    - ngx_odoo_http: Odoo HTTP only
    - ngx_odoo_ssl: Odoo with SSL
    - ngx_pgadmin: pgAdmin4 with SSL
    - ngx_portainer: Portainer with SSL
    - ngx_pwa: Progressive Web App with SSL
    - ngx_redirect: Domain redirect without SSL
    - ngx_redirect_ssl: Domain redirect with SSL
    - ngx_n8n: n8n configuration with SSL/http2
    - ngx_kasm: Kasm Workspaces configuration with SSL/http2
    - ngx_qdrant: Qdrant vector database with SSL/http2 and gRPC support

Note: This module is deprecated and will be removed in a future version.
      Please use nginx_set_conf.templates.all_templates instead.
"""

# Import from the new module structure
from nginx_set_conf.templates.all_templates import get_config_template

# For backward compatibility
config_template_dict = {
    "ngx_code_server": get_config_template("ngx_code_server"),
    "ngx_fast_report": get_config_template("ngx_fast_report"),
    "ngx_nextcloud": get_config_template("ngx_nextcloud"),
    "ngx_portainer": get_config_template("ngx_portainer"),
    "ngx_odoo_http": get_config_template("ngx_odoo_http"),
    "ngx_odoo_ssl": get_config_template("ngx_odoo_ssl"),
    "ngx_pgadmin": get_config_template("ngx_pgadmin"),
    "ngx_pwa": get_config_template("ngx_pwa"),
    "ngx_mailpit": get_config_template("ngx_mailpit"),
    "ngx_redirect": get_config_template("ngx_redirect"),
    "ngx_redirect_ssl": get_config_template("ngx_redirect_ssl"),
    "ngx_n8n": get_config_template("ngx_n8n"),
    "ngx_kasm": get_config_template("ngx_kasm"),
    "ngx_qdrant": get_config_template("ngx_qdrant"),
}

# Keeping the function for backward compatibility
def get_config_template(config_template_name):
    """
    Get template by name (legacy function for backward compatibility).
    
    Args:
        config_template_name (str): Name of the template to retrieve
        
    Returns:
        str: Template content or empty string if not found
    """
    if config_template_name in config_template_dict:
        return config_template_dict[config_template_name]
    else:
        return ""
