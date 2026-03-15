"""
Pattern expansion utility for bulk instance naming.

Supports patterns like:
- vm-{01-05} → vm-01, vm-02, vm-03, vm-04, vm-05
- server-{1-3} → server-1, server-2, server-3
- test-{a-c} → test-a, test-b, test-c
"""
import re
from typing import List


# Pattern: prefix-{start-end} where start/end can be numbers or single letters
PATTERN_REGEX = re.compile(r'^(.*)\{(\d+|\w)-(\d+|\w)\}(.*)$')


def expand_pattern(pattern: str) -> List[str]:
    """
    Expand a pattern into a list of names.
    
    Args:
        pattern: Pattern string like "vm-{01-05}" or "server-{1-3}"
        
    Returns:
        List of expanded names
        
    Raises:
        ValueError: If pattern is invalid
    """
    match = PATTERN_REGEX.match(pattern.strip())
    
    if not match:
        # No pattern detected, return as single name
        return [pattern] if pattern else []
    
    prefix, start, end, suffix = match.groups()
    
    # Try numeric expansion
    if start.isdigit() and end.isdigit():
        start_num = int(start)
        end_num = int(end)
        
        if start_num > end_num:
            raise ValueError(f"Invalid range: {start} > {end}")
        
        if end_num - start_num > 100:
            raise ValueError(f"Range too large: maximum 100 instances")
        
        # Determine zero-padding width from start value
        width = len(start)
        
        return [
            f"{prefix}{str(i).zfill(width)}{suffix}"
            for i in range(start_num, end_num + 1)
        ]
    
    # Try alphabetic expansion (single characters only)
    if len(start) == 1 and len(end) == 1 and start.isalpha() and end.isalpha():
        start_ord = ord(start.lower())
        end_ord = ord(end.lower())
        
        if start_ord > end_ord:
            raise ValueError(f"Invalid range: {start} > {end}")
        
        # Preserve case of start character
        is_upper = start.isupper()
        
        names = []
        for i in range(start_ord, end_ord + 1):
            char = chr(i)
            if is_upper:
                char = char.upper()
            names.append(f"{prefix}{char}{suffix}")
        
        return names
    
    raise ValueError(f"Invalid pattern: range must be numeric or single letters")


def expand_names_input(names_input: str) -> List[str]:
    """
    Expand names from user input (supports multiple patterns, one per line or comma-separated).
    
    Args:
        names_input: User input string (newline or comma-separated)
        
    Returns:
        List of all expanded names
        
    Raises:
        ValueError: If any pattern is invalid
    """
    all_names = []
    
    # Split by newlines or commas
    lines = [line.strip() for line in names_input.replace(',', '\n').split('\n')]
    lines = [line for line in lines if line]  # Remove empty lines
    
    for line in lines:
        expanded = expand_pattern(line)
        all_names.extend(expanded)
    
    return all_names


def has_pattern(text: str) -> bool:
    """
    Check if text contains a pattern.
    
    Args:
        text: Text to check
        
    Returns:
        True if pattern detected, False otherwise
    """
    return bool(PATTERN_REGEX.match(text.strip()))
