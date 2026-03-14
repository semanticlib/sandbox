"""Jump user management service for SSH ProxyJump"""
import subprocess
import os
from core.config import settings


def jump_user_exists(username: str) -> bool:
    """Check if jump user exists on the host system."""
    try:
        result = subprocess.run(
            ['id', username],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def create_jump_user(username: str, public_key: str) -> dict:
    """
    Create a jump user on the host system for SSH ProxyJump.
    
    Args:
        username: Username for the jump user
        public_key: SSH public key to add to authorized_keys
    
    Returns:
        dict with success status and message
    """
    try:
        # Check if user already exists
        if jump_user_exists(username):
            # User exists, just update the authorized_keys
            return update_jump_user_keys(username, public_key)
        
        # Create user with nologin shell
        subprocess.run(
            ['sudo', 'useradd', '-m', '-s', '/usr/sbin/nologin', username],
            check=True,
            capture_output=True
        )
        
        # Create .ssh directory
        subprocess.run(
            ['sudo', 'mkdir', '-p', f'/home/{username}/.ssh'],
            check=True,
            capture_output=True
        )
        
        # Add public key to authorized_keys
        subprocess.run(
            ['sudo', 'sh', '-c', f'echo "{public_key}" > /home/{username}/.ssh/authorized_keys'],
            check=True,
            capture_output=True
        )
        
        # Set ownership
        subprocess.run(
            ['sudo', 'chown', '-R', f'{username}:{username}', f'/home/{username}/.ssh'],
            check=True,
            capture_output=True
        )
        
        # Set permissions
        subprocess.run(
            ['sudo', 'chmod', '700', f'/home/{username}/.ssh'],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['sudo', 'chmod', '600', f'/home/{username}/.ssh/authorized_keys'],
            check=True,
            capture_output=True
        )
        
        return {
            "success": True,
            "message": f"Jump user '{username}' created successfully",
            "created": True
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"Failed to create jump user: {e.stderr.decode() if e.stderr else str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to create jump user: {str(e)}"
        }


def update_jump_user_keys(username: str, public_key: str) -> dict:
    """
    Update authorized_keys for an existing jump user.
    
    Args:
        username: Username for the jump user
        public_key: SSH public key to add to authorized_keys
    
    Returns:
        dict with success status and message
    """
    try:
        # Check if user exists
        if not jump_user_exists(username):
            return {
                "success": False,
                "message": f"User '{username}' does not exist"
            }
        
        # Add public key to authorized_keys (append if key not already present)
        result = subprocess.run(
            ['sudo', 'grep', '-q', '-F', public_key, f'/home/{username}/.ssh/authorized_keys'],
            capture_output=True
        )
        
        if result.returncode != 0:
            # Key not found, append it
            subprocess.run(
                ['sudo', 'sh', '-c', f'echo "{public_key}" >> /home/{username}/.ssh/authorized_keys'],
                check=True,
                capture_output=True
            )
        
        return {
            "success": True,
            "message": f"SSH key updated for user '{username}'",
            "created": False
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"Failed to update SSH key: {e.stderr.decode() if e.stderr else str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to update SSH key: {str(e)}"
        }


def delete_jump_user(username: str) -> dict:
    """
    Delete a jump user from the host system.
    
    Args:
        username: Username for the jump user
    
    Returns:
        dict with success status and message
    """
    try:
        # Check if user exists
        if not jump_user_exists(username):
            return {
                "success": True,
                "message": f"User '{username}' does not exist, nothing to delete"
            }
        
        # Delete user and home directory
        subprocess.run(
            ['sudo', 'userdel', '-r', username],
            check=True,
            capture_output=True
        )
        
        return {
            "success": True,
            "message": f"Jump user '{username}' deleted successfully"
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"Failed to delete jump user: {e.stderr.decode() if e.stderr else str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to delete jump user: {str(e)}"
        }
