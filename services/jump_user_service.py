"""Jump user management service for SSH ProxyJump"""
import subprocess
import shlex
import re
from typing import Dict
from core.validators import validate_username


# Strict pattern for SSH public keys (OpenSSH format)
SSH_PUBLIC_KEY_PATTERN = re.compile(
    r'^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521)\s+'
    r'[A-Za-z0-9+/=]+\s*'
    r'(\S+)?\s*$'
)


def _validate_ssh_public_key(public_key: str) -> bool:
    """
    Validate SSH public key format.
    
    Args:
        public_key: SSH public key string
        
    Returns:
        True if valid OpenSSH format, False otherwise
    """
    if not public_key or len(public_key) > 4096:
        return False
    
    return bool(SSH_PUBLIC_KEY_PATTERN.match(public_key.strip()))


def _sanitize_username(username: str) -> str:
    """
    Sanitize username for safe use in system commands.
    
    Args:
        username: Username to sanitize
        
    Returns:
        Sanitized username (alphanumeric, hyphens, underscores only)
        
    Raises:
        ValueError: If username contains invalid characters
    """
    is_valid, error = validate_username(username)
    if not is_valid:
        raise ValueError(f"Invalid username: {error}")
    
    # Additional check: only allow alphanumeric, hyphen, underscore
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', username):
        raise ValueError("Username contains invalid characters")
    
    return username


def jump_user_exists(username: str) -> bool:
    """Check if jump user exists on the host system."""
    try:
        # Sanitize username before use
        safe_username = _sanitize_username(username)
        
        result = subprocess.run(
            ['id', safe_username],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (ValueError, subprocess.TimeoutExpired):
        return False
    except Exception:
        return False


def create_jump_user(username: str, public_key: str) -> Dict:
    """
    Create a jump user on the host system for SSH ProxyJump.

    Args:
        username: Username for the jump user (validated)
        public_key: SSH public key in OpenSSH format

    Returns:
        dict with success status and message
    """
    try:
        # Validate inputs
        safe_username = _sanitize_username(username)
        
        if not _validate_ssh_public_key(public_key):
            return {
                "success": False,
                "message": "Invalid SSH public key format"
            }
        
        # Check if user already exists
        if jump_user_exists(username):
            return update_jump_user_keys(username, public_key)

        # Create user with nologin shell (no shell interpolation)
        subprocess.run(
            ['sudo', 'useradd', '-m', '-s', '/usr/sbin/nologin', safe_username],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Create .ssh directory
        subprocess.run(
            ['sudo', 'mkdir', '-p', f'/home/{safe_username}/.ssh'],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Write public key to authorized_keys using tee (safer than echo with shell)
        # Note: We must use shell here for file redirection, but key is validated
        safe_key = shlex.quote(public_key)
        subprocess.run(
            ['sudo', 'sh', '-c', f'echo {safe_key} > /home/{safe_username}/.ssh/authorized_keys'],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Set ownership
        subprocess.run(
            ['sudo', 'chown', '-R', f'{safe_username}:{safe_username}', f'/home/{safe_username}/.ssh'],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Set permissions
        subprocess.run(
            ['sudo', 'chmod', '700', f'/home/{safe_username}/.ssh'],
            check=True,
            capture_output=True,
            timeout=30
        )
        subprocess.run(
            ['sudo', 'chmod', '600', f'/home/{safe_username}/.ssh/authorized_keys'],
            check=True,
            capture_output=True,
            timeout=30
        )

        return {
            "success": True,
            "message": f"Jump user '{safe_username}' created successfully",
            "created": True
        }

    except ValueError as e:
        return {
            "success": False,
            "message": str(e)
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Command timed out"
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        # Sanitize error message to prevent info disclosure
        error_msg = re.sub(r'/home/[^:]+', '/home/[REDACTED]', error_msg)
        return {
            "success": False,
            "message": f"Failed to create jump user: {error_msg}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Failed to create jump user"
        }


def update_jump_user_keys(username: str, public_key: str) -> Dict:
    """
    Update authorized_keys for an existing jump user.

    Args:
        username: Username for the jump user
        public_key: SSH public key to add to authorized_keys

    Returns:
        dict with success status and message
    """
    try:
        # Validate inputs
        safe_username = _sanitize_username(username)
        
        if not _validate_ssh_public_key(public_key):
            return {
                "success": False,
                "message": "Invalid SSH public key format"
            }
        
        # Check if user exists
        if not jump_user_exists(username):
            return {
                "success": False,
                "message": "User does not exist"
            }

        # Check if key already exists (using grep -F for fixed string match)
        safe_key = shlex.quote(public_key)
        result = subprocess.run(
            ['sudo', 'grep', '-q', '-F', public_key, f'/home/{safe_username}/.ssh/authorized_keys'],
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            # Key not found, append it safely
            subprocess.run(
                ['sudo', 'sh', '-c', f'echo {safe_key} >> /home/{safe_username}/.ssh/authorized_keys'],
                check=True,
                capture_output=True,
                timeout=30
            )

        return {
            "success": True,
            "message": "SSH key updated",
            "created": False
        }

    except ValueError as e:
        return {
            "success": False,
            "message": str(e)
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Command timed out"
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": "Failed to update SSH key"
        }
    except Exception:
        return {
            "success": False,
            "message": "Failed to update SSH key"
        }


def delete_jump_user(username: str) -> Dict:
    """
    Delete a jump user from the host system.

    Args:
        username: Username for the jump user

    Returns:
        dict with success status and message
    """
    try:
        # Validate username
        safe_username = _sanitize_username(username)
        
        # Check if user exists
        if not jump_user_exists(username):
            return {
                "success": True,
                "message": "User does not exist"
            }

        # Delete user and home directory
        subprocess.run(
            ['sudo', 'userdel', '-r', safe_username],
            check=True,
            capture_output=True,
            timeout=30
        )

        return {
            "success": True,
            "message": "Jump user deleted"
        }

    except ValueError as e:
        return {
            "success": False,
            "message": str(e)
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Command timed out"
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": "Failed to delete jump user"
        }
    except Exception:
        return {
            "success": False,
            "message": "Failed to delete jump user"
        }
