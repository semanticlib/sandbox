"""SSH key generation service for VM instances"""
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Base directory for storing instance SSH keys
INSTANCES_BASE_DIR = Path("_instances").resolve()


def _safe_instance_path(name: str, base_path: str = "_instances") -> Path:
    """
    Safely resolve an instance directory path, preventing path traversal.
    
    Args:
        name: Instance name (validated)
        base_path: Base directory path
        
    Returns:
        Resolved Path within allowed directory
        
    Raises:
        ValueError: If path would escape allowed directory
    """
    # Reject dangerous characters before processing
    if not name or any(c in name for c in ['/', '\\', '..', '~', '$']):
        raise ValueError("Invalid instance name: contains forbidden characters")
    
    # Resolve base path
    base = Path(base_path).resolve()
    
    # Construct and resolve the full path
    full_path = (base / name).resolve()
    
    # Verify the path is within the base directory
    try:
        full_path.relative_to(base)
    except ValueError:
        raise ValueError("Invalid instance name: path traversal detected")
    
    return full_path


def generate_ed25519_keypair():
    """
    Generate a new ED25519 key pair.
    
    Returns:
        tuple: (private_key_pem, public_key_pem)
    """
    # Generate private key
    private_key = Ed25519PrivateKey.generate()
    
    # Serialize private key (PEM format)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Serialize public key (OpenSSH format for cloud-init)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    ).decode('utf-8')
    
    return private_pem, public_pem


def save_instance_keys(vm_name: str, private_key: str, public_key: str, base_path: str = "_instances"):
    """
    Save SSH keys for a VM instance.

    Args:
        vm_name: Name of the VM instance
        private_key: Private key PEM string
        public_key: Public key OpenSSH string
        base_path: Base directory for storing keys
    """
    # Safely resolve path (prevents path traversal)
    instance_dir = _safe_instance_path(vm_name, base_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    # Save private key
    private_key_path = instance_dir / "id_ed25519"
    with open(private_key_path, 'w') as f:
        f.write(private_key)
    os.chmod(private_key_path, 0o600)  # Restrictive permissions

    # Save public key
    public_key_path = instance_dir / "id_ed25519.pub"
    with open(public_key_path, 'w') as f:
        f.write(public_key)
    os.chmod(public_key_path, 0o644)

    return {
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "instance_dir": str(instance_dir)
    }


def get_instance_keys(vm_name: str, base_path: str = "_instances"):
    """
    Get SSH keys for a VM instance.

    Args:
        vm_name: Name of the VM instance
        base_path: Base directory where keys are stored

    Returns:
        dict: {'private_key': str, 'public_key': str} or None if not found
    """
    try:
        instance_dir = _safe_instance_path(vm_name, base_path)
    except ValueError:
        return None
        
    private_key_path = instance_dir / "id_ed25519"
    public_key_path = instance_dir / "id_ed25519.pub"

    if not private_key_path.exists() or not public_key_path.exists():
        return None

    with open(private_key_path, 'r') as f:
        private_key = f.read()

    with open(public_key_path, 'r') as f:
        public_key = f.read()

    return {
        "private_key": private_key,
        "public_key": public_key
    }


def generate_and_save_keys(vm_name: str, base_path: str = "_instances"):
    """
    Generate a new key pair and save it for a VM instance.
    
    Args:
        vm_name: Name of the VM instance
        base_path: Base directory for storing keys
    
    Returns:
        dict: {'private_key': str, 'public_key': str, 'paths': dict}
    """
    # Generate key pair
    private_key, public_key = generate_ed25519_keypair()
    
    # Save keys
    paths = save_instance_keys(vm_name, private_key, public_key, base_path)
    
    return {
        "private_key": private_key,
        "public_key": public_key,
        "paths": paths
    }
