# RELEASE NOTES

## Version 1.9.1 (26.02.2026)

### Fixed
- **[FIX]** Fix proxy_pass/grpc_pass directives: revert from public IP placeholder (`ip.ip.ip.ip`) back to loopback default (`127.0.0.1`)
  - Previous IPv6 commit incorrectly routed proxy_pass to the server's public IP instead of localhost

### Added
- **[ADD]** New `--backend_ip` CLI option for configurable proxy_pass target (default: `127.0.0.1`)
  - `{{BACKEND_IP}}` placeholder in all 16 templates
  - Support via YAML configuration: `backend_ip: "::1"` for IPv6 loopback backends
  - IPv6 addresses automatically formatted with brackets: `[::1]`
  - Validation via `validators.py` when `backend_ip` is provided

### Changed
- **[CHG]** Remove incorrect Dual-Stack IPv4/IPv6 documentation sections from README
- **[CHG]** Update IPv6 Support documentation to reference `--backend_ip` parameter
- **[CHG]** `ip` parameter no longer replaces values in proxy_pass directives (only used for listen/upstream)

## Version 1.9.0 (18.02.2026)

### New Features
- **[ADD]** IPv6 support for `--ip` parameter in all 15 templates
  - Automatic bracket formatting for IPv6 addresses in `proxy_pass`/`grpc_pass` URLs
  - `_format_ip_for_nginx()` helper for transparent IPv4/IPv6 handling
  - Example: `--ip ::1` → `proxy_pass http://[::1]:8069`
  - Full backward compatibility with IPv4 addresses

### Security Hardening
- **[CHG]** Eliminate all `os.system()` shell injection vectors in utils.py (15+ instances)
- **[CHG]** Replace sed-based config manipulation with in-memory Python string operations
- **[CHG]** Replace bare `except` clauses with specific exception handling
- **[CHG]** Replace debug `print()` calls with proper logging
- **[ADD]** Comprehensive input validation module (`validators.py`)

### Build System
- **[CHG]** Migrate from setuptools/setup.py to hatchling/pyproject.toml
- **[CHG]** Remove redundant `requirements.txt` and `requirements-dev.txt` (single source: `pyproject.toml`)
- **[CHG]** Consolidate flake8+black+isort into ruff for linting and formatting
- **[CHG]** Update pre-commit hooks (ruff, bandit, mypy)

### Tests
- **[ADD]** 104 tests covering validators, utils, and templates
  - 88 base tests for security hardening and validation
  - 16 additional tests for IPv6 formatting, integration, and regression

## Version 1.8.0 (10.09.2025)

### Breaking Changes
- **[CHG]** Removed `ngx_` prefix from all template names for simpler usage
  - Old: `nginx-set-conf --config_template ngx_odoo_ssl`
  - New: `nginx-set-conf --config_template odoo_ssl`
  - Backward compatibility maintained: old names still work

### Improvements
- **[CHG]** Simplified template naming convention
- **[CHG]** Updated all documentation and examples
- **[CHG]** Maintained backward compatibility for existing scripts

## Version 1.7.0 (10.09.2025)

### New Features
- **[ADD]** Apache Guacamole nginx template with optimized WebSocket support
  - Extended timeouts for long RDP/SSH/VNC sessions (3600s)
  - Proper WebSocket header configuration for real-time communication
  - Increased file upload limits (100MB) for RDP/SSH file transfers
  - Disabled buffering for optimal performance
  - Cookie path adjustment for Guacamole routing
  - Support for alternative path configurations
  - Optimized for remote desktop access protocols

### Template Features
- Full SSL/HTTP2 support
- WebSocket connection upgrade mapping
- Extended proxy timeouts for persistent connections
- Real-time communication without buffering
- Large file transfer support
- Performance optimizations for remote desktop protocols

### Configuration
Default configuration uses port 8080 and routes to `/guacamole/` path. The template automatically handles:
- WebSocket protocol upgrades
- Connection persistence for long sessions
- File transfers via remote protocols
- Cookie path adjustments

## Version 1.6.1 (2025)
- **[ADD]** IP access restrictions feature
- Enhanced security with IP-based access control

## Version 1.6.0 (2025)
- **[ADD]** IP access restrictions feature v1.6.0

## Version 1.5.4 (2024)
- **[FIX]** Use embedded templates instead of local files
- **[DOC]** Update CLAUDE.md for embedded templates