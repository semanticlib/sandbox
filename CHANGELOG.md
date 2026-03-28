# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Classroom Management** - Create reusable configurations with predefined images, LXD profiles, and SSH templates
- **LXD Profile Management** - Full CRUD UI for managing LXD profiles with CPU, RAM, disk, and cloud-init settings
- **Container Support** - Bulk creation now supports both VMs and containers with density-aware resource checks
- **Over-commit Option** - Allow resource over-commitment for high-density container deployments
- **Instance Type Display** - Shows selected instance type (VM/Container) in creation forms
- **Help Links** - Added informational links for LXD container vs VM selection

### Changed
- **Refactored Settings** - Merged VM/Container defaults and SSH templates into unified Classroom model
- **Cloud-init Templates** - Separate default templates for VMs (with swap) and containers (with MOTD)
- **Pre-flight Checks** - Container density factor (4x) applied for more accurate resource estimation
- **Delete Confirmations** - Modal dialogs for deleting classrooms and profiles (consistent with dashboard)
- **Profile Protection** - Cannot delete LXD profiles in use by classrooms or the 'default' profile
- **Username Required** - Default username is now mandatory in classroom configuration

### Removed
- **Swap Setting** - Removed dedicated swap field; swap now configured exclusively via cloud-init templates
- **Standalone Settings** - VM defaults, container defaults, and connection templates tabs removed from Settings

### Security
- **Profile Deletion Protection** - Application-level foreign key constraint prevents deleting profiles in use


## [v0.2.0] - 2026-03-25

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

### Security
- Added password strength requirements (8+ chars, mixed case, numbers, special chars)
- Rate limiting on login and setup endpoints

## [0.1.0] - 2026-03-23

### Added
- Initial release
- LXD VM and container management
- Bulk operations (create, start, stop, delete)
- SSH ProxyJump support
- Web-based dashboard
- Dark mode
