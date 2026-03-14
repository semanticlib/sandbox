"""Simple in-memory rate limiter for login protection"""
import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    """Token bucket rate limiter for brute-force protection"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_attempts: Maximum number of attempts allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, list] = defaultdict(list)

    def is_rate_limited(self, identifier: str) -> bool:
        """
        Check if an identifier (IP or username) is rate limited.

        Args:
            identifier: Unique identifier (e.g., IP address or username)

        Returns:
            True if rate limited, False if request is allowed
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old attempts outside the window
        self._attempts[identifier] = [
            t for t in self._attempts[identifier] if t > window_start
        ]

        # Check if rate limited
        if len(self._attempts[identifier]) >= self.max_attempts:
            return True

        # Record this attempt
        self._attempts[identifier].append(now)
        return False

    def get_retry_after(self, identifier: str) -> int:
        """
        Get seconds until the identifier can retry.

        Args:
            identifier: Unique identifier

        Returns:
            Seconds to wait before retrying
        """
        if not self._attempts[identifier]:
            return 0

        oldest_attempt = min(self._attempts[identifier])
        retry_after = int(oldest_attempt + self.window_seconds - time.time())
        return max(0, retry_after)

    def reset(self, identifier: str):
        """
        Reset attempts for an identifier (e.g., after successful login).

        Args:
            identifier: Unique identifier
        """
        self._attempts[identifier] = []


# Global rate limiter instance for login attempts
login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
