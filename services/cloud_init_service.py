"""Cloud-init template service for VM/container configuration"""
from core.config import settings


# Default cloud-init template for VMs (includes swap configuration)
DEFAULT_CLOUD_INIT_TEMPLATE_VM = """#cloud-config
# Default user configuration
users:
  - name: {username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {public_key}

# Update packages on first boot
package_update: true
package_upgrade: false

# Install additional packages
packages:
  - zip
  - plocate

# Add swap file (2GB)
runcmd:
  - [ fallocate, -l, '2G', /swapfile ]
  - [ chmod, 600, /swapfile ]
  - [ mkswap, /swapfile ]
  - [ swapon, /swapfile ]
  - [ sed, -i, '$a/swapfile none swap sw 0 0', /etc/fstab ]
"""


# Default cloud-init template for Containers (includes MOTD)
DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER = """#cloud-config
# Default user configuration
users:
  - name: {username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {public_key}

# Update packages on first boot
package_update: true
package_upgrade: false

# Install additional packages
packages:
  - zip
  - plocate

# Set custom MOTD
motd: |
  Welcome to the server.
  This message is displayed to all users when they log in.
"""

def get_cloud_init_template(custom_template: str = None, public_key: str = None, username: str = None) -> str:
    """
    Get cloud-init template with placeholders replaced.

    Args:
        custom_template: Custom template from database. If None, uses default VM template.
        public_key: SSH public key to use. If None, uses empty string.
        username: Username for the instance. If None, uses 'ubuntu'.

    Returns:
        Cloud-init template with username and public key replaced
    """
    # Use custom template or default VM template
    template = custom_template if custom_template else DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER

    # Use provided values or defaults
    ssh_public_key = public_key if public_key else ''
    vm_username = username if username else 'ubuntu'

    # Replace placeholders with values
    return template.format(
        username=vm_username,
        public_key=ssh_public_key
    )


def validate_cloud_init_template(template: str) -> tuple[bool, str]:
    """
    Validate that a cloud-init template has the required placeholders.

    Args:
        template: Template string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_placeholders = ['{username}', '{public_key}']
    missing = []

    for placeholder in required_placeholders:
        if placeholder not in template:
            missing.append(placeholder)

    if missing:
        return False, f"Missing placeholders: {', '.join(missing)}"

    return True, ""
