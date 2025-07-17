# nginx-set-conf

[🇬🇧 English Version](#english-version) | [🇩🇪 Deutsche Version](#deutsche-version)

---

## 🇬🇧 English Version

A simple Python library that helps you create nginx configurations for different Docker-based applications with nginx as reverse proxy, including advanced configuration verification and synchronization features.

### Features

- **Template-based configuration**: Support for 15+ pre-built templates
- **SSL/TLS support**: Automatic Let's Encrypt integration
- **Configuration verification**: Check consistency between local and server files
- **Interactive synchronization**: Sync configurations between local and server
- **Backup functionality**: Automatic backup of server configurations
- **Dry run mode**: Test configurations without applying changes
- **PDF MIME-Type optimization**: Enhanced PDF handling for Odoo applications

### Installation

#### Requirements

- Python (>= 3.8)
- click (>= 8.1.3)
- PyYAML (>= 5.4.1)

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
- `--sync_config` - Interactive sync of configuration files
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

### Configuration Verification and Synchronization

#### 1. Configuration Verification (`--verify_config`)

Check consistency between local template files and installed server configurations:

```bash
nginx-set-conf --verify_config
```

**Verified Files:**
- `/etc/nginx/nginx.conf` ↔ `yaml_examples/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf` ↔ `yaml_examples/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf` ↔ `yaml_examples/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf` ↔ `yaml_examples/nginxconfig.io/ssl_stapling.conf`

**Output:**
- ✓ CONSISTENT: Files are identical
- ✗ INCONSISTENT: Files differ or are missing
- Detailed information about missing files or differences

#### 2. Interactive Synchronization (`--sync_config`)

Enable interactive synchronization of configuration files:

```bash
nginx-set-conf --sync_config
```

**Synchronization Options:**
1. **Local → Server**: Copy local files to server
2. **Server → Local**: Copy server files to local
3. **Cancel**: Abort operation

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

### Practical Usage Scenarios

#### Scenario 1: Consistency Check Before Deployment

```bash
# Check before deployment
nginx-set-conf --verify_config

# If inconsistencies found: Create backup
nginx-set-conf --backup_config

# Then synchronize
nginx-set-conf --sync_config
```

#### Scenario 2: Server Setup Adoption

```bash
# Backup current server configuration
nginx-set-conf --backup_config

# Sync local templates to server
nginx-set-conf --sync_config
# Choose option 1: Local → Server

# Verify result
nginx-set-conf --verify_config
```

#### Scenario 3: Update Local Development Environment

```bash
# Adopt server configuration to local environment
nginx-set-conf --sync_config
# Choose option 2: Server → Local

# Confirm consistency
nginx-set-conf --verify_config
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
# Backup + Verification + Sync in one workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config && nginx-set-conf --sync_config
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
- **Backup-first approach**: Backup recommended before each synchronization
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
- **Konfigurationsverifikation**: Konsistenzprüfung zwischen lokalen und Server-Dateien
- **Interaktive Synchronisation**: Synchronisation von Konfigurationen zwischen lokal und Server
- **Backup-Funktionalität**: Automatische Sicherung von Server-Konfigurationen
- **Dry-Run-Modus**: Konfigurationen testen ohne Änderungen anzuwenden
- **PDF MIME-Type-Optimierung**: Verbesserte PDF-Behandlung für Odoo-Anwendungen

### Installation

#### Anforderungen

- Python (>= 3.8)
- click (>= 8.1.3)
- PyYAML (>= 5.4.1)

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

- `--verify_config` - Konsistenz zwischen lokalen und Server-Konfigurationsdateien prüfen
- `--sync_config` - Interaktive Synchronisation von Konfigurationsdateien
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

### Konfigurationsverifikation und Synchronisation

#### 1. Konfigurationsverifikation (`--verify_config`)

Konsistenz zwischen lokalen Template-Dateien und installierten Server-Konfigurationen prüfen:

```bash
nginx-set-conf --verify_config
```

**Überprüfte Dateien:**
- `/etc/nginx/nginx.conf` ↔ `yaml_examples/nginx.conf`
- `/etc/nginx/nginxconfig.io/general.conf` ↔ `yaml_examples/nginxconfig.io/general.conf`
- `/etc/nginx/nginxconfig.io/security.conf` ↔ `yaml_examples/nginxconfig.io/security.conf`
- `/etc/nginx/nginxconfig.io/ssl_stapling.conf` ↔ `yaml_examples/nginxconfig.io/ssl_stapling.conf`

**Ausgabe:**
- ✓ CONSISTENT: Dateien sind identisch
- ✗ INCONSISTENT: Dateien unterscheiden sich oder fehlen
- Detaillierte Informationen über fehlende Dateien oder Unterschiede

#### 2. Interaktive Synchronisation (`--sync_config`)

Interaktive Synchronisation von Konfigurationsdateien ermöglichen:

```bash
nginx-set-conf --sync_config
```

**Synchronisationsoptionen:**
1. **Local → Server**: Lokale Dateien auf Server kopieren
2. **Server → Local**: Server-Dateien zu lokalen Dateien kopieren
3. **Cancel**: Vorgang abbrechen

**Sicherheitsfeatures:**
- Bestätigung vor Überschreibung von Dateien
- Automatische Verzeichniserstellung
- Fehlerbehandlung bei Zugriffsproblemen

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

# Dann synchronisieren
nginx-set-conf --sync_config
```

#### Szenario 2: Server-Setup übernehmen

```bash
# Aktuelle Server-Konfiguration sichern
nginx-set-conf --backup_config

# Lokale Templates auf Server synchronisieren
nginx-set-conf --sync_config
# Option 1 wählen: Local → Server

# Ergebnis überprüfen
nginx-set-conf --verify_config
```

#### Szenario 3: Lokale Entwicklungsumgebung aktualisieren

```bash
# Server-Konfiguration in lokale Umgebung übernehmen
nginx-set-conf --sync_config
# Option 2 wählen: Server → Local

# Konsistenz bestätigen
nginx-set-conf --verify_config
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
# Backup + Verifikation + Sync in einem Workflow
nginx-set-conf --backup_config && nginx-set-conf --verify_config && nginx-set-conf --sync_config
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