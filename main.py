from datetime import datetime
import threading
import uuid
import time
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jinja2 import filters
from pydantic import BaseModel

from database import engine, get_db, Base
from models import AdminUser, LXDSettings, VMDefaultSettings
from auth import get_password_hash, verify_password, create_access_token
from cert_utils import generate_client_certificate
from jose import JWTError, jwt
from auth import SECRET_KEY, ALGORITHM

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Admin Panel")

templates = Jinja2Templates(directory="templates")
# Add filesizeformat filter
templates.env.filters['filesizeformat'] = filters.do_filesizeformat

# In-memory task tracking for instance creation
creation_tasks = {}


class InstanceCreateRequest(BaseModel):
    name: str
    cpu: int
    ram: int
    disk: int
    type: str = "virtual-machine"


def track_instance_creation(task_id: str, name: str, cpu: int, ram: int, disk: int, instance_type: str, lxd_settings: dict):
    """Background task to create an instance and track progress"""
    try:
        creation_tasks[task_id] = {
            "progress": 5,
            "message": "Connecting to LXD...",
            "done": False,
            "error": None
        }
        
        from lxd_client import get_lxd_client
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
        
        # Build instance configuration
        config = {
            "limits.cpu": str(cpu),
            "limits.memory": f"{ram}GiB",
        }
        devices = {
            "root": {
                "type": "disk",
                "path": "/",
                "pool": "default",
                "size": f"{disk}GiB"
            }
        }
        
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
            del creation_tasks[task_id]
    
    cleanup_thread = threading.Thread(target=cleanup_task)
    cleanup_thread.daemon = True
    cleanup_thread.start()


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return templates.TemplateResponse("errors/404.html", {
        "request": request,
        "status_code": 404,
        "message": "The page you're looking for doesn't exist."
    }, status_code=404)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc):
    """Handle general exceptions"""
    return templates.TemplateResponse("errors/500.html", {
        "request": request,
        "status_code": 500,
        "message": "Something went wrong. Please try again later."
    }, status_code=500)


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in user from session cookie"""
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        return user
    except JWTError:
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


def admin_exists(db: Session) -> bool:
    """Check if any admin user exists"""
    return db.query(AdminUser).first() is not None


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, error: str = None):
    """First-launch setup page - create admin account"""
    db = next(get_db())
    if admin_exists(db):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("auth/setup.html", {
        "request": request,
        "error": error
    })


@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle setup form - create first admin"""
    if admin_exists(db):
        return RedirectResponse(url="/login")

    if password != confirm_password:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Passwords do not match"
        })

    if len(password) < 6:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Password must be at least 6 characters"
        })

    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        return templates.TemplateResponse("auth/setup.html", {
            "request": request,
            "error": "Username already taken"
        })

    admin = AdminUser(
        username=username,
        password_hash=get_password_hash(password),
        is_active=True,
        is_first_login=True
    )
    db.add(admin)
    db.commit()

    access_token = create_access_token(data={"sub": admin.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Show login page"""
    db = next(get_db())
    if not admin_exists(db):
        return RedirectResponse(url="/setup")

    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": error
    })


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission"""
    user = db.query(AdminUser).filter(AdminUser.username == username).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    if not user.is_active:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Account is disabled"
        })

    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=1800)
    return response


@app.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
    page: int = 1,
    search: str = ""
):
    """Admin dashboard with LXD instance stats"""
    total_instances = 0
    running_instances = 0
    lxd_connected = False
    instances = []
    
    try:
        settings = db.query(LXDSettings).first()
        if settings:
            from lxd_client import get_lxd_client
            if settings.use_socket:
                client = get_lxd_client(
                    use_socket=True,
                    verify_ssl=settings.verify_ssl,
                    cert=settings.client_cert,
                    key=settings.client_key
                )
            elif settings.server_url:
                client = get_lxd_client(
                    settings.server_url,
                    verify_ssl=settings.verify_ssl,
                    cert=settings.client_cert,
                    key=settings.client_key
                )
            if client:
                all_instances = client.instances.all()
                total_instances = len(all_instances)
                running_instances = sum(1 for i in all_instances if i.status == "Running")
                lxd_connected = True
                
                # Get instance details
                for inst in all_instances:
                    try:
                        cpu = 'N/A'
                        memory_usage = 'N/A'
                        memory_allocated = 'N/A'

                        # Get allocated resources from instance config
                        # CPU: limits.cpu (can be number of cores or CPU set)
                        allocated_cpu = inst.config.get('limits.cpu')
                        if allocated_cpu:
                            cpu = allocated_cpu

                        # Memory: limits.memory or boot.memory (with unit suffix like MB, GB)
                        allocated_memory = inst.config.get('limits.memory') or inst.config.get('boot.memory')
                        if allocated_memory:
                            memory_allocated = allocated_memory

                        # For running instances: get actual usage from state
                        if inst.status == 'Running':
                            try:
                                state = inst.state
                                cpu_state = getattr(state, 'cpu', None)
                                memory_state = getattr(state, 'memory', None)

                                # Extract actual usage values from state objects
                                # For VMs: requires QEMU guest agent to be running
                                if memory_state and hasattr(memory_state, 'usage'):
                                    memory_usage = memory_state.usage  # in bytes
                            except Exception:
                                pass

                        # Format memory as usage/allocated if both available
                        if memory_usage != 'N/A' and memory_allocated != 'N/A':
                            memory = f"{memory_usage}/{memory_allocated}"
                        elif memory_allocated != 'N/A':
                            memory = memory_allocated
                        else:
                            # No allocated memory set - VM uses LXD defaults
                            if memory_usage != 'N/A':
                                memory = memory_usage  # Show usage only
                            else:
                                memory = 'N/A'

                        # If CPU is still N/A, check if it's a VM without limits
                        if cpu == 'N/A' and inst.type == 'virtual-machine':
                            cpu = 'default'  # LXD default CPU allocation

                        instances.append({
                            'name': inst.name,
                            'status': inst.status,
                            'type': inst.type,
                            'cpu': cpu,
                            'memory': memory,
                        })
                    except Exception:
                        instances.append({
                            'name': inst.name,
                            'status': inst.status,
                            'type': inst.type,
                            'cpu': 'N/A',
                            'memory': 'N/A',
                        })
                
                # Filter by search
                if search:
                    instances = [i for i in instances if search.lower() in i['name'].lower()]
                
                # Paginate
                per_page = 10
                total_pages = (len(instances) + per_page - 1) // per_page
                start = (page - 1) * per_page
                end = start + per_page
                instances = instances[start:end]
    except Exception:
        lxd_connected = False
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "username": user.username,
        "is_first_login": user.is_first_login,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_instances": total_instances,
        "running_instances": running_instances,
        "lxd_connected": lxd_connected,
        "instances": instances,
        "page": page,
        "search": search,
        "vm_defaults": db.query(VMDefaultSettings).first()
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
    lxd_success: str = None,
    lxd_error: str = None,
    password_success: str = None,
    password_error: str = None,
    vm_success: str = None,
    vm_error: str = None
):
    """Settings page - change password, LXD configuration, and VM defaults"""
    lxd_settings = db.query(LXDSettings).first()
    vm_settings = db.query(VMDefaultSettings).first()

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "lxd_settings": lxd_settings,
        "vm_settings": vm_settings,
        "lxd_success": lxd_success,
        "lxd_error": lxd_error,
        "password_success": password_success,
        "password_error": password_error,
        "vm_success": vm_success,
        "vm_error": vm_error
    })


@app.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_auth)
):
    """Handle password change"""
    if len(new_password) < 6:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": "New password must be at least 6 characters"
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": "New passwords do not match"
        })

    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("admin/settings.html", {
            "request": request,
            "username": user.username,
            "lxd_settings": db.query(LXDSettings).first(),
            "password_error": "Current password is incorrect"
        })

    user.password_hash = get_password_hash(new_password)
    user.is_first_login = False
    db.commit()

    return RedirectResponse(url="/settings?password_success=true", status_code=303)


@app.post("/settings/lxd")
async def save_lxd_settings(
    request: Request,
    server_url: str = Form(""),
    use_socket: str = Form("off"),
    client_cert: str = Form(""),
    client_key: str = Form(""),
    verify_ssl: str = Form("off"),
    db: Session = Depends(get_db)
):
    """Save LXD connection settings"""
    settings = db.query(LXDSettings).first()
    
    if settings:
        settings.server_url = server_url if server_url else None
        settings.use_socket = use_socket == "on"
        settings.client_cert = client_cert if client_cert else None
        settings.client_key = client_key if client_key else None
        settings.verify_ssl = verify_ssl == "on"
    else:
        settings = LXDSettings(
            server_url=server_url if server_url else None,
            use_socket=use_socket == "on",
            client_cert=client_cert if client_cert else None,
            client_key=client_key if client_key else None,
            verify_ssl=verify_ssl == "on"
        )
        db.add(settings)
    
    db.commit()
    
    return RedirectResponse(url="/settings?lxd_success=Settings saved successfully", status_code=303)


@app.post("/settings/lxd/test")
async def test_lxd_connection(request: Request, db: Session = Depends(get_db)):
    """Test LXD connection"""
    settings = db.query(LXDSettings).first()
    
    if not settings:
        return JSONResponse({"success": False, "message": "No LXD settings configured"})
    
    # Socket connection doesn't require certificate
    if not settings.use_socket and (not settings.client_cert or not settings.client_key):
        return JSONResponse({"success": False, "message": "Certificate and Key are required for HTTPS connection. Please paste them in the settings form."})
    
    try:
        from lxd_client import get_lxd_client
        if settings.use_socket:
            client = get_lxd_client(
                use_socket=True,
                verify_ssl=settings.verify_ssl,
                cert=settings.client_cert,
                key=settings.client_key
            )
        else:
            client = get_lxd_client(
                settings.server_url,
                verify_ssl=settings.verify_ssl,
                cert=settings.client_cert,
                key=settings.client_key
            )
        server = client.api.get().json()
        connection_type = "Unix socket" if settings.use_socket else "HTTPS"
        return JSONResponse({
            "success": True, 
            "message": f"Connected to LXD server via {connection_type}: {server.get('environment', {}).get('server_name', 'unknown')}"
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/settings/lxd/generate-cert")
async def generate_certificate(request: Request):
    """Generate client certificate for LXD authentication"""
    try:
        cert_pem, key_pem = generate_client_certificate("fastapi-client")
        return JSONResponse({
            "success": True,
            "certificate": cert_pem,
            "key": key_pem,
            "message": "Certificate generated! Copy the certificate and add it to LXD trust store."
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/settings/vm")
async def save_vm_settings(
    request: Request,
    cpu: int = Form(...),
    memory: int = Form(...),
    disk: int = Form(...),
    db: Session = Depends(get_db)
):
    """Save default VM settings"""
    settings = db.query(VMDefaultSettings).first()

    if settings:
        settings.cpu = cpu
        settings.memory = memory
        settings.disk = disk
    else:
        settings = VMDefaultSettings(
            cpu=cpu,
            memory=memory,
            disk=disk
        )
        db.add(settings)

    db.commit()

    return RedirectResponse(url="/settings?vm_success=VM defaults saved successfully", status_code=303)


@app.post("/instances/create")
async def create_instance(request: Request, db: Session = Depends(get_db)):
    """Create a new instance (VM or container)"""
    try:
        data = await request.json()
        req = InstanceCreateRequest(**data)
        
        # Validate instance name
        if not req.name or not req.name.replace("-", "").replace("_", "").isalnum():
            return JSONResponse({
                "success": False,
                "message": "Instance name must be alphanumeric (hyphens and underscores allowed)"
            })

        # Get LXD settings BEFORE starting background thread
        settings = db.query(LXDSettings).first()
        if not settings:
            return JSONResponse({
                "success": False,
                "message": "LXD not configured. Please configure LXD in Settings first."
            })

        lxd_settings = {
            "use_socket": settings.use_socket,
            "server_url": settings.server_url,
            "verify_ssl": settings.verify_ssl,
            "client_cert": settings.client_cert,
            "client_key": settings.client_key
        }

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Start background task
        thread = threading.Thread(
            target=track_instance_creation,
            args=(task_id, req.name, req.cpu, req.ram, req.disk, req.type, lxd_settings)
        )
        thread.daemon = True
        thread.start()

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": f"Creating {req.type} '{req.name}'..."
        })
    except Exception as e:
        print(f"[ERROR] create_instance: {e}")  # Error log
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/instances/create/status/{task_id}")
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


@app.post("/instances/{instance_name}/start")
async def start_instance(instance_name: str, request: Request, db: Session = Depends(get_db)):
    """Start an LXD instance"""
    settings = db.query(LXDSettings).first()
    
    if not settings:
        return JSONResponse({"success": False, "message": "LXD not configured"})
    
    try:
        from lxd_client import get_lxd_client
        if settings.use_socket:
            client = get_lxd_client(use_socket=True, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)
        else:
            client = get_lxd_client(settings.server_url, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)
        
        instance = client.instances.get(instance_name)
        instance.start()
        return JSONResponse({"success": True, "message": f"Instance {instance_name} started"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.post("/instances/{instance_name}/stop")
async def stop_instance(instance_name: str, request: Request, db: Session = Depends(get_db)):
    """Stop an LXD instance"""
    settings = db.query(LXDSettings).first()

    if not settings:
        return JSONResponse({"success": False, "message": "LXD not configured"})

    try:
        from lxd_client import get_lxd_client
        if settings.use_socket:
            client = get_lxd_client(use_socket=True, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)
        else:
            client = get_lxd_client(settings.server_url, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)

        instance = client.instances.get(instance_name)
        instance.stop()
        return JSONResponse({"success": True, "message": f"Instance {instance_name} stopped"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.delete("/instances/{instance_name}/delete")
async def delete_instance(instance_name: str, request: Request, db: Session = Depends(get_db), force: bool = False):
    """Delete an LXD instance"""
    settings = db.query(LXDSettings).first()

    if not settings:
        return JSONResponse({"success": False, "message": "LXD not configured"})

    try:
        from lxd_client import get_lxd_client
        if settings.use_socket:
            client = get_lxd_client(use_socket=True, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)
        else:
            client = get_lxd_client(settings.server_url, verify_ssl=settings.verify_ssl, cert=settings.client_cert, key=settings.client_key)

        instance = client.instances.get(instance_name)
        
        # Stop instance first if running and not force delete
        if instance.status == "Running" and not force:
            return JSONResponse({
                "success": False,
                "message": f"Instance '{instance_name}' is running. Stop it first or check 'Force delete'."
            })
        
        # Delete the instance
        instance.delete(wait=True)
        return JSONResponse({"success": True, "message": f"Instance '{instance_name}' deleted successfully"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/root-redirect", response_class=HTMLResponse)
async def root_redirect(request: Request, user: AdminUser = Depends(get_current_user)):
    """Root redirect"""
    db = next(get_db())
    if not admin_exists(db):
        return RedirectResponse(url="/setup")
    if user:
        return RedirectResponse(url="/")
    return RedirectResponse(url="/login")


from database import SessionLocal
