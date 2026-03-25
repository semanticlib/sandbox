"""
Tests for Jump User Service.

These tests verify that jump users are properly created and deleted,
ensuring each instance has its own unique jump user.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from services.jump_user_service import (
    create_jump_user,
    delete_jump_user,
    jump_user_exists,
    update_jump_user_keys,
)


class TestJumpUserCreation:
    """Test jump user creation functionality."""

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_create_jump_user_with_instance_name(
        self, mock_exists, mock_run
    ):
        """Test that jump user is created with instance name as username."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        result = create_jump_user(
            username="ubuntu",  # This should be ignored when instance_name is provided
            public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
            instance_name="vm-test-001",
        )

        assert result["success"] is True
        assert result["created"] is True

        # Verify useradd was called with instance name, not 'ubuntu'
        useradd_call = mock_run.call_args_list[0]
        assert "vm-test-001" in useradd_call[0][0]
        assert "ubuntu" not in useradd_call[0][0]

    @patch("services.jump_user_service.jump_user_exists")
    def test_create_jump_user_fails_if_user_exists(self, mock_exists):
        """Test that creation fails if user already exists (no reuse)."""
        mock_exists.return_value = True

        result = create_jump_user(
            username="vm-test-001",
            public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
            instance_name="vm-test-001",
        )

        assert result["success"] is False
        assert "already exists" in result["message"]

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_create_jump_user_creates_ssh_directory(
        self, mock_exists, mock_run
    ):
        """Test that .ssh directory is created for the jump user."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        create_jump_user(
            username="test-user",
            public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
            instance_name="vm-test-001",
        )

        # Check that mkdir was called for .ssh directory
        mkdir_calls = [
            call for call in mock_run.call_args_list if "mkdir" in call[0][0]
        ]
        assert len(mkdir_calls) > 0

        # Verify the path uses the instance name
        mkdir_call = mkdir_calls[0]
        assert "vm-test-001/.ssh" in mkdir_call[0][0][3]

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_create_jump_user_sets_correct_permissions(
        self, mock_exists, mock_run
    ):
        """Test that correct permissions are set for SSH files."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        create_jump_user(
            username="test-user",
            public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
            instance_name="vm-test-001",
        )

        # Check chmod calls for .ssh directory (700) and authorized_keys (600)
        chmod_calls = [
            call for call in mock_run.call_args_list if "chmod" in call[0][0]
        ]

        # Should have at least 2 chmod calls (700 for .ssh, 600 for authorized_keys)
        assert len(chmod_calls) >= 2

        # Verify permissions
        chmod_700 = [c for c in chmod_calls if "700" in c[0][0]]
        chmod_600 = [c for c in chmod_calls if "600" in c[0][0]]

        assert len(chmod_700) > 0
        assert len(chmod_600) > 0


class TestJumpUserDeletion:
    """Test jump user deletion functionality."""

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_delete_jump_user_with_instance_name(self, mock_exists, mock_run):
        """Test that jump user is deleted using instance name."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = delete_jump_user("vm-test-001")

        assert result["success"] is True

        # Verify userdel was called with instance name
        userdel_call = mock_run.call_args_list[0]
        assert "vm-test-001" in userdel_call[0][0]

    @patch("services.jump_user_service.jump_user_exists")
    def test_delete_jump_user_when_user_does_not_exist(self, mock_exists):
        """Test that deletion succeeds silently if user doesn't exist."""
        mock_exists.return_value = False

        result = delete_jump_user("vm-test-001")

        assert result["success"] is True
        assert "does not exist" in result["message"]

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_delete_jump_user_removes_home_directory(
        self, mock_exists, mock_run
    ):
        """Test that userdel is called with -r flag to remove home directory."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        delete_jump_user("vm-test-001")

        # Verify userdel was called with -r flag
        userdel_call = mock_run.call_args_list[0]
        assert "-r" in userdel_call[0][0]


class TestJumpUserIntegration:
    """Integration tests for jump user lifecycle."""

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_create_and_delete_same_instance_name(self, mock_exists, mock_run):
        """Test that a jump user can be created and then deleted."""
        # First, user doesn't exist
        mock_exists.side_effect = [False, True]  # Create: False, Delete: True
        mock_run.return_value = MagicMock(returncode=0)

        # Create user
        create_result = create_jump_user(
            username="test",
            public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
            instance_name="vm-lifecycle-test",
        )
        assert create_result["success"] is True

        # Delete user
        delete_result = delete_jump_user("vm-lifecycle-test")
        assert delete_result["success"] is True

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_multiple_instances_have_unique_users(self, mock_exists, mock_run):
        """Test that multiple instances create separate jump users."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        instance_names = ["vm-001", "vm-002", "vm-003"]

        for name in instance_names:
            result = create_jump_user(
                username="ubuntu",  # Same fallback username
                public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
                instance_name=name,
            )
            assert result["success"] is True

        # Verify useradd was called 3 times with different names
        useradd_calls = [
            call for call in mock_run.call_args_list if "useradd" in call[0][0]
        ]
        assert len(useradd_calls) == 3

        # Verify each call used a different instance name
        called_names = []
        for call_item in useradd_calls:
            args = call_item[0][0]
            # Extract username from args (it's the last argument)
            called_names.append(args[-1])

        assert set(called_names) == set(instance_names)
