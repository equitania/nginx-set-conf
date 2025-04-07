"""
Nginx configuration templates for various services.

This module contains predefined Nginx configuration templates for different
services like code-server, FastReport, MailPit, NextCloud, Odoo, pgAdmin4,
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
    - ngx_supabase: Supabase database server with SSL/http2

Note: This module is deprecated and will be removed in a future version.
      Please use nginx_set_conf.templates.all_templates instead.
"""

# Import from the new module structure
from nginx_set_conf.templates.all_templates import get_config_template as all_get_config_template

# For backward compatibility - these templates are pre-rendered
# They should not be used for the final configuration
config_template_dict = {
    "ngx_code_server": all_get_config_template("ngx_code_server"),
    "ngx_fast_report": all_get_config_template("ngx_fast_report"),
    "ngx_nextcloud": all_get_config_template("ngx_nextcloud"),
    "ngx_portainer": all_get_config_template("ngx_portainer"),
    "ngx_odoo_http": all_get_config_template("ngx_odoo_http"),
    "ngx_odoo_ssl": all_get_config_template("ngx_odoo_ssl"),
    "ngx_pgadmin": all_get_config_template("ngx_pgadmin"),
    "ngx_pwa": all_get_config_template("ngx_pwa"),
    "ngx_mailpit": all_get_config_template("ngx_mailpit"),
    "ngx_redirect": all_get_config_template("ngx_redirect"),
    "ngx_redirect_ssl": all_get_config_template("ngx_redirect_ssl"),
    "ngx_n8n": all_get_config_template("ngx_n8n"),
    "ngx_kasm": all_get_config_template("ngx_kasm"),
    "ngx_qdrant": all_get_config_template("ngx_qdrant"),
    "ngx_supabase": all_get_config_template("ngx_supabase"),
}

# Keeping the function for backward compatibility
def get_config_template(config_template_name, domain=None):
    """
    Get template by name (legacy function for backward compatibility).
    
    Args:
        config_template_name (str): Name of the template to retrieve
        domain (str, optional): Domain name to create unique cache paths
        
    Returns:
        str: Template content or empty string if not found
    """
    if domain:
        # If domain is provided, always use the domain-specific path generation
        # This bypasses the pre-rendered templates in config_template_dict
        print(f"Using domain-specific template generation for {domain} with {config_template_name}")
        return all_get_config_template(config_template_name, domain)
    elif config_template_name in config_template_dict:
        print("Warning: Using pre-rendered template without domain specificity")
        return config_template_dict[config_template_name]
    else:
        return ""
