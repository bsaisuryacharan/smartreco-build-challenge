from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models import Product, Recommendation, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def catalog_index(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=48),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = db.query(Product).count()
    offset = (page - 1) * per_page
    products = (
        db.query(Product)
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    total_pages = max(1, (total + per_page - 1) // per_page)

    latest_rec = None
    rec_products = []
    if current_user:
        latest_rec = (
            db.query(Recommendation)
            .filter(Recommendation.user_id == current_user.id)
            .order_by(Recommendation.generated_at.desc())
            .first()
        )
        if latest_rec:
            import json
            try:
                pid_list = json.loads(latest_rec.product_ids)
                rec_products = (
                    db.query(Product).filter(Product.id.in_(pid_list)).all()
                )
            except Exception:
                rec_products = []

    return templates.TemplateResponse(
        "catalog/index.html",
        {
            "request": request,
            "current_user": current_user,
            "products": products,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "latest_rec": latest_rec,
            "rec_products": rec_products,
        },
    )


@router.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")

    latest_rec = None
    rec_products = []
    if current_user:
        latest_rec = (
            db.query(Recommendation)
            .filter(Recommendation.user_id == current_user.id)
            .order_by(Recommendation.generated_at.desc())
            .first()
        )
        if latest_rec:
            import json
            try:
                pid_list = json.loads(latest_rec.product_ids)
                rec_products = (
                    db.query(Product).filter(Product.id.in_(pid_list)).all()
                )
            except Exception:
                rec_products = []

    return templates.TemplateResponse(
        "catalog/product.html",
        {
            "request": request,
            "current_user": current_user,
            "product": product,
            "latest_rec": latest_rec,
            "rec_products": rec_products,
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = []
    if q.strip():
        from app.services.vector_store import search_products

        try:
            results = search_products(q, n_results=20)
            if results:
                pid_list = [int(r["product_id"]) for r in results]
                db_products = (
                    db.query(Product).filter(Product.id.in_(pid_list)).all()
                )
                pid_order = {pid: idx for idx, pid in enumerate(pid_list)}
                products = sorted(
                    db_products, key=lambda p: pid_order.get(p.id, 999)
                )
        except Exception:
            pass

        if not products:
            like = f"%{q}%"
            products = (
                db.query(Product)
                .filter(
                    (Product.title.ilike(like)) | (Product.description.ilike(like))
                )
                .limit(20)
                .all()
            )

    return templates.TemplateResponse(
        "catalog/search.html",
        {
            "request": request,
            "current_user": current_user,
            "products": products,
            "query": q,
        },
    )
