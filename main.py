from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jinja2 import filters

from database import engine, get_db, Base
from models import AdminUser, LXDSettings
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
        "search": search
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
    lxd_success: str = None,
    lxd_error: str = None,
    password_success: str = None,
    password_error: str = None
):
    """Settings page - change password and LXD configuration"""
    lxd_settings = db.query(LXDSettings).first()
    
    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": user.username,
        "lxd_settings": lxd_settings,
        "lxd_success": lxd_success,
        "lxd_error": lxd_error,
        "password_success": password_success,
        "password_error": password_error
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
