"""Input validation utilities"""
import re
from typing import Tuple, Optional


# Instance name pattern: alphanumeric, hyphens, underscores only
# Must start with letter, 1-63 characters (LXD limitation)
INSTANCE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,62}$')

# Username pattern: alphanumeric, hyphens, underscores only
# 1-32 characters
USERNAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,31}$')


def validate_instance_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an instance name for LXD.
    
    Args:
        name: Instance name to validate
        
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not name:
        return False, "Instance name is required"
    
    if not isinstance(name, str):
        return False, "Instance name must be a string"
    
    if len(name) < 1:
        return False, "Instance name is too short (minimum 1 character)"
    
    if len(name) > 63:
        return False, "Instance name is too long (maximum 63 characters)"
    
    if not INSTANCE_NAME_PATTERN.match(name):
        return False, (
            "Instance name must start with a letter and contain only "
            "letters, numbers, hyphens, and underscores"
        )
    
    # Check for path traversal attempts
    if '..' in name or '/' in name or '\\' in name:
        return False, "Instance name contains invalid characters"
    
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a username for VM login.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not username:
        return False, "Username is required"
    
    if not isinstance(username, str):
        return False, "Username must be a string"
    
    if len(username) < 1:
        return False, "Username is too short (minimum 1 character)"
    
    if len(username) > 32:
        return False, "Username is too long (maximum 32 characters)"
    
    if not USERNAME_PATTERN.match(username):
        return False, (
            "Username must start with a letter and contain only "
            "letters, numbers, hyphens, and underscores"
        )
    
    return True, None


def validate_positive_integer(value: any, field_name: str, 
                               min_val: int = 1, max_val: int = None) -> Tuple[bool, Optional[str]]:
    """
    Validate a positive integer value.
    
    Args:
        value: Value to validate
        field_name: Name of the field (for error messages)
        min_val: Minimum allowed value
        max_val: Maximum allowed value (optional)
        
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if value is None:
        return False, f"{field_name} is required"
    
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return False, f"{field_name} must be a number"
    
    if int_value < min_val:
        return False, f"{field_name} must be at least {min_val}"
    
    if max_val is not None and int_value > max_val:
        return False, f"{field_name} must be at most {max_val}"
    
    return True, None
