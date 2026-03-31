"""Tests for cloud-init template service"""
import pytest
from services.cloud_init_service import (
    get_cloud_init_template,
    validate_cloud_init_template,
    DEFAULT_CLOUD_INIT_TEMPLATE_VM,
    DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER
)


class TestGetCloudInitTemplate:
    """Test cloud-init template generation"""

    def test_vm_template_default(self):
        """Test VM template with default values"""
        result = get_cloud_init_template(
            public_key="ssh-ed25519 AAAA...",
            username="ubuntu",
            instance_type="virtual-machine"
        )
        
        assert "ubuntu" in result
        assert "ssh-ed25519 AAAA..." in result
        assert "swapfile" in result  # VM has swap
        assert "motd" not in result  # Container feature

    def test_container_template_default(self):
        """Test Container template with default values"""
        result = get_cloud_init_template(
            public_key="ssh-ed25519 AAAA...",
            username="root",
            instance_type="container"
        )
        
        assert "root" in result
        assert "ssh-ed25519 AAAA..." in result
        assert "motd" in result  # Container has MOTD
        assert "swapfile" not in result  # VM feature

    def test_custom_template(self):
        """Test custom template from LXD profile"""
        custom = """#cloud-config
users:
  - name: {username}
    ssh_authorized_keys:
      - {public_key}
"""
        result = get_cloud_init_template(
            custom_template=custom,
            public_key="ssh-key-123",
            username="testuser",
            instance_type="virtual-machine"
        )
        
        assert "testuser" in result
        assert "ssh-key-123" in result
        assert "swapfile" not in result  # Custom template used

    def test_empty_public_key(self):
        """Test with empty public key"""
        result = get_cloud_init_template(
            public_key="",
            username="ubuntu",
            instance_type="container"
        )
        
        assert "ubuntu" in result
        assert "ssh_authorized_keys:" in result

    def test_default_username(self):
        """Test default username fallback"""
        result = get_cloud_init_template(
            public_key="ssh-key",
            instance_type="virtual-machine"
        )
        
        assert "ubuntu" in result  # Default for VM


class TestValidateCloudInitTemplate:
    """Test cloud-init template validation"""

    def test_valid_template(self):
        """Test valid template with all placeholders"""
        template = """#cloud-config
users:
  - name: {username}
    ssh_authorized_keys:
      - {public_key}
"""
        is_valid, error = validate_cloud_init_template(template)
        
        assert is_valid is True
        assert error == ""

    def test_missing_username(self):
        """Test template missing username placeholder"""
        template = """#cloud-config
users:
  - name: admin
    ssh_authorized_keys:
      - {public_key}
"""
        is_valid, error = validate_cloud_init_template(template)
        
        assert is_valid is False
        assert "{username}" in error

    def test_missing_public_key(self):
        """Test template missing public_key placeholder"""
        template = """#cloud-config
users:
  - name: {username}
    shell: /bin/bash
"""
        is_valid, error = validate_cloud_init_template(template)
        
        assert is_valid is False
        assert "{public_key}" in error

    def test_missing_both_placeholders(self):
        """Test template missing both placeholders"""
        template = """#cloud-config
users:
  - name: admin
    shell: /bin/bash
"""
        is_valid, error = validate_cloud_init_template(template)
        
        assert is_valid is False
        assert "{username}" in error
        assert "{public_key}" in error
