"""Cloud-init template service for VM configuration"""
from core.config import settings


# Default cloud-init template
DEFAULT_CLOUD_INIT_TEMPLATE = """#cloud-config
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

# Add swap file
runcmd:
  - [ fallocate, -l, '{swap_size}G', /swapfile ]
  - [ chmod, 600, /swapfile ]
  - [ mkswap, /swapfile ]
  - [ swapon, /swapfile ]
  - [ sed, -i, '$a/swapfile none swap sw 0 0', /etc/fstab ]
"""


def get_cloud_init_template(custom_template: str = None, public_key: str = None, swap_size: int = 2) -> str:
    """
    Get cloud-init template with placeholders replaced.
    
    Args:
        custom_template: Custom template from database. If None, uses default template.
        public_key: SSH public key to use. If None, uses value from settings.
        swap_size: Swap size in GiB. Default is 2.
    
    Returns:
        Cloud-init template with username, public key, and swap size replaced
    """
    template = custom_template if custom_template else DEFAULT_CLOUD_INIT_TEMPLATE
    
    # Use provided public key or fallback to settings
    ssh_public_key = public_key if public_key else settings.ED25519_PUBLIC_KEY
    
    # Replace placeholders with values from settings
    return template.format(
        username=settings.DEFAULT_USERNAME,
        public_key=ssh_public_key,
        swap_size=swap_size
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
