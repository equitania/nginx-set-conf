# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nginx-set-conf is a Python CLI tool that generates nginx reverse proxy configurations for Docker-based applications. It supports SSL/HTTP2 and provides pre-built templates for various services like Odoo, Flowise, Qdrant, n8n, and more.

## Development Setup

```bash
# Create and activate UV environment
cd /Users/picard/gitbase/PyPi-Projects/nginx-set-conf
uv venv && venv+

# Install dependencies
uvpip  # Installs from requirements.txt

# Install package in editable mode
uv pip install -e .
```

## Building and Testing

```bash
# Build package with UV
uv build

# Run CLI directly after setup
nginx-set-conf --help

# Show a template without applying
nginx-set-conf --config_template ngx_odoo_ssl --show_template

# Dry run (test configuration without changes)
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain example.com --port 8069 --cert_name example.com --dry_run
```

## Architecture

### Core Components

1. **CLI Entry Point** (`nginx_set_conf/nginx_set_conf.py`): Processes command-line arguments using Click framework
2. **Template System** (`nginx_set_conf/templates/`): Each template is a Python module with a TEMPLATE string
3. **Template Registry** (`nginx_set_conf/templates/all_templates.py`): Central registry of all available templates
4. **Configuration Engine** (`nginx_set_conf/utils.py`): Main logic for configuration generation and deployment

### Key Design Principles

- **Domain Isolation**: Each domain gets unique cache paths and rate-limiting zones to avoid conflicts
- **Template Modularity**: New services can be added by creating a new template module
- **Placeholder System**: Templates use `{{PLACEHOLDER}}` syntax for dynamic values
- **SSL Integration**: Automatic Let's Encrypt certificate generation when cert_key is not provided

### Configuration Flow

1. User provides configuration via YAML file or command-line arguments
2. Template is loaded from the template registry
3. Placeholders are replaced with actual values (IP, domain, ports, etc.)
4. SSL certificates are created/verified if needed
5. Configuration is written to target path (default: `/etc/nginx/conf.d/`)
6. nginx service is reloaded to apply changes

## Template System

### Adding New Templates

1. Create new Python file in `nginx_set_conf/templates/`
2. Define TEMPLATE string with nginx configuration
3. Import in `all_templates.py` and add to `load_data()` function
4. Use placeholders: `{{PORT}}`, `{{DOMAIN}}`, `{{IP}}`, etc.

### Important Placeholders

- `server.domain.de` → Domain name
- `ip.ip.ip.ip` → Server IP address
- `{{PORT}}` → Primary application port
- `{{POLL_PORT}}` → Secondary port (e.g., Odoo longpolling)
- `{{GRPC_PORT}}` → gRPC port (e.g., Qdrant)
- `zertifikat.crt` → SSL certificate name
- `zertifikat.key` → SSL key name
- `{{AUTH_FILE}}` → htaccess authentication file
- `{{REDIRECT_DOMAIN}}` → Target domain for redirects

### Version 1.4.5 Changes

- Enhanced cache path handling with domain-specific paths
- Prevents cache conflicts between multiple instances
- `replace_cache_path()` function ensures unique paths per domain

## Common Development Tasks

```bash
# Test with YAML configuration
nginx-set-conf --config_path yaml_examples/server_config

# Test specific template with direct parameters
nginx-set-conf --config_template ngx_flowise --ip 127.0.0.1 --domain flowise.local --port 3000 --cert_name flowise.local --dry_run

# Deploy to PyPI (requires credentials)
uv build
twine upload dist/*
```

## Important Files

- `nginx_set_conf/__init__.py`: Contains version and `replace_cache_path()` utility
- `yaml_examples/server_config/config.yaml`: Example configurations for all templates
- `yaml_examples/nginxconfig.io/`: nginx include files (security headers, SSL config, etc.)
- `yaml_examples/nginx.conf`: Base nginx configuration with OCSP stapling disabled by default

## Recent Updates

- OCSP stapling disabled by default to avoid warnings with Let's Encrypt certificates
- All SSL templates now include `nginxconfig.io/ssl_stapling.conf`
- Templates support both self-signed and Let's Encrypt certificates