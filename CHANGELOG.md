# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pattern-based bulk VM creation (e.g., `vm-{01-05}`)
- Pre-flight resource checks for bulk operations
- Live search for instances table

### Changed
- Moved user info and dark mode toggle to sidebar
- Improved error messages (no internal details exposed)

### Fixed
- Command injection vulnerability in jump user service
- Path traversal in SSH key file operations
- Missing authentication on bulk operation endpoints
- Cookie expiration mismatch (now 1 hour)

### Security
- Added password strength requirements (8+ chars, mixed case, numbers, special chars)
- Rate limiting on login and setup endpoints
- Secure cookie flag for HTTPS
- Input validation on all user-provided data

## [0.1.0] - 2025-01-01

### Added
- Initial release
- LXD VM and container management
- Bulk operations (create, start, stop, delete)
- SSH ProxyJump support
- Web-based dashboard
- Dark mode
