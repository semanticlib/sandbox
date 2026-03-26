"""
Pytest configuration and shared fixtures for Sandbox Manager tests.

This module provides:
- Test database setup/teardown
- Test client for API testing
- Mock utilities for LXD and external services
- Common test data factories
"""
import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.models import AdminUser, LXDSettings, Classroom
from core.security import get_password_hash
from main import app


# ============== Test Database Configuration ==============

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database for each test function.
    
    Usage:
        def test_something(db_session):
            user = AdminUser(username="test", password_hash="...")
            db_session.add(user)
            db_session.commit()
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        # Rollback any uncommitted changes and close
        session.rollback()
        session.close()
        
        # Drop tables
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with database dependency override.
    
    Usage:
        def test_api_endpoint(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ============== Authentication Fixtures ==============

@pytest.fixture
def test_user(db_session):
    """Create a test admin user and return user data."""
    user = AdminUser(
        username="testadmin",
        password_hash=get_password_hash("testpassword123"),
        is_active=True,
        is_first_login=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return {
        "id": user.id,
        "username": user.username,
        "is_first_login": user.is_first_login,
    }


@pytest.fixture
def test_user_credentials():
    """Return test user credentials (without creating in DB)."""
    return {
        "username": "testadmin",
        "password": "testpassword123",
    }


@pytest.fixture
def auth_client(client, test_user_credentials):
    """
    Create an authenticated test client.
    
    Usage:
        def test_protected_endpoint(auth_client):
            response = auth_client.get("/")
            assert response.status_code == 200
    """
    # Login to get cookie
    response = client.post("/login", data=test_user_credentials)
    
    # Extract cookie from response
    cookies = response.cookies
    
    # Create new client with auth cookie
    auth_client = TestClient(app)
    auth_client.cookies.update(cookies)
    
    return auth_client


# ============== LXD Mock Fixtures ==============

@pytest.fixture
def mock_lxd_client():
    """
    Create a mock LXD client for testing.
    
    Usage:
        def test_lxd_service(mock_lxd_client):
            with patch('services.lxd_client.get_lxd_client') as mock_get:
                mock_get.return_value = mock_lxd_client
                # ... test code
    """
    client = MagicMock()
    
    # Mock instances
    mock_instance = MagicMock()
    mock_instance.name = "test-vm"
    mock_instance.status = "Stopped"
    mock_instance.type = "virtual-machine"
    mock_instance.config = {
        "limits.cpu": "2",
        "limits.memory": "4GiB",
    }
    mock_instance.devices = {
        "root": {"type": "disk", "size": "20GiB"}
    }
    mock_instance.start = MagicMock()
    mock_instance.stop = MagicMock()
    mock_instance.delete = MagicMock()
    
    # Mock instance state
    mock_state = MagicMock()
    mock_state.network = {
        "eth0": {
            "addresses": [
                {"family": "inet", "address": "10.0.0.100"}
            ]
        }
    }
    mock_instance.state = mock_state
    
    # Mock instances collection
    client.instances = MagicMock()
    client.instances.all = MagicMock(return_value=[mock_instance])
    client.instances.get = MagicMock(return_value=mock_instance)
    
    # Mock API
    client.api = MagicMock()
    client.api.get = MagicMock(return_value=MagicMock(
        json=MagicMock(return_value={
            "environment": {"server_name": "test-lxd-server"}
        })
    ))
    
    return client


@pytest.fixture
def mock_lxd_settings(db_session):
    """Create LXD settings in test database."""
    settings = LXDSettings(
        use_socket=False,
        server_url="https://localhost:8443",
        client_cert="-----BEGIN CERTIFICATE-----\ntest-cert\n-----END CERTIFICATE-----",
        client_key="-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        verify_ssl=True,
    )
    db_session.add(settings)
    db_session.commit()

    return settings


@pytest.fixture
def mock_classroom(db_session):
    """Create default classroom in test database."""
    classroom = Classroom(
        name="Test Classroom",
        username="ubuntu",
        image_type="virtual-machine",
        image_fingerprint="abc123def456",
        image_alias="ubuntu/24.04",
        image_description="Ubuntu 24.04 LTS",
        ssh_config_template="Host {vm_name}\n    HostName {host_ip}\n    User {username}",
    )
    db_session.add(classroom)
    db_session.commit()

    return classroom


# ============== Utility Fixtures ==============

@pytest.fixture
def temp_ssh_keys_dir(tmp_path):
    """
    Create a temporary directory for SSH key testing.
    
    Usage:
        def test_ssh_keys(temp_ssh_keys_dir):
            from services.ssh_key_service import save_instance_keys
            save_instance_keys("test-vm", "priv", "pub", str(temp_ssh_keys_dir))
    """
    return tmp_path / "_instances"


@pytest.fixture
def mock_psutil():
    """Mock psutil for system metrics testing."""
    with patch('psutil.virtual_memory') as mock_mem, \
         patch('psutil.cpu_count') as mock_cpu:
        
        mock_mem.return_value = MagicMock(
            total=17179869184,  # 16 GB
            available=8589934592,  # 8 GB
        )
        mock_cpu.return_value = 8
        
        yield mock_mem, mock_cpu


# ============== Test Data Factories ==============

def create_instance_data(name, status="Running", instance_type="virtual-machine"):
    """Factory function to create instance data dict."""
    return {
        "name": name,
        "status": status,
        "type": instance_type,
        "cpu": "2",
        "memory": "4GiB",
        "disk": "20GiB",
        "ip": "10.0.0.100" if status == "Running" else "N/A",
    }


def create_bulk_operation_data(operation_type="bulk_create"):
    """Factory function to create bulk operation data dict."""
    return {
        "id": "test-op-id",
        "type": operation_type,
        "total": 5,
        "completed": 0,
        "failed": 0,
        "progress": 0,
        "status": "starting",
        "message": "Starting operation...",
        "done": False,
        "error": None,
        "results": [],
    }
