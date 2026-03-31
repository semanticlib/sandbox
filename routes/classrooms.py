"""Classrooms page routes - manages Classrooms"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AdminUser, LXDSettings, Classroom
from core.templates import templates
from core.config import settings

router = APIRouter()


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


@router.get("/classrooms", response_class=HTMLResponse)
async def classrooms_page(
    request: Request,
    user: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Classrooms management page"""
    return templates.TemplateResponse("admin/classrooms.html", {
        "request": request,
        "username": user.username,
    })

# ============================================================
# Cloud-init template routes (API)
# ============================================================

@router.get("/classrooms/cloud-init/template")
async def get_default_cloud_init_template(template_type: str = "container"):
    """Return the default cloud-init template text for VM or Container."""
    from services.cloud_init_service import DEFAULT_CLOUD_INIT_TEMPLATE_VM, DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER

    if template_type == "container":
        template = DEFAULT_CLOUD_INIT_TEMPLATE_CONTAINER
    else:
        template = DEFAULT_CLOUD_INIT_TEMPLATE_VM

    return JSONResponse({"success": True, "template": template})


# ============================================================
# Classroom CRUD (JSON API)
# ============================================================

@router.get("/api/classrooms")
async def get_classrooms(db: Session = Depends(get_db)):
    """Return all classrooms."""
    try:
        classrooms = db.query(Classroom).all()
        return JSONResponse({
            "success": True,
            "classrooms": [
                {
                    "id": c.id,
                    "name": c.name,
                    "username": c.username,
                    "image_type": c.image_type,
                    "cloud_init": c.cloud_init or "",
                    "local_forwards": c.local_forwards or "",
                    "image_fingerprint": c.image_fingerprint,
                    "image_description": c.image_description,
                }
                for c in classrooms
            ]
        })
    except Exception as exc:
        import logging
        logging.exception("Error fetching classrooms")
        return JSONResponse({"success": False, "message": str(exc)})


@router.get("/api/classrooms/{classroom_id}")
async def get_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """Return a single classroom by ID."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)
        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "cloud_init": classroom.cloud_init or "",
                "local_forwards": classroom.local_forwards or "",
                "image_fingerprint": classroom.image_fingerprint,
                "image_description": classroom.image_description,
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error fetching classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.post("/api/classrooms")
async def create_classroom(request: Request, db: Session = Depends(get_db)):
    """Create a new classroom."""
    try:
        data = await request.json()
        name = (data.get("name") or "").strip()
        if not name:
            return JSONResponse({"success": False, "message": "Classroom name is required"})

        username = (data.get("username") or "").strip()
        if not username:
            return JSONResponse({"success": False, "message": "Default username is required"})

        # Check if name already exists
        existing = db.query(Classroom).filter(Classroom.name == name).first()
        if existing:
            return JSONResponse({"success": False, "message": "Classroom name already exists"})

        classroom = Classroom(
            name=name,
            username=username,
            image_type=data.get("image_type", "container"),
            cloud_init=data.get("cloud_init"),
            local_forwards=data.get("local_forwards"),
            image_fingerprint=data.get("image_fingerprint"),
            image_description=data.get("image_description"),
        )
        db.add(classroom)
        db.commit()
        db.refresh(classroom)

        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "cloud_init": classroom.cloud_init or "",
                "local_forwards": classroom.local_forwards or "",
                "image_fingerprint": classroom.image_fingerprint,
                "image_description": classroom.image_description,
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error creating classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.put("/api/classrooms/{classroom_id}")
async def update_classroom(classroom_id: int, request: Request, db: Session = Depends(get_db)):
    """Update an existing classroom."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)

        data = await request.json()

        # Check if name is being changed and if it already exists
        new_name = data.get("name", classroom.name).strip()
        if new_name != classroom.name:
            existing = db.query(Classroom).filter(Classroom.name == new_name).first()
            if existing:
                return JSONResponse({"success": False, "message": "Classroom name already exists"})
            classroom.name = new_name

        new_username = (data.get("username") or "").strip()
        if not new_username:
            return JSONResponse({"success": False, "message": "Default username is required"})
        classroom.username = new_username

        classroom.image_type = data.get("image_type", classroom.image_type)
        classroom.cloud_init = data.get("cloud_init")
        classroom.local_forwards = data.get("local_forwards")
        classroom.image_fingerprint = data.get("image_fingerprint")
        classroom.image_description = data.get("image_description")

        db.commit()
        db.refresh(classroom)

        return JSONResponse({
            "success": True,
            "classroom": {
                "id": classroom.id,
                "name": classroom.name,
                "username": classroom.username,
                "image_type": classroom.image_type,
                "cloud_init": classroom.cloud_init or "",
                "local_forwards": classroom.local_forwards or "",
                "image_fingerprint": classroom.image_fingerprint,
                "image_description": classroom.image_description,
            }
        })
    except Exception as exc:
        import logging
        logging.exception("Error updating classroom")
        return JSONResponse({"success": False, "message": str(exc)})


@router.delete("/api/classrooms/{classroom_id}")
async def delete_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """Delete a classroom."""
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return JSONResponse({"success": False, "message": "Classroom not found"}, status_code=404)

        db.delete(classroom)
        db.commit()

        return JSONResponse({"success": True, "message": f"Classroom '{classroom.name}' deleted"})
    except Exception as exc:
        import logging
        logging.exception("Error deleting classroom")
        return JSONResponse({"success": False, "message": str(exc)})
