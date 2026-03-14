# Sandbox Manager - Test Suite

## Overview

This test suite provides comprehensive coverage for the Sandbox Manager application, including unit tests, service tests, and integration tests.

## Quick Start

```bash
# Run all tests with coverage
./scripts/test.sh

# Run tests without coverage (faster)
./scripts/test.sh fast

# Run only unit tests
./scripts/test.sh unit
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and utilities
├── unit/                 # Unit tests (fast, isolated)
│   ├── test_security.py  # Password hashing, JWT tokens
│   ├── test_validators.py # Input validation
│   └── test_rate_limiter.py # Rate limiting logic
├── services/             # Service tests (mocked dependencies)
├── integration/          # Integration tests (API, database)
└── e2e/                  # End-to-end tests (optional)
```

## Running Tests

### Basic Commands

| Command | Description |
|---------|-------------|
| `./scripts/test.sh` | Run all tests with coverage |
| `./scripts/test.sh fast` | Run tests without coverage (faster) |
| `./scripts/test.sh unit` | Run unit tests only |
| `./scripts/test.sh html` | Generate HTML coverage report |
| `./scripts/test.sh cov` | Show coverage in terminal |

### Pytest Direct Usage

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_security.py -v

# Run specific test function
pytest tests/unit/test_security.py::TestPasswordHashing::test_verify_password_success -v

# Run tests matching keyword
pytest -k "password" -v

# Run tests with coverage for specific module
pytest --cov=core.security --cov-report=term-missing
```

## Writing Tests

### Example Unit Test

```python
# tests/unit/test_example.py
import pytest
from core.security import verify_password, get_password_hash

class TestExample:
    def test_password_verification(self):
        password = "SecurePassword123!"
        password_hash = get_password_hash(password)
        
        assert verify_password(password, password_hash) is True
        assert verify_password("wrong", password_hash) is False
```

### Example Service Test (with Mocking)

```python
# tests/services/test_example.py
import pytest
from unittest.mock import MagicMock, patch

def test_lxd_service_with_mock(mock_lxd_client):
    with patch('services.lxd_client.get_lxd_client') as mock_get:
        mock_get.return_value = mock_lxd_client
        
        # Your test code here
        pass
```

### Example API Test

```python
# tests/integration/test_api.py
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded", "unhealthy"]

def test_protected_endpoint(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
```

## Fixtures

The `conftest.py` provides these useful fixtures:

| Fixture | Description |
|---------|-------------|
| `db_session` | Fresh in-memory database for each test |
| `client` | TestClient with database override |
| `auth_client` | Authenticated TestClient (logged in) |
| `test_user` | Creates test admin user in DB |
| `test_user_credentials` | Returns test credentials dict |
| `mock_lxd_client` | Mocked LXD client |
| `mock_lxd_settings` | Creates LXD settings in DB |
| `mock_vm_settings` | Creates VM defaults in DB |
| `temp_ssh_keys_dir` | Temporary directory for SSH key tests |
| `mock_psutil` | Mocked psutil for system metrics |

## Coverage

Current coverage report:

```
Name                                Stmts   Miss  Cover
-------------------------------------------------------
core/security.py                       25      0   100%
core/validators.py                     35      2    94%
core/rate_limiter.py                   30      1    97%
```

View HTML report: `./scripts/test.sh html` then open `htmlcov/index.html`

## CI/CD

Tests run automatically on:
- Every push to `main` branch
- Every pull request

GitHub Actions workflow: `.github/workflows/test.yml`

Coverage reports are uploaded to:
- Codecov: codecov.io
- GitHub Actions artifacts

## Best Practices

1. **Test names**: Use descriptive names like `test_verify_password_success`
2. **Arrange-Act-Assert**: Structure tests clearly
3. **Fixtures**: Use fixtures for common setup
4. **Mocking**: Mock external services (LXD, filesystem)
5. **Coverage**: Aim for >80% coverage on critical paths
6. **Speed**: Keep unit tests fast (<100ms each)

## Troubleshooting

### SECRET_KEY Error
```bash
export SECRET_KEY=$(openssl rand -hex 32)
```

### Database Lock
```bash
# Clean up any leftover test databases
rm -f test.db app.db
```

### Import Errors
```bash
# Ensure you're in the project directory
cd /path/to/sandbox

# Activate virtual environment
source .venv/bin/activate
```

## Dependencies

Test dependencies are in `requirements-test.txt`:
- pytest
- pytest-asyncio
- pytest-cov
- httpx (test client)
- respx (HTTP mocking)
- pytest-mock
