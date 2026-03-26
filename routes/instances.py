"""Instance management routes"""
import os
import shutil
import uuid
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, Classroom
from core.validators import validate_instance_name, validate_positive_integer
from services.lxd_service import LXDService
from services.instance_tasks import InstanceTaskService, creation_tasks

router = APIRouter(prefix="/instances", tags=["instances"])


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in user from session cookie"""
    from jose import JWTError, jwt
    from core.config import settings

    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        return user
    except (JWTError, Exception):
        return None


def require_auth(request: Request, db: Session = Depends(get_db)):
    """Dependency to require authentication"""
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user


@router.post("/create")
async def create_instance(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
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

        # Check if a system user with the instance name already exists (before creating instance)
        # This prevents conflicts with existing system users
        from services.jump_user_service import jump_user_exists
        if jump_user_exists(name):
            return JSONResponse({
                "success": False,
                "message": f"A system user '{name}' already exists. Please choose a different instance name."
            })

        # Get classroom from request if provided, otherwise use first classroom
        classroom_id = data.get("classroom_id")
        lxd_profile = data.get("lxd_profile")
        if classroom_id:
            classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        else:
            classroom = db.query(Classroom).first()
        
        # Use classroom settings if available
        if classroom:
            instance_type = classroom.image_type or instance_type
            vm_username = classroom.username
            image_fingerprint = classroom.image_fingerprint
            lxd_profile = lxd_profile or classroom.lxd_profile
        else:
            vm_username = "root" if instance_type == "container" else "ubuntu"
            image_fingerprint = None
        
        cloud_init = None  # Cloud-init is now handled via LXD profiles

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
            vm_swap=2,  # Default swap, can be set in cloud-init
            vm_username=vm_username,
            image_fingerprint=image_fingerprint,
            lxd_profile=lxd_profile
        )

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": f"Creating {instance_type} '{name}'..."
        })
    except Exception:
        # Log full error internally, return generic message
        import logging
        logging.exception("Error creating instance")
        return JSONResponse({"success": False, "message": "Failed to create instance"})


@router.get("/create/status/{task_id}")
async def get_instance_creation_status(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
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


# ============== Bulk Operations (BEFORE {instance_name} routes) ==============

@router.post("/api/expand-pattern")
async def api_expand_pattern(request: Request):
    """Expand a pattern into a list of names (for UI preview)"""
    from utils.pattern_expander import expand_names_input
    
    try:
        data = await request.json()
        pattern = data.get("pattern", "")
        
        names = expand_names_input(pattern)
        
        return JSONResponse({
            "success": True,
            "names": names,
            "count": len(names)
        })
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": "Invalid pattern format"
        }, status_code=400)


@router.get("/bulk/preflight")
async def bulk_preflight_check(
    names: str = "",
    cpu: int = 2,
    ram: int = 4,
    disk: int = 20,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Run pre-flight checks before bulk operations"""
    from services.bulk_service import BulkOperationService
    from utils.pattern_expander import expand_names_input

    # Parse names if provided (expand patterns)
    instance_names = []
    if names:
        # Split by comma first (in case multiple patterns/names are provided)
        name_parts = [n.strip() for n in names.split(",") if n.strip()]
        # Expand each part (handles both patterns and plain names)
        for part in name_parts:
            expanded = expand_names_input(part)
            instance_names.extend(expanded)

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
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Create multiple instances at once"""
    from services.bulk_service import BulkOperationService
    from utils.pattern_expander import expand_names_input
    import logging

    try:
        data = await request.json()
        logging.info(f"Bulk create request data: {data}")

        # Parse names (support list, comma-separated, or patterns)
        names_input = data.get("names", "")
        logging.info(f"Names input (type: {type(names_input).__name__}): {names_input}")

        # Expand patterns if provided
        if isinstance(names_input, str):
            instance_names = expand_names_input(names_input)
            logging.info(f"Expanded pattern to {len(instance_names)} instances: {instance_names}")
        else:
            # Already a list, use as-is
            instance_names = names_input
            logging.info(f"Using list input: {instance_names}")

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

        # Validate we have at least one name
        if not instance_names:
            return JSONResponse({
                "success": False,
                "message": "No instance names provided"
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

        # Check if any system user with the instance names already exists (before creating instances)
        # This prevents conflicts with existing system users
        from services.jump_user_service import jump_user_exists
        for name in instance_names:
            if jump_user_exists(name):
                return JSONResponse({
                    "success": False,
                    "message": f"A system user '{name}' already exists. Please choose different instance names."
                })

        # Get classroom from request if provided, otherwise use first classroom
        classroom_id = data.get("classroom_id")
        lxd_profile = data.get("lxd_profile")
        if classroom_id:
            classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        else:
            classroom = db.query(Classroom).first()
        
        # Use classroom settings if available
        if classroom:
            instance_type = classroom.image_type or instance_type
            vm_username = classroom.username
            image_fingerprint = classroom.image_fingerprint
            lxd_profile = lxd_profile or classroom.lxd_profile
        else:
            vm_username = "ubuntu"
            image_fingerprint = None
        
        cloud_init = None  # Cloud-init is now handled via LXD profiles

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
            vm_swap=2,  # Default swap, can be set in cloud-init
            vm_username=vm_username,
            image_fingerprint=image_fingerprint,
            lxd_profile=lxd_profile
        )

        return JSONResponse({
            "success": True,
            "operation_id": op_id,
            "message": f"Starting bulk creation of {len(instance_names)} instances..."
        })

    except ValueError as e:
        logging.exception("Pattern expansion error")
        return JSONResponse({"success": False, "message": str(e)})
    except Exception as e:
        logging.exception("Error in bulk create")
        return JSONResponse({"success": False, "message": f"Failed to start bulk creation: {str(e)}"})


@router.post("/bulk/stop")
async def bulk_stop_instances(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Stop multiple instances at once"""
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

    except Exception:
        import logging
        logging.exception("Error in bulk stop")
        return JSONResponse({"success": False, "message": "Failed to stop instances"})


@router.post("/bulk/start")
async def bulk_start_instances(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Start multiple instances at once"""
    from services.bulk_service import BulkOperationService

    try:
        data = await request.json()
        start_all = data.get("all", False)
        instance_names = data.get("names", [])

        lxd_service = LXDService(db)
        lxd_service.get_client()

        if not lxd_service.is_connected():
            return JSONResponse({
                "success": False,
                "message": "LXD not configured"
            })

        # Get all instances if "all" is specified
        if start_all:
            all_instances = lxd_service.get_all_instances()
            instance_names = [
                inst["name"] for inst in all_instances
                if inst.get("status") != "Running"
            ]

        if not instance_names:
            return JSONResponse({
                "success": False,
                "message": "No instances to start"
            })

        op_id = BulkOperationService.start_bulk_start(instance_names, db)

        return JSONResponse({
            "success": True,
            "operation_id": op_id,
            "message": f"Starting {len(instance_names)} instances..."
        })

    except Exception:
        import logging
        logging.exception("Error in bulk start")
        return JSONResponse({"success": False, "message": "Failed to start instances"})


@router.post("/bulk/delete")
async def bulk_delete_instances(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Delete multiple instances at once"""
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

    except Exception:
        import logging
        logging.exception("Error in bulk delete")
        return JSONResponse({"success": False, "message": "Failed to delete instances"})


@router.get("/bulk/status/{operation_id}")
async def get_bulk_operation_status(
    operation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
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
async def list_bulk_operations(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """List all recent bulk operations"""
    from services.bulk_service import BulkOperationService

    operations = BulkOperationService.get_all_operations()
    return JSONResponse({
        "success": True,
        "operations": list(operations.values())
    })


# ============== Individual Instance Operations ==============

@router.post("/{instance_name}/start")
async def start_instance(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
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
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
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
    user: AdminUser = Depends(require_auth)
):
    """Delete an LXD instance and its SSH keys"""
    from services.jump_user_service import delete_jump_user

    lxd_service = LXDService(db)
    lxd_service.get_client()

    if not lxd_service.is_connected():
        return JSONResponse({"success": False, "message": "LXD not configured"})

    # Delete the LXD instance
    result = lxd_service.delete_instance(instance_name)

    if result.get("success"):
        # Clean up SSH keys folder (with path traversal protection)
        from services.ssh_key_service import _safe_instance_path
        try:
            ssh_keys_path = _safe_instance_path(instance_name, "_instances")
            if ssh_keys_path.exists():
                try:
                    shutil.rmtree(ssh_keys_path)
                    result["message"] = "Instance and SSH keys deleted successfully"
                except Exception:
                    result["message"] = "Instance deleted, SSH key cleanup failed"
        except ValueError:
            result["message"] = "Instance deleted, invalid instance name format"

        # Delete jump user from host system (using instance name as the jump user)
        try:
            delete_jump_user(instance_name)
        except Exception:
            pass  # Don't fail deletion if jump user cleanup fails

    return JSONResponse(result)


@router.get("/{instance_name}/ssh-keys")
async def get_instance_ssh_keys(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
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
async def download_ssh_config(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Generate and download SSH config files as a zip"""
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    from services.ssh_key_service import get_instance_keys
    from services.ssh_config_service import create_ssh_config_files, DEFAULT_SSH_CONFIG_TEMPLATE
    from services.jump_user_service import create_jump_user
    from core.models import Classroom

    # Get SSH keys
    keys = get_instance_keys(instance_name)
    if not keys:
        return JSONResponse({
            "success": False,
            "message": "SSH keys not found for this instance"
        })

    # Create/update jump user on host system using instance name as username
    # This ensures each instance has its own unique jump user
    jump_user_result = create_jump_user(
        username=instance_name,  # Fallback (not used when instance_name provided)
        public_key=keys["public_key"],
        instance_name=instance_name  # Use instance name as the jump user
    )
    if not jump_user_result.get("success"):
        return JSONResponse({
            "success": False,
            "message": f"Failed to setup jump user: {jump_user_result.get('message')}"
        })

    # Get classroom settings for username (used for VM login, not jump user)
    classroom = db.query(Classroom).first()
    username = classroom.username if classroom else "ubuntu"

    # Get SSH config template from classroom
    ssh_template = classroom.ssh_config_template if classroom and classroom.ssh_config_template else DEFAULT_SSH_CONFIG_TEMPLATE

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
    create_ssh_config_files(instance_name, keys, username, vm_ip, ssh_template)

    # Create zip file in memory (with path traversal protection)
    from services.ssh_key_service import _safe_instance_path
    try:
        instance_dir = _safe_instance_path(instance_name, "_instances")
    except ValueError:
        return JSONResponse({
            "success": False,
            "message": "Invalid instance name"
        })

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in ['id_ed25519', 'ssh-config', 'launch-server.bat']:
            filepath = instance_dir / filename
            if filepath.exists():
                zip_file.write(filepath, filename)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={instance_name}-ssh-config.zip"}
    )
