"""Background task service for instance creation"""
import threading
import time
import uuid
from typing import Dict, Any, Optional

from services.cloud_init_service import get_cloud_init_template


# In-memory task tracking
creation_tasks: Dict[str, Dict[str, Any]] = {}


class InstanceTaskService:
    """Service for managing instance creation background tasks"""

    @staticmethod
    def get_task(task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by ID"""
        if task_id not in creation_tasks:
            return None
        return creation_tasks[task_id]

    @staticmethod
    def get_all_tasks() -> Dict[str, Dict[str, Any]]:
        """Get all tasks"""
        return creation_tasks

    @staticmethod
    def cleanup_task(task_id: str):
        """Clean up a completed task"""
        if task_id in creation_tasks and creation_tasks[task_id].get("done"):
            del creation_tasks[task_id]

    @staticmethod
    def create_instance_background(
        task_id: str,
        name: str,
        cpu: int,
        ram: int,
        disk: int,
        instance_type: str,
        lxd_settings: dict,
        cloud_init: Optional[str] = None
    ):
        """Background task to create an instance and track progress"""
        from services.lxd_client import get_lxd_client

        try:
            creation_tasks[task_id] = {
                "progress": 5,
                "message": "Connecting to LXD...",
                "done": False,
                "error": None
            }

            if lxd_settings["use_socket"]:
                client = get_lxd_client(
                    use_socket=True,
                    verify_ssl=lxd_settings["verify_ssl"],
                    cert=lxd_settings["client_cert"],
                    key=lxd_settings["client_key"]
                )
            else:
                client = get_lxd_client(
                    lxd_settings["server_url"],
                    verify_ssl=lxd_settings["verify_ssl"],
                    cert=lxd_settings["client_cert"],
                    key=lxd_settings["client_key"]
                )

            creation_tasks[task_id]["progress"] = 15
            creation_tasks[task_id]["message"] = f"Checking if instance '{name}' already exists..."

            # Check if instance already exists
            try:
                existing = client.instances.get(name)
                if existing:
                    raise Exception(f"Instance '{name}' already exists")
            except Exception:
                pass  # Instance doesn't exist, which is what we want

            creation_tasks[task_id]["progress"] = 25
            creation_tasks[task_id]["message"] = "Preparing instance configuration..."

            creation_tasks[task_id]["progress"] = 40
            creation_tasks[task_id]["message"] = "Getting Ubuntu image..."

            # Create instance from image - LXD will auto-download if not present
            try:
                # First, try to find a local Ubuntu 24.04 image
                image_alias = None
                local_image = None

                for img in client.images.all():
                    # Check if it's Ubuntu 24.04 using properties dict
                    desc = img.properties.get('description', '').lower()
                    if "ubuntu" in desc and "24.04" in desc:
                        local_image = img
                        if img.aliases:
                            image_alias = img.aliases[0]
                        break

                if local_image:
                    # Use the local image fingerprint
                    image_source = {
                        "type": "image",
                        "fingerprint": local_image.fingerprint
                    }
                    creation_tasks[task_id]["message"] = f"Using local image: {local_image.fingerprint[:12]}"
                else:
                    # Download from Ubuntu simplestreams
                    creation_tasks[task_id]["message"] = "Downloading Ubuntu 24.04 image..."
                    image_source = {
                        "type": "image",
                        "protocol": "simplestreams",
                        "server": "https://cloud-images.ubuntu.com/releases",
                        "alias": "24.04"
                    }

                if instance_type == "virtual-machine":
                    # Create VM using API directly (virtual_machines.create() has issues with image type)
                    creation_tasks[task_id]["message"] = "Creating virtual machine (downloading image if needed)..."
                    vm_config = {
                        "limits.cpu": str(cpu),
                        "limits.memory": f"{ram}GiB",
                    }
                    
                    # Add cloud-init user-data if provided
                    if cloud_init:
                        vm_config["user.user-data"] = cloud_init
                    
                    vm_devices = {
                        "root": {
                            "type": "disk",
                            "path": "/",
                            "pool": "default",
                            "size": f"{disk}GiB"
                        }
                    }
                    # Create VM with explicit type field
                    config_data = {
                        "name": name,
                        "source": image_source,
                        "config": vm_config,
                        "devices": vm_devices,
                        "type": "virtual-machine"
                    }
                    # Use API directly
                    response = client.api.instances.post(json=config_data)
                    operation_id = response.json()["operation"].split("/")[-1]

                    # Wait for operation to complete
                    while True:
                        op = client.operations.get(operation_id)
                        if op.status_code == 200:
                            break
                        time.sleep(1)
                        # Safely get progress from metadata
                        progress = 0
                        if op.metadata:
                            progress_val = op.metadata.get("progress", 0)
                            # Progress can be a dict or a number
                            if isinstance(progress_val, dict):
                                progress = progress_val.get("progress", 0)
                            elif isinstance(progress_val, (int, float)):
                                progress = progress_val
                        creation_tasks[task_id]["progress"] = min(60 + int(progress * 0.3), 90)
                else:
                    # Create container
                    creation_tasks[task_id]["message"] = "Creating container (downloading image if needed)..."
                    container_config = {
                        "limits.cpu": str(cpu),
                        "limits.memory": f"{ram}GiB",
                    }
                    
                    # Add cloud-init user-data if provided
                    if cloud_init:
                        container_config["user.user-data"] = cloud_init
                    
                    container_devices = {
                        "root": {
                            "type": "disk",
                            "path": "/",
                            "pool": "default",
                            "size": f"{disk}GiB"
                        }
                    }
                    config_data = {
                        "name": name,
                        "source": image_source,
                        "config": container_config,
                        "devices": container_devices
                    }
                    container = client.containers.create(config_data, wait=True)

                creation_tasks[task_id]["progress"] = 90
                creation_tasks[task_id]["message"] = "Finalizing instance..."
                time.sleep(1)

                creation_tasks[task_id]["progress"] = 100
                creation_tasks[task_id]["message"] = f"Instance '{name}' created successfully!"
                creation_tasks[task_id]["done"] = True

            except Exception as create_error:
                raise create_error

        except Exception as e:
            creation_tasks[task_id]["progress"] = 100
            creation_tasks[task_id]["done"] = True
            creation_tasks[task_id]["error"] = str(e)
            creation_tasks[task_id]["message"] = "Failed"

        # Clean up old completed tasks after a delay
        def cleanup_task():
            time.sleep(300)  # Keep task for 5 minutes
            if task_id in creation_tasks and creation_tasks[task_id]["done"]:
                InstanceTaskService.cleanup_task(task_id)

        cleanup_thread = threading.Thread(target=cleanup_task)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    @staticmethod
    def start_creation_task(
        name: str,
        cpu: int,
        ram: int,
        disk: int,
        instance_type: str,
        lxd_settings: dict,
        cloud_init: Optional[str] = None
    ) -> str:
        """Start a new instance creation task and return task ID"""
        task_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=InstanceTaskService.create_instance_background,
            args=(task_id, name, cpu, ram, disk, instance_type, lxd_settings, cloud_init)
        )
        thread.daemon = True
        thread.start()
        return task_id
