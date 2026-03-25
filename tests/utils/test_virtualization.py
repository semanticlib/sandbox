"""
Tests for virtualization detection utility.
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from utils.virtualization import (
    is_virtualization_supported,
    get_virtualization_info,
    check_lxd_vm_support,
)


class TestVirtualizationDetection:
    """Test virtualization detection functions."""

    @patch("utils.virtualization.os.path.exists")
    def test_kvm_device_exists(self, mock_exists):
        """Test that KVM device detection works."""
        mock_exists.return_value = True
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is True
        mock_exists.assert_called_with("/dev/kvm")

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu vmx mmx sse")
    def test_intel_vmx_detected(self, mock_file, mock_exists):
        """Test that Intel VT-x (vmx) flag is detected."""
        mock_exists.return_value = False
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is True

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu svm mmx sse")
    def test_amd_svm_detected(self, mock_file, mock_exists):
        """Test that AMD-V (svm) flag is detected."""
        mock_exists.return_value = False
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is True

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu mmx sse")
    def test_no_virtualization_flags(self, mock_file, mock_exists):
        """Test that missing virtualization flags returns False."""
        mock_exists.return_value = False
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is False

    @patch("utils.virtualization.os.path.exists")
    @patch("utils.virtualization.subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu mmx sse")
    def test_kvm_ok_command_success(self, mock_file, mock_run, mock_exists):
        """Test that kvm-ok command success indicates support."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0, stdout="KVM acceleration can be used")
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is True

    @patch("utils.virtualization.os.path.exists")
    @patch("utils.virtualization.subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu mmx sse")
    def test_kvm_ok_command_failure(self, mock_file, mock_run, mock_exists):
        """Test that kvm-ok command failure returns False."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=1, stdout="KVM is not available")
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is False

    @patch("utils.virtualization.os.path.exists")
    @patch("utils.virtualization.subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu mmx sse")
    def test_kvm_ok_not_available(self, mock_file, mock_run, mock_exists):
        """Test that missing kvm-ok command doesn't crash."""
        mock_exists.return_value = False
        mock_run.side_effect = FileNotFoundError("kvm-ok not found")
        
        # Clear cache before test
        is_virtualization_supported.cache_clear()
        get_virtualization_info.cache_clear()
        
        result = is_virtualization_supported()
        
        assert result is False


class TestGetVirtualizationInfo:
    """Test get_virtualization_info function."""

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu vmx mmx sse")
    def test_info_with_intel_cpu(self, mock_file, mock_exists):
        """Test virtualization info for Intel CPU."""
        mock_exists.return_value = True
        
        # Clear cache before test
        get_virtualization_info.cache_clear()
        
        info = get_virtualization_info()
        
        assert info["supported"] is True
        assert info["kvm_device"] is True
        assert info["cpu_vendor"] == "Intel"
        assert "vmx" in info["cpu_flags"]

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu svm mmx sse")
    def test_info_with_amd_cpu(self, mock_file, mock_exists):
        """Test virtualization info for AMD CPU."""
        mock_exists.return_value = False
        
        # Clear cache before test
        get_virtualization_info.cache_clear()
        
        info = get_virtualization_info()
        
        assert info["supported"] is True
        assert info["kvm_device"] is False
        assert info["cpu_vendor"] == "AMD"
        assert "svm" in info["cpu_flags"]

    @patch("utils.virtualization.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="flags : fpu mmx sse")
    def test_info_without_virtualization(self, mock_file, mock_exists):
        """Test virtualization info when not supported."""
        mock_exists.return_value = False
        
        # Clear cache before test
        get_virtualization_info.cache_clear()
        
        info = get_virtualization_info()
        
        assert info["supported"] is False
        assert info["kvm_device"] is False
        assert info["cpu_vendor"] is None
        assert "vmx" not in info["cpu_flags"]
        assert "svm" not in info["cpu_flags"]


class TestLXDVMSupport:
    """Test check_lxd_vm_support function."""

    @patch("utils.virtualization.get_virtualization_info")
    def test_vm_supported(self, mock_get_info):
        """Test when VMs are supported."""
        mock_get_info.return_value = {
            "supported": True,
            "kvm_device": True,
            "cpu_flags": ["vmx"],
            "cpu_vendor": "Intel",
            "message": "Hardware virtualization is available"
        }
        
        result = check_lxd_vm_support()
        
        assert result["vm_supported"] is True
        assert result["container_supported"] is True
        assert result["recommendation"] == ""

    @patch("utils.virtualization.get_virtualization_info")
    def test_vm_not_supported(self, mock_get_info):
        """Test when VMs are not supported."""
        mock_get_info.return_value = {
            "supported": False,
            "kvm_device": False,
            "cpu_flags": [],
            "cpu_vendor": None,
            "message": "Hardware virtualization is not available"
        }
        
        result = check_lxd_vm_support()
        
        assert result["vm_supported"] is False
        assert result["container_supported"] is True
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0
