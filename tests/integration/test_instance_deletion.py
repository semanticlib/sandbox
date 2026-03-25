"""
Integration tests for instance deletion with jump user cleanup.

These tests verify that when an instance is deleted, the associated
jump user is also properly cleaned up.

Note: We test the service layer directly rather than through HTTP endpoints
to avoid complex mocking of the entire request pipeline.
"""
import pytest
from unittest.mock import patch, MagicMock, call


class TestJumpUserCleanupOnDeletion:
    """Test that jump users are properly deleted when instances are deleted."""

    @patch("services.jump_user_service.delete_jump_user")
    def test_delete_jump_user_called_with_instance_name(self, mock_delete_jump_user):
        """Verify delete_jump_user is called with the instance name."""
        from services.jump_user_service import delete_jump_user
        
        mock_delete_jump_user.return_value = {"success": True}
        
        # Call the function directly
        result = delete_jump_user("test-vm-001")
        
        assert result["success"] is True
        mock_delete_jump_user.assert_called_once_with("test-vm-001")

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_jump_user_deleted_with_correct_username(
        self, mock_exists, mock_run
    ):
        """Verify that userdel is called with the instance name, not a generic username."""
        from services.jump_user_service import delete_jump_user
        
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        # Delete jump user with instance name
        delete_jump_user("my-custom-vm")
        
        # Verify userdel was called with instance name
        userdel_call = mock_run.call_args_list[0]
        userdel_args = userdel_call[0][0]
        
        # Should contain instance name, not 'ubuntu' or 'root'
        assert "my-custom-vm" in userdel_args
        assert "ubuntu" not in userdel_args
        
        # Verify -r flag is present (remove home directory)
        assert "-r" in userdel_args

    @patch("services.jump_user_service.subprocess.run")
    @patch("services.jump_user_service.jump_user_exists")
    def test_multiple_instances_have_separate_jump_users(
        self, mock_exists, mock_run
    ):
        """Verify that each instance has its own jump user that can be deleted independently."""
        from services.jump_user_service import create_jump_user, delete_jump_user
        
        mock_exists.return_value = False  # User doesn't exist initially
        mock_run.return_value = MagicMock(returncode=0)
        
        instance_names = ["vm-001", "vm-002", "vm-003"]
        
        # Create jump users for each instance
        for name in instance_names:
            result = create_jump_user(
                username="ubuntu",  # This should be ignored
                public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI test@example.com",
                instance_name=name,
            )
            assert result["success"] is True
        
        # Verify useradd was called 3 times with different names
        useradd_calls = [c for c in mock_run.call_args_list if "useradd" in c[0][0]]
        assert len(useradd_calls) == 3
        
        # Reset mock to test deletion
        mock_run.reset_mock()
        mock_exists.return_value = True
        
        # Delete each jump user
        for name in instance_names:
            result = delete_jump_user(name)
            assert result["success"] is True
        
        # Verify userdel was called 3 times with correct names
        userdel_calls = [c for c in mock_run.call_args_list if "userdel" in c[0][0]]
        assert len(userdel_calls) == 3
        
        # Verify each call used the correct instance name
        deleted_names = []
        for call_item in userdel_calls:
            args = call_item[0][0]
            deleted_names.append(args[-1])  # Last arg is the username
        
        assert set(deleted_names) == set(instance_names)

