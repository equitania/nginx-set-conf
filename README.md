# nginx-set-conf

[🇬🇧 English Version](#english-version) | [🇩🇪 Deutsche Version](#deutsche-version)

---

## 🇬🇧 English Version

A simple Python library that helps you create nginx configurations for different Docker-based applications with nginx as reverse proxy, including configuration verification features.

### Features

- **Template-based configuration**: Support for 15+ pre-built templates
- **SSL/TLS support**: Automatic Let's Encrypt integration
- **IP access restrictions**: Optional IP whitelist/blacklist functionality
- **Configuration verification**: Check consistency between local and server files
- **Configuration verification**: Check if required nginx files exist
- **Backup functionality**: Automatic backup of server configurations
- **Dry run mode**: Test configurations without applying changes
- **PDF MIME-Type optimization**: Enhanced PDF handling for Odoo applications
- **Intranet support**: Optional disable domain prefix in listen directives for internal networks

### Installation

#### Requirements

- Python (>= 3.10)
- click (>= 8.2.1)
- PyYAML (>= 6.0.2)

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install nginx-set-conf:

```bash
pip install nginx-set-conf
```

### Usage

#### Basic Usage

```bash
$ nginx-set-conf --help
```

#### Supported Templates

- `ngx_code_server` - Code-server with SSL
- `ngx_fast_report` - FastReport with SSL
- `ngx_flowise` - Flowise AI with SSL/HTTP2
- `ngx_guacamole` - Apache Guacamole with SSL/HTTP2 and WebSocket
- `ngx_kasm` - Kasm Workspaces with SSL/HTTP2
- `ngx_mailpit` - Mailpit with SSL/HTTP2
- `ngx_n8n` - n8n with SSL/HTTP2
- `ngx_nextcloud` - NextCloud with SSL
- `ngx_odoo_http` - Odoo HTTP only
- `ngx_odoo_ssl` - Odoo with SSL
- `ngx_pgadmin` - pgAdmin4 with SSL
- `ngx_portainer` - Portainer with SSL
- `ngx_pwa` - Progressive Web App with SSL
- `ngx_qdrant` - Qdrant vector database with SSL/HTTP2 and gRPC
- `ngx_redirect` - Domain redirect without SSL
- `ngx_redirect_ssl` - Domain redirect with SSL
- `ngx_supabase` - Supabase database server with SSL/HTTP2

#### Configuration Management Options

- `--verify_config` - Check consistency between local and server config files
- `--create_dirs` - Create missing nginx configuration directories
- `--backup_config` - Create backup of current server configuration

### Examples

#### Basic Configuration

```bash
# Using configuration file
nginx-set-conf --config_path server_config

# Direct configuration
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --pollport 8072

# Custom target path
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --target_path /tmp/nginx-test

# Dry run mode
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --dry_run

# With IP access restrictions
nginx-set-conf --config_template ngx_flowise --ip 192.168.1.10 --domain secure-flowise.example.com --port 3000 --cert_name secure-flowise.example.com --allowed_ips "192.168.1.0/24,10.0.0.50,203.0.113.100"

# For intranet systems without domain prefix in listen directives
nginx-set-conf --config_template ngx_odoo_ssl --ip 192.168.1.100 --domain dev01-a.intra.company.local --port 8069 --cert_name dev01-a.intra.company.local --disable_domain_listen
```

#### Template Preview

```bash
# Show template configuration
nginx-set-conf --config_template ngx_odoo_ssl --show_template

# Show Qdrant template
nginx-set-conf --config_template ngx_qdrant --show_template
```

#### Advanced Examples

```bash
# Qdrant with gRPC support
nginx-set-conf --config_template ngx_qdrant --ip 1.2.3.4 --domain vector.example.com --port 6333 --grpcport 6334 --cert_name vector.example.com

# Flowise AI server
nginx-set-conf --config_template ngx_flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com

# Supabase database server
nginx-set-conf --config_template ngx_supabase --ip 1.2.3.4 --domain supabase.example.com --port 8000 --cert_name supabase.example.com
```

### Configuration Verification

#### 1. Configuration File Check (`--verify_config`)

Check if required nginx configuration files exist on the server:

```bash
nginx-set-conf --verify_config
```

**Checked Files:**
- `/etc/nginx/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf`

**Output:**
- ✓ EXISTS: File is present on the server
- ✗ MISSING: File not found
- Shows file path and size for existing files

#### 2. Create Missing Directories (`--create_dirs`)

Create missing nginx configuration directories if needed:

```bash
nginx-set-conf --create_dirs
```

**What it does:**
- Checks for missing files
- Creates `/etc/nginx/nginxconfig.io/` directory if missing
- Useful after fresh nginx installation

**Security Features:**
- Confirmation before overwriting files
- Automatic directory creation
- Error handling for access problems

#### 3. Configuration Backup (`--backup_config`)

Create automatic backups of current server configuration:

```bash
nginx-set-conf --backup_config
```

**Backup Features:**
- Timestamp-based backup folders: `/tmp/nginx_backup/nginx_config_backup_YYYYMMDD_HHMMSS`
- Complete backup of `/etc/nginx/nginx.conf`
- Recursive backup of `nginxconfig.io/` directory
- Logging of all backup operations

### Intranet Configuration (disable_domain_listen)

For intranet systems where nginx requires listen directives without domain prefix:

#### When to Use

Some internal/intranet environments require nginx listen directives without the domain prefix:
- **Standard**: `listen domain.com:443 ssl;`
- **Intranet**: `listen 443 ssl;`

#### Configuration Example

```yaml
intranet-odoo:
  config_template: ngx_odoo_ssl
  ip: 192.168.1.100
  domain: dev01-a.intra.company.local
  port: 8069
  cert_name: dev01-a.intra.company.local
  pollport: 8072
  disable_domain_listen: true  # Remove domain prefix from listen directives
```

#### Command Line Usage

```bash
nginx-set-conf --config_template ngx_odoo_ssl \
  --ip 192.168.1.100 \
  --domain dev01-a.intra.company.local \
  --port 8069 \
  --cert_name dev01-a.intra.company.local \
  --disable_domain_listen
```

#### Effect on Configuration

**Without `disable_domain_listen`:**
```nginx
server {
    listen dev01-a.intra.company.local:80;
    server_name dev01-a.intra.company.local;
}

server {
    listen dev01-a.intra.company.local:443 ssl;
    server_name dev01-a.intra.company.local;
}
```

**With `disable_domain_listen`:**
```nginx
server {
    listen 80;
    server_name dev01-a.intra.company.local;
}

server {
    listen 443 ssl;
    http2 on;
    server_name dev01-a.intra.company.local;
}
```

### IP Access Restrictions

nginx-set-conf supports optional IP-based access control to restrict access to your applications to specific IP addresses or CIDR blocks.

#### CLI Usage

```bash
# Restrict access to specific IPs
nginx-set-conf --config_template ngx_flowise \
  --ip 192.168.1.10 --domain secure.example.com --port 3000 \
  --cert_name secure.example.com \
  --allowed_ips "192.168.1.0/24,10.0.0.50,203.0.113.100"

# Multiple IP formats supported
nginx-set-conf --config_template ngx_odoo_ssl \
  --ip 10.0.0.5 --domain erp.company.com --port 8069 \
  --cert_name erp.company.com --pollport 8072 \
  --allowed_ips "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
```

#### YAML Configuration

```yaml
# Example with IP restrictions
Secure Flowise:
  config_template: ngx_flowise
  ip: 192.168.1.10
  domain: secure-flowise.example.com
  port: 3000
  cert_name: secure-flowise.example.com
  allowed_ips: "192.168.1.0/24,10.0.0.50,203.0.113.100"

# Mixed authentication (IP + htaccess)
Odoo Production:
  config_template: ngx_odoo_ssl
  ip: 10.0.0.5
  domain: erp.company.com
  port: 8069
  cert_name: erp.company.com
  pollport: 8072
  auth_file: /etc/nginx/.htpasswd
  allowed_ips: "192.168.0.0/16,10.0.0.0/8"
```

#### Generated nginx Configuration

When `allowed_ips` is specified, the following directives are automatically added to your nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name secure.example.com;
    
    # IP restrictions
    allow 192.168.1.0/24;
    allow 10.0.0.50;
    allow 203.0.113.100;
    deny all;
    
    # ... rest of configuration
}
```

#### Supported IP Formats

- **Single IP**: `192.168.1.100`
- **CIDR notation**: `192.168.1.0/24`, `10.0.0.0/8`
- **IPv6**: `2001:db8::/32` (if supported by nginx)
- **Multiple entries**: Comma-separated list

#### Security Notes

- IP restrictions are applied at the server block level
- Restrictions work with both SSL and non-SSL templates
- Compatible with existing authentication (`auth_file`)
- Applied before location-specific rules
- Use `deny all` as final rule for security

### Practical Usage Scenarios

#### Scenario 1: Consistency Check Before Deployment

```bash
# Check before deployment
nginx-set-conf --verify_config

# If inconsistencies found: Create backup
nginx-set-conf --backup_config

# If directories missing, create them
nginx-set-conf --create_dirs
```

#### Scenario 2: Server Setup Adoption

```bash
# Backup current server configuration
nginx-set-conf --backup_config

# Create missing directories if needed
nginx-set-conf --create_dirs

# Verify result
nginx-set-conf --verify_config
```

#### Scenario 3: Fresh nginx Installation

```bash
# Check if all required files exist
nginx-set-conf --verify_config

# If directories are missing, create them
nginx-set-conf --create_dirs
```

### SSL Certificate Management

#### Create Let's Encrypt Certificate

```bash
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.example.com
```

#### Install certbot on Debian/Ubuntu

```bash
apt-get install certbot
```

#### Create Authentication File

```bash
# Install htpasswd on Debian/Ubuntu
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htaccess/.htpasswd-user USER
```

### Nginx Template Settings

You can download our optimized settings:
- [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)
- [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)

Based on [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)

### Technical Details

#### Hash-based Verification
- SHA256 hashes for precise file comparisons
- Detection of content, size, and modification time
- Robust error handling for access problems

#### Secure Synchronization
- Explicit user confirmation before overwrites
- Automatic directory creation
- Detailed logging information
- Rollback possibility through backup system

#### Flexible Path Configuration
- Customizable local paths (default: `yaml_examples/`)
- Configurable server paths (default: `/etc/nginx/`)
- Support for different nginx installations

### Advanced Usage

#### Combined Commands
```bash
# Backup + Verification in one workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config
```

#### Combining with Other Options
```bash
# Verification with Dry-Run
nginx-set-conf --verify_config --dry_run
```

### Troubleshooting

#### Common Issues

1. **Permission denied**: Ensure user has write permissions for `/etc/nginx/`
2. **Missing directories**: Tool automatically creates missing directories
3. **Backup storage full**: Remove old backups from `/tmp/nginx_backup/`

#### Logging
All operations are logged to:
- Console: INFO level
- File: `nginx_set_conf.log` (with rotation)

### Security Aspects

- **No automatic changes**: All changes require explicit confirmation
- **Backup-first approach**: Backup recommended before configuration changes
- **Granular control**: Individual files can be identified and handled
- **Error handling**: Robust handling of permission and access problems

### License

This project is licensed under the terms of the **AGPLv3** license.

---

## 🇩🇪 Deutsche Version

Eine einfache Python-Bibliothek, die bei der Erstellung von nginx-Konfigurationen für verschiedene Docker-basierte Anwendungen mit nginx als Reverse-Proxy hilft, einschließlich erweiterten Konfigurationsverifikations- und Synchronisationsfunktionen.

### Funktionen

- **Template-basierte Konfiguration**: Unterstützung für 15+ vorgefertigte Templates
- **SSL/TLS-Unterstützung**: Automatische Let's Encrypt Integration
- **IP-Zugriffsbeschränkungen**: Optionale IP-Whitelist/Blacklist Funktionalität
- **Konfigurationsverifikation**: Konsistenzprüfung zwischen lokalen und Server-Dateien
- **Interaktive Synchronisation**: Synchronisation von Konfigurationen zwischen lokal und Server
- **Backup-Funktionalität**: Automatische Sicherung von Server-Konfigurationen
- **Dry-Run-Modus**: Konfigurationen testen ohne Änderungen anzuwenden
- **PDF MIME-Type-Optimierung**: Verbesserte PDF-Behandlung für Odoo-Anwendungen
- **Intranet-Unterstützung**: Optional Domain-Präfix in Listen-Direktiven für interne Netzwerke deaktivieren

### Installation

#### Anforderungen

- Python (>= 3.10)
- click (>= 8.2.1)
- PyYAML (>= 6.0.2)

Verwenden Sie den Paketmanager [pip](https://pip.pypa.io/en/stable/) zur Installation von nginx-set-conf:

```bash
pip install nginx-set-conf
```

### Verwendung

#### Grundlegende Verwendung

```bash
$ nginx-set-conf --help
```

#### Unterstützte Templates

- `ngx_code_server` - Code-Server mit SSL
- `ngx_fast_report` - FastReport mit SSL
- `ngx_flowise` - Flowise AI mit SSL/HTTP2
- `ngx_guacamole` - Apache Guacamole mit SSL/HTTP2 und WebSocket
- `ngx_kasm` - Kasm Workspaces mit SSL/HTTP2
- `ngx_mailpit` - Mailpit mit SSL/HTTP2
- `ngx_n8n` - n8n mit SSL/HTTP2
- `ngx_nextcloud` - NextCloud mit SSL
- `ngx_odoo_http` - Odoo nur HTTP
- `ngx_odoo_ssl` - Odoo mit SSL
- `ngx_pgadmin` - pgAdmin4 mit SSL
- `ngx_portainer` - Portainer mit SSL
- `ngx_pwa` - Progressive Web App mit SSL
- `ngx_qdrant` - Qdrant Vektordatenbank mit SSL/HTTP2 und gRPC
- `ngx_redirect` - Domain-Weiterleitung ohne SSL
- `ngx_redirect_ssl` - Domain-Weiterleitung mit SSL
- `ngx_supabase` - Supabase Datenbankserver mit SSL/HTTP2

#### Konfigurationsverwaltungsoptionen

- `--verify_config` - Prüfen ob benötigte nginx Konfigurationsdateien existieren
- `--create_dirs` - Fehlende nginx Konfigurationsverzeichnisse erstellen
- `--backup_config` - Backup der aktuellen Server-Konfiguration erstellen

### Beispiele

#### Grundkonfiguration

```bash
# Verwendung von Konfigurationsdatei
nginx-set-conf --config_path server_config

# Direkte Konfiguration
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --pollport 8072

# Benutzerdefinierter Zielpfad
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --target_path /tmp/nginx-test

# Dry-Run-Modus
nginx-set-conf --config_template ngx_odoo_ssl --ip 1.2.3.4 --domain www.example.com --port 8069 --cert_name www.example.com --dry_run
```

#### Template-Vorschau

```bash
# Template-Konfiguration anzeigen
nginx-set-conf --config_template ngx_odoo_ssl --show_template

# Qdrant-Template anzeigen
nginx-set-conf --config_template ngx_qdrant --show_template
```

#### Erweiterte Beispiele

```bash
# Qdrant mit gRPC-Unterstützung
nginx-set-conf --config_template ngx_qdrant --ip 1.2.3.4 --domain vector.example.com --port 6333 --grpcport 6334 --cert_name vector.example.com

# Flowise AI Server
nginx-set-conf --config_template ngx_flowise --ip 1.2.3.4 --domain flowise.example.com --port 3000 --cert_name flowise.example.com

# Supabase Datenbankserver
nginx-set-conf --config_template ngx_supabase --ip 1.2.3.4 --domain supabase.example.com --port 8000 --cert_name supabase.example.com
```

### Konfigurationsverifikation

#### 1. Konfigurationsdatei-Prüfung (`--verify_config`)

Prüfen ob benötigte nginx Konfigurationsdateien auf dem Server existieren:

```bash
nginx-set-conf --verify_config
```

**Geprüfte Dateien:**
- `/etc/nginx/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf`

**Ausgabe:**
- ✓ EXISTS: Datei ist auf dem Server vorhanden
- ✗ MISSING: Datei nicht gefunden
- Zeigt Dateipfad und Größe für existierende Dateien

#### 2. Fehlende Verzeichnisse erstellen (`--create_dirs`)

Fehlende nginx Konfigurationsverzeichnisse bei Bedarf erstellen:

```bash
nginx-set-conf --create_dirs
```

**Was es tut:**
- Prüft auf fehlende Dateien
- Erstellt `/etc/nginx/nginxconfig.io/` Verzeichnis falls fehlend
- Nützlich nach frischer nginx Installation

#### 3. Konfigurationsbackup (`--backup_config`)

Automatische Backups der aktuellen Server-Konfiguration erstellen:

```bash
nginx-set-conf --backup_config
```

**Backup-Funktionen:**
- Zeitstempel-basierte Backup-Ordner: `/tmp/nginx_backup/nginx_config_backup_YYYYMMDD_HHMMSS`
- Vollständige Sicherung von `/etc/nginx/nginx.conf`
- Rekursive Sicherung des `nginxconfig.io/` Verzeichnisses
- Logging aller Backup-Operationen

### Praktische Anwendungsszenarien

#### Szenario 1: Konsistenzprüfung vor Deployment

```bash
# Vor dem Deployment prüfen
nginx-set-conf --verify_config

# Bei Inconsistenzen: Backup erstellen
nginx-set-conf --backup_config

# Bei fehlenden Verzeichnissen erstellen
nginx-set-conf --create_dirs
```

#### Szenario 2: Server-Setup übernehmen

```bash
# Aktuelle Server-Konfiguration sichern
nginx-set-conf --backup_config

# Fehlende Verzeichnisse erstellen falls nötig
nginx-set-conf --create_dirs
# Option 1 wählen: Local → Server

# Ergebnis überprüfen
nginx-set-conf --verify_config
```

#### Szenario 3: Neue nginx Installation prüfen

```bash
# Prüfen ob alle Dateien vorhanden sind
nginx-set-conf --verify_config

# Falls Verzeichnisse fehlen, diese erstellen
nginx-set-conf --create_dirs
```

### SSL-Zertifikatsverwaltung

#### Let's Encrypt Zertifikat erstellen

```bash
certbot certonly --standalone --agree-tos --register-unsafely-without-email -d www.example.com
```

#### certbot auf Debian/Ubuntu installieren

```bash
apt-get install certbot
```

#### Authentifizierungsdatei erstellen

```bash
# htpasswd auf Debian/Ubuntu installieren
apt-get install apache2-utils
htpasswd -c /etc/nginx/.htaccess/.htpasswd-user USER
```

### Nginx-Template-Einstellungen

Sie können unsere optimierten Einstellungen herunterladen:
- [nginx.conf](https://rm.ownerp.io/staff/nginx.conf)
- [nginxconfig.io.zip](https://rm.ownerp.io/staff/nginxconfig.io.zip)

Basierend auf [https://www.digitalocean.com/community/tools/nginx](https://www.digitalocean.com/community/tools/nginx)

### Technische Details

#### Hash-basierte Verifikation
- SHA256-Hashes für präzise Dateivergleiche
- Erkennung von Inhalt, Größe und Änderungszeit
- Robuste Fehlerbehandlung bei Zugriffsproblemen

#### Sichere Synchronisation
- Explizite Benutzerbestätigung vor Überschreibungen
- Automatische Verzeichniserstellung
- Detaillierte Logging-Informationen
- Rollback-Möglichkeit durch Backup-System

#### Flexible Pfad-Konfiguration
- Anpassbare lokale Pfade (Standard: `yaml_examples/`)
- Konfigurierbare Server-Pfade (Standard: `/etc/nginx/`)
- Unterstützung für verschiedene nginx-Installationen

### Erweiterte Nutzung

#### Kombinierte Befehle
```bash
# Backup + Verifikation in einem Workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config
```

#### Mit anderen Optionen kombinieren
```bash
# Verifikation mit Dry-Run
nginx-set-conf --verify_config --dry_run
```

### Fehlerbehebung

#### Häufige Probleme

1. **Berechtigung verweigert**: Sicherstellen, dass der Benutzer Schreibrechte für `/etc/nginx/` hat
2. **Verzeichnisse fehlen**: Tool erstellt automatisch fehlende Verzeichnisse
3. **Backup-Speicher voll**: Alte Backups aus `/tmp/nginx_backup/` entfernen

#### Logging
Alle Operationen werden geloggt in:
- Konsole: INFO-Level
- Datei: `nginx_set_conf.log` (mit Rotation)

### Sicherheitsaspekte

- **Keine automatischen Änderungen**: Alle Änderungen erfordern explizite Bestätigung
- **Backup-First-Ansatz**: Backup vor jeder Synchronisation empfohlen
- **Granulare Kontrolle**: Einzelne Dateien können identifiziert und behandelt werden
- **Fehlerbehandlung**: Robuste Behandlung von Permissions- und Zugriffsproblemen

### Lizenz

Dieses Projekt ist unter den Bedingungen der **AGPLv3**-Lizenz lizenziert.