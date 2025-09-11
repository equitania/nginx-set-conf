"""
Nginx configuration templates for various services.

This module contains predefined Nginx configuration templates for different
services like code-server, FastReport, MailPit, NextCloud, Odoo, pgAdmin4,
Portainer, and PWA. Each template includes SSL/TLS and HTTP/2 configurations
where applicable.

Available templates:
    - code_server: Code-server with SSL/HTTP2
    - fast_report: FastReport with SSL
    - flowise: Flowise AI with SSL/HTTP2
    - guacamole: Apache Guacamole with SSL/HTTP2 and WebSocket
    - kasm: Kasm Workspaces configuration with SSL/http2
    - mailpit: Mailpit with SSL
    - n8n: n8n configuration with SSL/http2
    - nextcloud: NextCloud with SSL
    - odoo_http: Odoo HTTP only
    - odoo_ssl: Odoo with SSL
    - pgadmin: pgAdmin4 with SSL
    - portainer: Portainer with SSL
    - pwa: Progressive Web App with SSL
    - qdrant: Qdrant vector database with SSL/http2 and gRPC support
    - redirect: Domain redirect without SSL
    - redirect_ssl: Domain redirect with SSL
    - supabase: Supabase database server with SSL/http2

Note: This module is deprecated and will be removed in a future version.
      Please use nginx_set_conf.templates.all_templates instead.
"""

# Import from the new module structure
from nginx_set_conf.templates.all_templates import get_config_template as all_get_config_template

# For backward compatibility - these templates are pre-rendered
# They should not be used for the final configuration
# Backward compatibility mapping for old template names with ngx_ prefix
config_template_dict = {
    "ngx_code_server": all_get_config_template("code_server"),
    "ngx_fast_report": all_get_config_template("fast_report"),
    "ngx_flowise": all_get_config_template("flowise"),
    "ngx_guacamole": all_get_config_template("guacamole"),
    "ngx_kasm": all_get_config_template("kasm"),
    "ngx_mailpit": all_get_config_template("mailpit"),
    "ngx_n8n": all_get_config_template("n8n"),
    "ngx_nextcloud": all_get_config_template("nextcloud"),
    "ngx_odoo_http": all_get_config_template("odoo_http"),
    "ngx_odoo_ssl": all_get_config_template("odoo_ssl"),
    "ngx_pgadmin": all_get_config_template("pgadmin"),
    "ngx_portainer": all_get_config_template("portainer"),
    "ngx_pwa": all_get_config_template("pwa"),
    "ngx_qdrant": all_get_config_template("qdrant"),
    "ngx_redirect": all_get_config_template("redirect"),
    "ngx_redirect_ssl": all_get_config_template("redirect_ssl"),
    "ngx_supabase": all_get_config_template("supabase"),
    # New template names without prefix
    "code_server": all_get_config_template("code_server"),
    "fast_report": all_get_config_template("fast_report"),
    "flowise": all_get_config_template("flowise"),
    "guacamole": all_get_config_template("guacamole"),
    "kasm": all_get_config_template("kasm"),
    "mailpit": all_get_config_template("mailpit"),
    "n8n": all_get_config_template("n8n"),
    "nextcloud": all_get_config_template("nextcloud"),
    "odoo_http": all_get_config_template("odoo_http"),
    "odoo_ssl": all_get_config_template("odoo_ssl"),
    "pgadmin": all_get_config_template("pgadmin"),
    "portainer": all_get_config_template("portainer"),
    "pwa": all_get_config_template("pwa"),
    "qdrant": all_get_config_template("qdrant"),
    "redirect": all_get_config_template("redirect"),
    "redirect_ssl": all_get_config_template("redirect_ssl"),
    "supabase": all_get_config_template("supabase"),
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
