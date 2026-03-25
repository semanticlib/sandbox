"""System utility functions for hardware and virtualization detection"""
import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def is_virtualization_supported() -> bool:
    """
    Check if the system supports hardware virtualization (KVM/QEMU).

    This is required for creating LXD virtual machines (VMs).
    Containers do not require virtualization support.

    Checks performed (in order):
    1. Check if /dev/kvm exists (KVM device)
    2. Check CPU flags for vmx (Intel) or svm (AMD)
    3. Try to run kvm-ok command if available

    Returns:
        True if virtualization is supported, False otherwise
    """
    # Check 1: KVM device exists
    if os.path.exists("/dev/kvm"):
        return True

    # Check 2: CPU flags contain virtualization extensions
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read().lower()
            # Intel VT-x or AMD-V
            if "vmx" in cpuinfo or "svm" in cpuinfo:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    # Check 3: Try kvm-ok command (if available)
    try:
        result = subprocess.run(
            ["kvm-ok"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return False


@lru_cache(maxsize=1)
def get_virtualization_info() -> dict:
    """
    Get detailed information about virtualization support.

    Returns:
        dict with virtualization support details
    """
    info = {
        "supported": False,
        "kvm_device": False,
        "cpu_flags": [],
        "cpu_vendor": None,
        "kvm_ok_available": False,
        "message": ""
    }

    # Check KVM device
    info["kvm_device"] = os.path.exists("/dev/kvm")

    # Check CPU flags
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            # Extract flags from first CPU
            for line in cpuinfo.split("\n"):
                if line.startswith("flags") or line.startswith("Features"):
                    flags = line.split(":", 1)[1].strip().lower().split()
                    info["cpu_flags"] = flags
                    if "vmx" in flags:
                        info["cpu_vendor"] = "Intel"
                    elif "svm" in flags:
                        info["cpu_vendor"] = "AMD"
                    break
    except (FileNotFoundError, PermissionError):
        pass

    # Check kvm-ok
    try:
        result = subprocess.run(
            ["kvm-ok"],
            capture_output=True,
            text=True,
            timeout=5
        )
        info["kvm_ok_available"] = True
        if result.returncode == 0:
            info["message"] = "KVM acceleration can be used"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["kvm_ok_available"] = False

    # Determine overall support
    info["supported"] = info["kvm_device"] or \
                        "vmx" in info["cpu_flags"] or \
                        "svm" in info["cpu_flags"]

    # Generate message
    if info["supported"]:
        vendor = info["cpu_vendor"] or "Unknown"
        info["message"] = f"Hardware virtualization ({vendor}) is available"
    else:
        info["message"] = "Hardware virtualization is not available on this system"

    return info


def check_lxd_vm_support() -> dict:
    """
    Check if LXD can create virtual machines on this system.

    This combines virtualization detection with LXD-specific checks.

    Returns:
        dict with LXD VM support details
    """
    virt_info = get_virtualization_info()

    result = {
        "vm_supported": virt_info["supported"],
        "container_supported": True,  # Containers always supported
        "details": virt_info,
        "recommendation": ""
    }

    if not virt_info["supported"]:
        result["recommendation"] = (
            "Virtual machines require hardware virtualization (Intel VT-x or AMD-V). "
            "This system does not appear to have virtualization support enabled. "
            "You can still create containers, which do not require virtualization. "
            "If this is a cloud VM, check if your provider offers VMs with nested virtualization enabled."
        )

    return result
