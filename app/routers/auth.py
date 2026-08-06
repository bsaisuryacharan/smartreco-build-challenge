from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models import User
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request, "auth/login.html", {"current_user": None, "error": None}
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"current_user": None, "error": "Invalid email or password."},
            status_code=400,
        )
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request, "auth/register.html", {"current_user": None, "error": None}
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()

    if password != confirm_password:
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"current_user": None, "error": "Passwords do not match."},
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"current_user": None, "error": "Password must be at least 6 characters."},
            status_code=400,
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            request, "auth/register.html",
            {"current_user": None, "error": "An account with that email already exists."},
            status_code=400,
        )

    user = User(
        email=email,
        password_hash=hash_password(password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
