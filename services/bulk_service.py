"""Bulk operations service for managing multiple instances"""
import threading
import time
import uuid
import shutil
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from services.instance_tasks import InstanceTaskService, creation_tasks
from services.lxd_service import LXDService


# In-memory tracking for bulk operations
bulk_operations: Dict[str, Dict[str, Any]] = {}


class BulkOperationService:
    """Service for managing bulk instance operations"""

    @staticmethod
    def get_operation(op_id: str) -> Optional[Dict[str, Any]]:
        """Get bulk operation status by ID"""
        return bulk_operations.get(op_id)

    @staticmethod
    def get_all_operations() -> Dict[str, Dict[str, Any]]:
        """Get all bulk operations"""
        return bulk_operations.copy()

    @staticmethod
    def cleanup_operation(op_id: str):
        """Clean up a completed operation"""
        if op_id in bulk_operations and bulk_operations[op_id].get("done"):
            del bulk_operations[op_id]

    @staticmethod
    def check_preflight(db, instance_names: List[str] = None,
                        cpu_per_instance: int = 2, ram_per_instance: int = 4,
                        disk_per_instance: int = 20, instance_type: str = "container",
                        allow_overcommit: bool = False, required_disk_gb: float = 50) -> Dict[str, Any]:
        """
        Run pre-flight checks before bulk operations.

        Args:
            db: Database session
            instance_names: List of instance names to create (for capacity check)
            cpu_per_instance: CPU cores per instance
            ram_per_instance: RAM in GB per instance
            disk_per_instance: Disk in GB per instance
            instance_type: "container" or "virtual-machine" (affects density calculations)
            allow_overcommit: If True, allow over-provisioning beyond normal limits
            required_disk_gb: Minimum required free disk space after creation

        Returns:
            Dict with pass/fail status and details
        """
        checks = {
            "passed": True,
            "warnings": [],
            "errors": []
        }

        num_instances = len(instance_names) if instance_names else 0
        is_container = instance_type == "container"
        
        # Container density factor: containers can be 4-5x more dense than VMs
        # because they share the kernel and have less overhead
        density_factor = 4.0 if is_container else 1.0

        # Check LXD connection
        try:
            from core.models import LXDSettings
            lxd_settings = db.query(LXDSettings).first()

            if not lxd_settings:
                checks["errors"].append("LXD not configured. Please configure LXD in Settings first.")
                checks["passed"] = False
            else:
                lxd_service = LXDService(db)
                lxd_service.get_client()

                if not lxd_service.is_connected():
                    checks["errors"].append("Cannot connect to LXD. Check your LXD configuration.")
                    checks["passed"] = False
                else:
                    checks["lxd_connected"] = True
                    
                    # Get existing instance count
                    try:
                        existing_instances = lxd_service.get_all_instances()
                        checks["existing_instances"] = len(existing_instances)
                        running_count = sum(1 for i in existing_instances if i.get("status") == "Running")
                        checks["running_instances"] = running_count
                    except Exception:
                        pass
        except Exception as e:
            checks["errors"].append(f"LXD connection error: {str(e)}")
            checks["passed"] = False

        # Calculate resource requirements
        if num_instances > 0:
            total_cpu_needed = num_instances * cpu_per_instance
            total_ram_needed = num_instances * ram_per_instance
            total_disk_needed = num_instances * disk_per_instance
            checks["resources_requested"] = {
                "instances": num_instances,
                "cpu": total_cpu_needed,
                "ram_gb": total_ram_needed,
                "disk_gb": total_disk_needed
            }
            # Effective resource needs accounting for container density
            effective_cpu_needed = total_cpu_needed / density_factor
            effective_ram_needed = total_ram_needed / density_factor
            checks["effective_resources"] = {
                "cpu": round(effective_cpu_needed, 1),
                "ram_gb": round(effective_ram_needed, 1),
                "density_factor": density_factor
            }

        # Check disk space
        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024 ** 3)
            checks["disk_free_gb"] = round(free_gb, 2)
            
            # Calculate disk after creation
            if num_instances > 0:
                disk_after = free_gb - total_disk_needed
                checks["disk_after_creation_gb"] = round(disk_after, 2)
                
                if disk_after < required_disk_gb:
                    checks["errors"].append(
                        f"Insufficient disk space: {free_gb:.1f} GB free, "
                        f"{total_disk_needed} GB needed for {num_instances} VMs, "
                        f"only {disk_after:.1f} GB would remain (minimum {required_disk_gb} GB recommended)"
                    )
                    checks["passed"] = False
                elif disk_after < required_disk_gb * 2:
                    checks["warnings"].append(
                        f"Disk space will be low after creation: {disk_after:.1f} GB remaining"
                    )
            else:
                if free_gb < required_disk_gb:
                    checks["errors"].append(
                        f"Low disk space: {free_gb:.1f} GB free (minimum {required_disk_gb} GB recommended)"
                    )
                    checks["passed"] = False
        except Exception as e:
            checks["errors"].append(f"Failed to check disk space: {str(e)}")
            checks["passed"] = False

        # Check RAM capacity
        try:
            import psutil
            total_ram = psutil.virtual_memory().total / (1024 ** 3)
            available_ram = psutil.virtual_memory().available / (1024 ** 3)
            checks["ram_total_gb"] = round(total_ram, 2)
            checks["ram_available_gb"] = round(available_ram, 2)

            if num_instances > 0:
                # Use effective RAM for containers (lower due to density)
                effective_ram = effective_ram_needed if is_container else total_ram_needed
                ram_after = available_ram - effective_ram
                checks["ram_after_creation_gb"] = round(ram_after, 2)

                # Reserve 2GB for host system
                min_ram_after = 2.0

                if ram_after < min_ram_after:
                    if allow_overcommit:
                        checks["warnings"].append(
                            f"⚠️ Over-committing RAM: {available_ram:.1f} GB available, "
                            f"{effective_ram:.1f} GB requested, only {ram_after:.1f} GB would remain"
                        )
                    else:
                        checks["errors"].append(
                            f"Insufficient RAM: {available_ram:.1f} GB available, "
                            f"{effective_ram:.1f} GB needed for {num_instances} {'containers' if is_container else 'VMs'}, "
                            f"only {ram_after:.1f} GB would remain (minimum {min_ram_after} GB for host recommended)"
                        )
                        checks["passed"] = False
                elif ram_after < min_ram_after * 2:
                    checks["warnings"].append(
                        f"RAM will be low after creation: {ram_after:.1f} GB remaining for host"
                    )
        except ImportError:
            checks["warnings"].append("psutil not installed - skipping RAM check")
        except Exception as e:
            checks["warnings"].append(f"Failed to check RAM: {str(e)}")

        # Check CPU capacity
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=True)
            checks["cpu_logical_cores"] = cpu_count

            if num_instances > 0:
                # Use effective CPU for containers (lower due to density)
                effective_cpu = effective_cpu_needed if is_container else total_cpu_needed
                # Allow overcommitment but warn if too aggressive
                cpu_ratio = effective_cpu / cpu_count if cpu_count > 0 else 999

                if allow_overcommit:
                    # More lenient thresholds when overcommit is allowed
                    if cpu_ratio > 8:
                        checks["warnings"].append(
                            f"⚠️ Very high CPU overcommitment: {effective_cpu:.1f} vCPUs requested "
                            f"on {cpu_count} core system ({cpu_ratio:.1f}x overcommit)"
                        )
                    elif cpu_ratio > 4:
                        checks["warnings"].append(
                            f"⚠️ High CPU overcommitment: {effective_cpu:.1f} vCPUs requested "
                            f"on {cpu_count} core system ({cpu_ratio:.1f}x overcommit)"
                        )
                else:
                    # Normal thresholds
                    if cpu_ratio > 4:
                        checks["warnings"].append(
                            f"High CPU overcommitment: {effective_cpu:.1f} vCPUs requested "
                            f"on {cpu_count} core system ({cpu_ratio:.1f}x overcommit)"
                        )
                    elif cpu_ratio > 2:
                        checks["warnings"].append(
                            f"Moderate CPU overcommitment: {effective_cpu:.1f} vCPUs "
                            f"on {cpu_count} core system ({cpu_ratio:.1f}x overcommit)"
                        )
        except ImportError:
            checks["warnings"].append("psutil not installed - skipping CPU check")
        except Exception as e:
            checks["warnings"].append(f"Failed to check CPU: {str(e)}")

        # Check if too many instances already running
        if checks.get("running_instances", 0) >= 20:
            checks["warnings"].append(
                f"Already running {checks['running_instances']} instances. Performance may degrade."
            )

        return checks

    @staticmethod
    def bulk_create_instances(
        op_id: str,
        instance_names: List[str],
        cpu: int,
        ram: int,
        disk: int,
        instance_type: str,
        lxd_settings: dict,
        cloud_init: Optional[str] = None,
        vm_username: str = "ubuntu",
        image_fingerprint: Optional[str] = None
    ):
        """
        Background task to create multiple instances.

        Args:
            op_id: Operation ID for tracking
            instance_names: List of instance names to create
            cpu: CPU cores per instance
            ram: RAM in GB per instance
            disk: Disk size in GB per instance
            instance_type: "virtual-machine" or "container"
            lxd_settings: LXD connection settings
            cloud_init: Cloud-init template
            vm_username: Default username for VMs
            image_fingerprint: Optional LXD image fingerprint
        """
        total = len(instance_names)
        completed = 0
        failed = 0
        failed_names = []
        
        bulk_operations[op_id] = {
            "id": op_id,
            "type": "bulk_create",
            "total": total,
            "completed": 0,
            "failed": 0,
            "progress": 0,
            "status": "starting",
            "message": f"Starting bulk creation of {total} instances...",
            "done": False,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "results": []
        }
        
        try:
            for i, name in enumerate(instance_names):
                bulk_operations[op_id]["status"] = f"Creating {name}..."
                bulk_operations[op_id]["progress"] = int((i / total) * 100)
                
                # Create instance using existing task service
                task_id = InstanceTaskService.start_creation_task(
                    name=name,
                    cpu=cpu,
                    ram=ram,
                    disk=disk,
                    instance_type=instance_type,
                    lxd_settings=lxd_settings,
                    cloud_init=cloud_init,
                    vm_username=vm_username,
                    image_fingerprint=image_fingerprint
                )
                
                # Wait for this instance to complete before starting next
                # This prevents overwhelming the system
                while task_id in creation_tasks:
                    task = creation_tasks[task_id]
                    if task.get("done"):
                        break
                    time.sleep(1)
                
                # Check result
                if task_id in creation_tasks:
                    task = creation_tasks[task_id]
                    if task.get("error"):
                        failed += 1
                        failed_names.append(name)
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": False,
                            "error": task.get("error")
                        })
                    else:
                        completed += 1
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": True
                        })
                
                bulk_operations[op_id]["completed"] = completed
                bulk_operations[op_id]["failed"] = failed
            
            # Final status
            bulk_operations[op_id]["progress"] = 100
            bulk_operations[op_id]["done"] = True
            
            if failed > 0:
                bulk_operations[op_id]["status"] = "completed_with_errors"
                bulk_operations[op_id]["message"] = (
                    f"Created {completed}/{total} instances. "
                    f"{failed} failed: {', '.join(failed_names)}"
                )
            else:
                bulk_operations[op_id]["status"] = "completed"
                bulk_operations[op_id]["message"] = f"Successfully created {total} instances"
                
        except Exception as e:
            bulk_operations[op_id]["done"] = True
            bulk_operations[op_id]["error"] = str(e)
            bulk_operations[op_id]["status"] = "failed"
            bulk_operations[op_id]["message"] = f"Bulk creation failed: {str(e)}"
        
        # Schedule cleanup
        def cleanup():
            time.sleep(300)  # Keep for 5 minutes
            BulkOperationService.cleanup_operation(op_id)
        
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    @staticmethod
    def start_bulk_create(
        instance_names: List[str],
        cpu: int,
        ram: int,
        disk: int,
        instance_type: str,
        lxd_settings: dict,
        cloud_init: Optional[str] = None,
        vm_username: str = "ubuntu",
        image_fingerprint: Optional[str] = None
    ) -> str:
        """
        Start a bulk creation operation and return operation ID.

        Returns:
            Operation ID for tracking progress
        """
        op_id = str(uuid.uuid4())

        thread = threading.Thread(
            target=BulkOperationService.bulk_create_instances,
            args=(op_id, instance_names, cpu, ram, disk, instance_type,
                  lxd_settings, cloud_init, vm_username, image_fingerprint)
        )
        thread.daemon = True
        thread.start()

        return op_id

    @staticmethod
    def bulk_stop_instances(
        op_id: str,
        instance_names: List[str],
        db
    ):
        """
        Background task to stop multiple instances.
        
        Args:
            op_id: Operation ID for tracking
            instance_names: List of instance names to stop
            db: Database session
        """
        total = len(instance_names)
        completed = 0
        failed = 0
        failed_names = []
        
        bulk_operations[op_id] = {
            "id": op_id,
            "type": "bulk_stop",
            "total": total,
            "completed": 0,
            "failed": 0,
            "progress": 0,
            "status": "starting",
            "message": f"Stopping {total} instances...",
            "done": False,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "results": []
        }
        
        try:
            lxd_service = LXDService(db)
            lxd_service.get_client()
            
            if not lxd_service.is_connected():
                raise Exception("LXD not connected")
            
            for i, name in enumerate(instance_names):
                bulk_operations[op_id]["progress"] = int((i / total) * 100)
                
                try:
                    result = lxd_service.stop_instance(name)
                    if result.get("success"):
                        completed += 1
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": True,
                            "action": "stopped"
                        })
                    else:
                        failed += 1
                        failed_names.append(name)
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": False,
                            "error": result.get("message")
                        })
                except Exception as e:
                    failed += 1
                    failed_names.append(name)
                    bulk_operations[op_id]["results"].append({
                        "name": name,
                        "success": False,
                        "error": str(e)
                    })
                
                bulk_operations[op_id]["completed"] = completed
                bulk_operations[op_id]["failed"] = failed
            
            # Final status
            bulk_operations[op_id]["progress"] = 100
            bulk_operations[op_id]["done"] = True
            
            if failed > 0:
                bulk_operations[op_id]["status"] = "completed_with_errors"
                bulk_operations[op_id]["message"] = (
                    f"Stopped {completed}/{total} instances. "
                    f"{failed} failed: {', '.join(failed_names)}"
                )
            else:
                bulk_operations[op_id]["status"] = "completed"
                bulk_operations[op_id]["message"] = f"Successfully stopped {total} instances"
                
        except Exception as e:
            bulk_operations[op_id]["done"] = True
            bulk_operations[op_id]["error"] = str(e)
            bulk_operations[op_id]["status"] = "failed"
            bulk_operations[op_id]["message"] = f"Bulk stop failed: {str(e)}"
        
        # Schedule cleanup
        def cleanup():
            time.sleep(300)
            BulkOperationService.cleanup_operation(op_id)
        
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    @staticmethod
    def start_bulk_stop(instance_names: List[str], db) -> str:
        """Start a bulk stop operation and return operation ID."""
        op_id = str(uuid.uuid4())

        thread = threading.Thread(
            target=BulkOperationService.bulk_stop_instances,
            args=(op_id, instance_names, db)
        )
        thread.daemon = True
        thread.start()

        return op_id

    @staticmethod
    def bulk_start_instances(
        op_id: str,
        instance_names: List[str],
        db
    ):
        """
        Background task to start multiple instances.

        Args:
            op_id: Operation ID for tracking
            instance_names: List of instance names to start
            db: Database session
        """
        total = len(instance_names)
        completed = 0
        failed = 0
        failed_names = []

        bulk_operations[op_id] = {
            "id": op_id,
            "type": "bulk_start",
            "total": total,
            "completed": 0,
            "failed": 0,
            "progress": 0,
            "status": "starting",
            "message": f"Starting {total} instances...",
            "done": False,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "results": []
        }

        try:
            lxd_service = LXDService(db)
            lxd_service.get_client()

            if not lxd_service.is_connected():
                raise Exception("LXD not connected")

            for i, name in enumerate(instance_names):
                bulk_operations[op_id]["progress"] = int((i / total) * 100)

                try:
                    result = lxd_service.start_instance(name)
                    if result.get("success"):
                        completed += 1
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": True,
                            "action": "started"
                        })
                    else:
                        failed += 1
                        failed_names.append(name)
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": False,
                            "error": result.get("message")
                        })
                except Exception as e:
                    failed += 1
                    failed_names.append(name)
                    bulk_operations[op_id]["results"].append({
                        "name": name,
                        "success": False,
                        "error": str(e)
                    })

                bulk_operations[op_id]["completed"] = completed
                bulk_operations[op_id]["failed"] = failed

            # Final status
            bulk_operations[op_id]["progress"] = 100
            bulk_operations[op_id]["done"] = True

            if failed > 0:
                bulk_operations[op_id]["status"] = "completed_with_errors"
                bulk_operations[op_id]["message"] = (
                    f"Started {completed}/{total} instances. "
                    f"{failed} failed: {', '.join(failed_names)}"
                )
            else:
                bulk_operations[op_id]["status"] = "completed"
                bulk_operations[op_id]["message"] = f"Successfully started {total} instances"

        except Exception as e:
            bulk_operations[op_id]["done"] = True
            bulk_operations[op_id]["error"] = str(e)
            bulk_operations[op_id]["status"] = "failed"
            bulk_operations[op_id]["message"] = f"Bulk start failed: {str(e)}"

        # Schedule cleanup
        def cleanup():
            time.sleep(300)
            BulkOperationService.cleanup_operation(op_id)

        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    @staticmethod
    def start_bulk_start(instance_names: List[str], db) -> str:
        """Start a bulk start operation and return operation ID."""
        op_id = str(uuid.uuid4())

        thread = threading.Thread(
            target=BulkOperationService.bulk_start_instances,
            args=(op_id, instance_names, db)
        )
        thread.daemon = True
        thread.start()

        return op_id

    @staticmethod
    def bulk_delete_instances(
        op_id: str,
        instance_names: List[str],
        db
    ):
        """
        Background task to delete multiple instances.
        
        Args:
            op_id: Operation ID for tracking
            instance_names: List of instance names to delete
            db: Database session
        """
        total = len(instance_names)
        completed = 0
        failed = 0
        failed_names = []
        
        bulk_operations[op_id] = {
            "id": op_id,
            "type": "bulk_delete",
            "total": total,
            "completed": 0,
            "failed": 0,
            "progress": 0,
            "status": "starting",
            "message": f"Deleting {total} instances...",
            "done": False,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "results": []
        }
        
        try:
            lxd_service = LXDService(db)
            lxd_service.get_client()
            
            if not lxd_service.is_connected():
                raise Exception("LXD not connected")
            
            for i, name in enumerate(instance_names):
                bulk_operations[op_id]["progress"] = int((i / total) * 100)
                
                try:
                    # First stop if running
                    instance_data = lxd_service.get_all_instances()
                    instance = next((inst for inst in instance_data if inst["name"] == name), None)

                    if instance and instance.get("status") == "Running":
                        lxd_service.stop_instance(name)
                        # Wait for stop to complete
                        time.sleep(2)

                    result = lxd_service.delete_instance(name)
                    if result.get("success"):
                        completed += 1

                        # Clean up SSH keys folder (with path traversal protection)
                        from services.ssh_key_service import _safe_instance_path
                        try:
                            ssh_keys_path = _safe_instance_path(name, "_instances")
                            ssh_cleanup_msg = ""
                            if ssh_keys_path.exists():
                                try:
                                    shutil.rmtree(ssh_keys_path)
                                    ssh_cleanup_msg = " (SSH keys cleaned)"
                                except Exception as cleanup_error:
                                    ssh_cleanup_msg = f" (SSH key cleanup failed)"
                        except ValueError:
                            ssh_cleanup_msg = " (invalid instance name)"

                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": True,
                            "action": "deleted",
                            "ssh_cleanup": ssh_cleanup_msg
                        })
                    else:
                        failed += 1
                        failed_names.append(name)
                        bulk_operations[op_id]["results"].append({
                            "name": name,
                            "success": False,
                            "error": result.get("message")
                        })
                except Exception as e:
                    failed += 1
                    failed_names.append(name)
                    bulk_operations[op_id]["results"].append({
                        "name": name,
                        "success": False,
                        "error": str(e)
                    })
                
                bulk_operations[op_id]["completed"] = completed
                bulk_operations[op_id]["failed"] = failed
            
            # Final status
            bulk_operations[op_id]["progress"] = 100
            bulk_operations[op_id]["done"] = True

            if failed > 0:
                bulk_operations[op_id]["status"] = "completed_with_errors"
                bulk_operations[op_id]["message"] = (
                    f"Deleted {completed}/{total} instances. "
                    f"{failed} failed: {', '.join(failed_names)}"
                )
            else:
                # Count successful SSH cleanups
                ssh_cleaned = sum(1 for r in bulk_operations[op_id]["results"] 
                                 if r.get("success") and r.get("ssh_cleanup"))
                ssh_msg = f" (including {ssh_cleaned} SSH key folders)" if ssh_cleaned > 0 else ""
                bulk_operations[op_id]["status"] = "completed"
                bulk_operations[op_id]["message"] = (
                    f"Successfully deleted {total} instances{ssh_msg}"
                )
                
        except Exception as e:
            bulk_operations[op_id]["done"] = True
            bulk_operations[op_id]["error"] = str(e)
            bulk_operations[op_id]["status"] = "failed"
            bulk_operations[op_id]["message"] = f"Bulk delete failed: {str(e)}"
        
        # Schedule cleanup
        def cleanup():
            time.sleep(300)
            BulkOperationService.cleanup_operation(op_id)
        
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    @staticmethod
    def start_bulk_delete(instance_names: List[str], db) -> str:
        """Start a bulk delete operation and return operation ID."""
        op_id = str(uuid.uuid4())
        
        thread = threading.Thread(
            target=BulkOperationService.bulk_delete_instances,
            args=(op_id, instance_names, db)
        )
        thread.daemon = True
        thread.start()
        
        return op_id
