from datetime import datetime
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_admin
from app.models import Product, User
from app.services.vector_store import upsert_product, delete_product

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def admin_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    return templates.TemplateResponse(
        request, "admin/products.html",
        {"current_user": current_user, "products": products, "editing": None},
    )


@router.get("/products/new", response_class=HTMLResponse)
def new_product_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    return templates.TemplateResponse(
        request, "admin/products.html",
        {"current_user": current_user, "products": products, "editing": None, "show_add_form": True},
    )


@router.post("/products", response_class=HTMLResponse)
def create_product(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    thumbnail_url: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = Product(
        title=title,
        description=description,
        category=category,
        price=price,
        thumbnail_url=thumbnail_url if thumbnail_url.strip() else None,
        vector_id="pending",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    product.vector_id = f"product_{product.id}"
    db.commit()
    db.refresh(product)

    upsert_product(product)

    return RedirectResponse(url="/admin/", status_code=302)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_form(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse(url="/admin/", status_code=302)
    products = db.query(Product).order_by(Product.id.desc()).all()
    return templates.TemplateResponse(
        request, "admin/products.html",
        {"current_user": current_user, "products": products, "editing": product},
    )


@router.post("/products/{product_id}", response_class=HTMLResponse)
def update_product(
    product_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    thumbnail_url: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse(url="/admin/", status_code=302)

    product.title = title
    product.description = description
    product.category = category
    product.price = price
    product.thumbnail_url = thumbnail_url if thumbnail_url.strip() else None
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)

    upsert_product(product)

    return RedirectResponse(url="/admin/", status_code=302)


@router.post("/products/{product_id}/delete", response_class=HTMLResponse)
def delete_product_route(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        delete_product(product.vector_id)
        db.delete(product)
        db.commit()
    return RedirectResponse(url="/admin/", status_code=302)
