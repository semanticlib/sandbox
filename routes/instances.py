"""Instance management routes"""
import os
import shutil
import uuid
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, VMDefaultSettings
from core.validators import validate_instance_name, validate_positive_integer
from services.lxd_service import LXDService
from services.instance_tasks import InstanceTaskService, creation_tasks

router = APIRouter(prefix="/instances", tags=["instances"])


@router.post("/create")
async def create_instance(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new instance (VM or container)"""
    try:
        data = await request.json()

        # Validate required fields
        name = data.get("name")
        cpu = data.get("cpu")
        ram = data.get("ram")
        disk = data.get("disk")
        instance_type = data.get("type", "virtual-machine")

        # Validate instance name
        is_valid, error = validate_instance_name(name)
        if not is_valid:
            return JSONResponse({
                "success": False,
                "message": error
            })

        # Validate numeric fields
        is_valid, error = validate_positive_integer(cpu, "CPU", min_val=1, max_val=128)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})

        is_valid, error = validate_positive_integer(ram, "RAM (GB)", min_val=1, max_val=512)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})

        is_valid, error = validate_positive_integer(disk, "Disk (GB)", min_val=5, max_val=2048)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})

        # Get LXD settings BEFORE starting background thread
        lxd_settings_db = db.query(LXDSettings).first()
        if not lxd_settings_db:
            return JSONResponse({
                "success": False,
                "message": "LXD not configured. Please configure LXD in Settings first."
            })

        # Get VM default settings for cloud-init
        vm_settings = db.query(VMDefaultSettings).first()
        cloud_init_template = vm_settings.cloud_init if vm_settings and vm_settings.cloud_init else None
        vm_swap = vm_settings.swap if vm_settings and vm_settings.swap else 2
        vm_username = vm_settings.username if vm_settings and vm_settings.username else "ubuntu"
        image_fingerprint = vm_settings.image_fingerprint if vm_settings and vm_settings.image_fingerprint else None
        
        # Pass the raw template (with placeholders) to the background task
        # The background task will generate SSH keys and process the template
        cloud_init = cloud_init_template

        lxd_settings = {
            "use_socket": lxd_settings_db.use_socket,
            "server_url": lxd_settings_db.server_url,
            "verify_ssl": lxd_settings_db.verify_ssl,
            "client_cert": lxd_settings_db.client_cert,
            "client_key": lxd_settings_db.client_key
        }

        # Start background task
        task_id = InstanceTaskService.start_creation_task(
            name=name,
            cpu=cpu,
            ram=ram,
            disk=disk,
            instance_type=instance_type,
            lxd_settings=lxd_settings,
            cloud_init=cloud_init,
            vm_swap=vm_swap,
            vm_username=vm_username,
            image_fingerprint=image_fingerprint
        )

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": f"Creating {instance_type} '{name}'..."
        })
    except Exception as e:
        print(f"[ERROR] create_instance: {e}")
        return JSONResponse({"success": False, "message": str(e)})


@router.get("/create/status/{task_id}")
async def get_instance_creation_status(task_id: str):
    """Get the status of an instance creation task"""
    if task_id not in creation_tasks:
        return JSONResponse({
            "success": False,
            "message": "Task not found"
        })

    task = creation_tasks[task_id]
    return JSONResponse({
        "success": True,
        "progress": task["progress"],
        "message": task["message"],
        "done": task["done"],
        "error": task.get("error")
    })


@router.post("/{instance_name}/start")
async def start_instance(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Start an LXD instance"""
    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not configured"})

    result = lxd_service.start_instance(instance_name)
    return JSONResponse(result)


@router.post("/{instance_name}/stop")
async def stop_instance(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Stop an LXD instance"""
    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not configured"})

    result = lxd_service.stop_instance(instance_name)
    return JSONResponse(result)


@router.delete("/{instance_name}/delete")
async def delete_instance(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete an LXD instance and its SSH keys"""
    from services.jump_user_service import delete_jump_user
    
    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not configured"})

    # Get VM settings for username (to delete jump user)
    vm_settings = db.query(VMDefaultSettings).first()
    username = vm_settings.username if vm_settings else "ubuntu"

    # Delete the LXD instance
    result = lxd_service.delete_instance(instance_name)

    if result.get("success"):
        # Clean up SSH keys folder
        ssh_keys_path = os.path.join("_instances", instance_name)
        if os.path.exists(ssh_keys_path):
            try:
                shutil.rmtree(ssh_keys_path)
                result["message"] = f"Instance '{instance_name}' and SSH keys deleted successfully"
            except Exception as e:
                result["message"] = f"Instance deleted, but failed to remove SSH keys: {e}"
        
        # Delete jump user from host system
        try:
            delete_jump_user(username)
        except Exception:
            pass  # Don't fail deletion if jump user cleanup fails

    return JSONResponse(result)


@router.get("/{instance_name}/ssh-keys")
async def get_instance_ssh_keys(instance_name: str):
    """Get SSH keys for a VM instance"""
    from services.ssh_key_service import get_instance_keys
    
    keys = get_instance_keys(instance_name)
    
    if not keys:
        return JSONResponse({
            "success": False,
            "message": "SSH keys not found for this instance"
        })
    
    return JSONResponse({
        "success": True,
        "private_key": keys["private_key"],
        "public_key": keys["public_key"]
    })


@router.get("/{instance_name}/download-ssh-config")
async def download_ssh_config(instance_name: str, db: Session = Depends(get_db)):
    """Generate and download SSH config files as a zip"""
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    from services.ssh_key_service import get_instance_keys
    from services.ssh_config_service import create_ssh_config_files, DEFAULT_SSH_CONFIG_TEMPLATE, DEFAULT_INSTRUCTIONS_TEMPLATE
    from services.jump_user_service import create_jump_user
    from core.models import ConnectionTemplate
    
    # Get SSH keys
    keys = get_instance_keys(instance_name)
    if not keys:
        return JSONResponse({
            "success": False,
            "message": "SSH keys not found for this instance"
        })
    
    # Get VM settings for username
    vm_settings = db.query(VMDefaultSettings).first()
    username = vm_settings.username if vm_settings else "ubuntu"
    
    # Get connection templates from DB
    templates = db.query(ConnectionTemplate).first()
    ssh_template = templates.ssh_config_template if templates and templates.ssh_config_template else DEFAULT_SSH_CONFIG_TEMPLATE
    instructions_template = templates.instructions_template if templates and templates.instructions_template else DEFAULT_INSTRUCTIONS_TEMPLATE
    
    # Create/update jump user on host system
    jump_user_result = create_jump_user(username, keys["public_key"])
    if not jump_user_result.get("success"):
        return JSONResponse({
            "success": False,
            "message": f"Failed to setup jump user: {jump_user_result.get('message')}"
        })
    
    # Get VM IP address
    from services.lxd_service import LXDService
    lxd_service = LXDService(db)
    lxd_service.get_client()
    vm_ip = None
    
    if lxd_service.is_connected():
        try:
            instance = lxd_service.client.instances.get(instance_name)
            if instance.status == "Running":
                state = instance.state()
                network = state.network
                if network:
                    for iface_name, iface_data in network.items():
                        addresses = iface_data.get('addresses', [])
                        for addr in addresses:
                            if addr.get('family') == 'inet':
                                vm_ip = addr.get('address')
                                break
                        if vm_ip:
                            break
        except Exception:
            pass
    
    # Generate SSH config files with templates
    create_ssh_config_files(instance_name, keys, username, vm_ip, ssh_template, instructions_template)
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    instance_dir = os.path.join("_instances", instance_name)
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in ['id_ed25519', 'id_ed25519.pub', 'ssh-config', 'instructions.txt']:
            filepath = os.path.join(instance_dir, filename)
            if os.path.exists(filepath):
                zip_file.write(filepath, filename)
    
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={instance_name}-ssh-config.zip"}
    )


# ============== Bulk Operations ==============

@router.get("/bulk/preflight")
async def bulk_preflight_check(
    names: str = "",
    cpu: int = 2,
    ram: int = 4,
    disk: int = 20,
    db: Session = Depends(get_db)
):
    """Run pre-flight checks before bulk operations"""
    from services.bulk_service import BulkOperationService
    
    # Parse names if provided
    instance_names = []
    if names:
        instance_names = [n.strip() for n in names.split(",") if n.strip()]
    
    checks = BulkOperationService.check_preflight(
        db, 
        instance_names=instance_names if instance_names else None,
        cpu_per_vm=cpu,
        ram_per_vm=ram,
        disk_per_vm=disk
    )
    return JSONResponse(checks)


@router.post("/bulk/create")
async def bulk_create_instances(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create multiple instances at once.
    
    Expects JSON with:
    - names: List of instance names (or comma-separated string)
    - cpu, ram, disk: Resource allocation per instance
    - type: "virtual-machine" or "container"
    """
    from services.bulk_service import BulkOperationService
    
    try:
        data = await request.json()
        
        # Parse names (support list or comma-separated string)
        names_input = data.get("names", [])
        if isinstance(names_input, str):
            instance_names = [n.strip() for n in names_input.split(",") if n.strip()]
        else:
            instance_names = names_input
        
        # Validate all names
        for name in instance_names:
            is_valid, error = validate_instance_name(name)
            if not is_valid:
                return JSONResponse({
                    "success": False,
                    "message": f"Invalid instance name '{name}': {error}"
                })
        
        # Check for duplicates
        if len(instance_names) != len(set(instance_names)):
            return JSONResponse({
                "success": False,
                "message": "Duplicate instance names detected"
            })
        
        # Validate resources
        cpu = data.get("cpu", 2)
        ram = data.get("ram", 4)
        disk = data.get("disk", 20)
        instance_type = data.get("type", "virtual-machine")
        
        is_valid, error = validate_positive_integer(cpu, "CPU", min_val=1, max_val=128)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})
        
        is_valid, error = validate_positive_integer(ram, "RAM (GB)", min_val=1, max_val=512)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})
        
        is_valid, error = validate_positive_integer(disk, "Disk (GB)", min_val=5, max_val=2048)
        if not is_valid:
            return JSONResponse({"success": False, "message": error})
        
        # Get LXD settings
        lxd_settings_db = db.query(LXDSettings).first()
        if not lxd_settings_db:
            return JSONResponse({
                "success": False,
                "message": "LXD not configured. Please configure LXD in Settings first."
            })
        
        # Get VM default settings
        vm_settings = db.query(VMDefaultSettings).first()
        cloud_init = vm_settings.cloud_init if vm_settings else None
        vm_swap = vm_settings.swap if vm_settings else 2
        vm_username = vm_settings.username if vm_settings else "ubuntu"
        image_fingerprint = vm_settings.image_fingerprint if vm_settings else None
        
        lxd_settings = {
            "use_socket": lxd_settings_db.use_socket,
            "server_url": lxd_settings_db.server_url,
            "verify_ssl": lxd_settings_db.verify_ssl,
            "client_cert": lxd_settings_db.client_cert,
            "client_key": lxd_settings_db.client_key
        }
        
        # Start bulk creation
        op_id = BulkOperationService.start_bulk_create(
            instance_names=instance_names,
            cpu=cpu,
            ram=ram,
            disk=disk,
            instance_type=instance_type,
            lxd_settings=lxd_settings,
            cloud_init=cloud_init,
            vm_swap=vm_swap,
            vm_username=vm_username,
            image_fingerprint=image_fingerprint
        )
        
        return JSONResponse({
            "success": True,
            "operation_id": op_id,
            "message": f"Starting bulk creation of {len(instance_names)} instances..."
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@router.post("/bulk/stop")
async def bulk_stop_instances(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Stop multiple instances at once.
    
    Expects JSON with:
    - names: List of instance names to stop
    - all: If true, stop all running instances (ignores names)
    """
    from services.bulk_service import BulkOperationService
    
    try:
        data = await request.json()
        stop_all = data.get("all", False)
        instance_names = data.get("names", [])
        
        lxd_service = LXDService(db)
        lxd_service.get_client()
        
        if not lxd_service.is_connected():
            return JSONResponse({
                "success": False,
                "message": "LXD not configured"
            })
        
        # Get all instances if "all" is specified
        if stop_all:
            all_instances = lxd_service.get_all_instances()
            instance_names = [
                inst["name"] for inst in all_instances 
                if inst.get("status") == "Running"
            ]
        
        if not instance_names:
            return JSONResponse({
                "success": False,
                "message": "No instances to stop"
            })
        
        op_id = BulkOperationService.start_bulk_stop(instance_names, db)
        
        return JSONResponse({
            "success": True,
            "operation_id": op_id,
            "message": f"Stopping {len(instance_names)} instances..."
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@router.post("/bulk/delete")
async def bulk_delete_instances(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Delete multiple instances at once.
    
    Expects JSON with:
    - names: List of instance names to delete
    - all: If true, delete all stopped instances (ignores names)
    """
    from services.bulk_service import BulkOperationService
    
    try:
        data = await request.json()
        delete_all = data.get("all", False)
        instance_names = data.get("names", [])
        
        lxd_service = LXDService(db)
        lxd_service.get_client()
        
        if not lxd_service.is_connected():
            return JSONResponse({
                "success": False,
                "message": "LXD not configured"
            })
        
        # Get all stopped instances if "all" is specified
        if delete_all:
            all_instances = lxd_service.get_all_instances()
            instance_names = [
                inst["name"] for inst in all_instances 
                if inst.get("status") != "Running"
            ]
        
        if not instance_names:
            return JSONResponse({
                "success": False,
                "message": "No instances to delete"
            })
        
        op_id = BulkOperationService.start_bulk_delete(instance_names, db)
        
        return JSONResponse({
            "success": True,
            "operation_id": op_id,
            "message": f"Deleting {len(instance_names)} instances..."
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@router.get("/bulk/status/{operation_id}")
async def get_bulk_operation_status(operation_id: str):
    """Get the status of a bulk operation"""
    from services.bulk_service import BulkOperationService
    
    operation = BulkOperationService.get_operation(operation_id)
    
    if not operation:
        return JSONResponse({
            "success": False,
            "message": "Operation not found"
        })
    
    return JSONResponse({
        "success": True,
        "operation": operation
    })


@router.get("/bulk/operations")
async def list_bulk_operations():
    """List all recent bulk operations"""
    from services.bulk_service import BulkOperationService
    
    operations = BulkOperationService.get_all_operations()
    return JSONResponse({
        "success": True,
        "operations": list(operations.values())
    })
