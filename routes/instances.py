"""Instance management routes"""
import os
import shutil
import uuid
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, VMDefaultSettings
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
        if not name or not name.replace("-", "").replace("_", "").isalnum():
            return JSONResponse({
                "success": False,
                "message": "Instance name must be alphanumeric (hyphens and underscores allowed)"
            })

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
            vm_swap=vm_swap
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
    db: Session = Depends(get_db),
    force: bool = False
):
    """Delete an LXD instance and its SSH keys"""
    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not configured"})

    # Delete the LXD instance
    result = lxd_service.delete_instance(instance_name, force)
    
    if result.get("success"):
        # Clean up SSH keys folder
        ssh_keys_path = os.path.join("_instances", instance_name)
        if os.path.exists(ssh_keys_path):
            try:
                shutil.rmtree(ssh_keys_path)
                result["message"] = f"Instance '{instance_name}' and SSH keys deleted successfully"
            except Exception as e:
                result["message"] = f"Instance deleted, but failed to remove SSH keys: {e}"
    
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
