# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Classroom Management** - Create reusable configurations with predefined images, LXD profiles, and SSH templates
- **Container Support** - Bulk creation now supports both VMs and containers with density-aware resource checks
- **Over-commit Option** - Allow resource over-commitment for high-density container deployments
- **SSH Local Port Forwards** - Configure port forwarding rules (e.g., `8080:localhost:80`) in Classroom settings
- **Cloud-init Validation** - Server-side validation ensures templates have required placeholders (`{username}`, `{public_key}`)

### Changed
- **Removed LXD Profiles** - Eliminated LXD Profile management; cloud-init now stored directly in Classroom model
- **Classroom Model** - Replaced `lxd_profile` and `ssh_config_template` columns with `cloud_init` and `local_forwards`
- **Cloud-init Editor** - Moved cloud-init template editor to Classroom page with type-specific default templates
- **SSH Config Generation** - Uses hard-coded default template; local forwards appended automatically
- **Instance Creation** - Now uses cloud-init from Classroom object instead of LXD profile
- **Resource Defaults** - Hard-coded defaults for CPU (2), RAM (4GB), Disk (20GB) instead of profile-based
- **Code Reuse** - Refactored bulk operations to use shared `wait_for_task()` from instance tasks
- **Code Reuse** - Consolidated classroom validation into single `validateClassroomPayload()` function
- **Form Behavior** - Cloud-init and image fields only reset when instance type changes (not on edit)

### Removed
- **Swap Setting** - Removed dedicated swap field; swap now configured exclusively via cloud-init templates
- **SSH Config Template Editor** - Removed editable SSH config template from Classroom settings

### Fixed
- **Dark Mode** - Fixed select dropdown arrow visibility with custom SVG icon
- **Classroom Edit** - Fixed unwanted reset of cloud-init and image fields when editing

### Security
- **Cloud-init Validation** - Prevents saving templates with missing required placeholders


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
