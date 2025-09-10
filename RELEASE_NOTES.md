# RELEASE NOTES

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