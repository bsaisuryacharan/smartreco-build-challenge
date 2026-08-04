import json
import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.models import User, Recommendation, Product

router = APIRouter()
logger = logging.getLogger(__name__)


def _hydrate_recommendation(rec: Recommendation, db: Session) -> dict:
    """Expand stored product_ids into full product objects."""
    try:
        pid_list = json.loads(rec.product_ids)
    except Exception:
        pid_list = []

    products_raw = db.query(Product).filter(Product.id.in_(pid_list)).all()
    # Preserve the ranked order from the agent
    pid_order = {pid: idx for idx, pid in enumerate(pid_list)}
    products_sorted = sorted(products_raw, key=lambda p: pid_order.get(p.id, 999))

    return {
        "narrative": rec.narrative,
        "products": [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "category": p.category,
                "price": p.price,
                "thumbnail_url": p.thumbnail_url,
            }
            for p in products_sorted
        ],
        "generated_at": rec.generated_at.isoformat(),
    }


@router.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    rec = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == current_user.id)
        .order_by(Recommendation.generated_at.desc())
        .first()
    )
    if not rec:
        return JSONResponse({"narrative": None, "products": [], "generated_at": None})
    return JSONResponse(_hydrate_recommendation(rec, db))


@router.post("/recommendations/generate")
def force_generate(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Force-trigger recommendation generation (useful for testing)."""
    from app.routers.events import check_and_trigger_recommendation

    # Lower the threshold: mark last rec as old by temporarily dropping it
    # so the trigger logic always fires — this is a dev/test endpoint
    background_tasks.add_task(_force_run_agent, current_user.id)
    return JSONResponse({"ok": True, "message": "Generation queued"})


def _force_run_agent(user_id: int) -> None:
    import json
    from app.database import SessionLocal
    from app.models import UserEvent, Recommendation, Product
    from app.services.agent import run_agent

    db = SessionLocal()
    try:
        recent_events_raw = (
            db.query(UserEvent)
            .filter(UserEvent.user_id == user_id)
            .order_by(UserEvent.created_at.desc())
            .limit(20)
            .all()
        )
        enriched = []
        for ev in recent_events_raw:
            meta = {}
            if ev.metadata_:
                try:
                    meta = json.loads(ev.metadata_)
                except Exception:
                    pass
            category = ""
            if ev.product_id:
                p = db.query(Product).filter(Product.id == ev.product_id).first()
                if p:
                    category = p.category
                    meta["title"] = p.title
            enriched.append({
                "event_type": ev.event_type,
                "product_id": ev.product_id,
                "metadata_": meta,
                "category": category,
            })

        result = run_agent(user_id, enriched)
        rec = Recommendation(
            user_id=user_id,
            narrative=result["narrative"],
            product_ids=json.dumps(result["product_ids"]),
            trigger_event_count=len(enriched),
        )
        db.add(rec)
        db.commit()
        logger.info("Force-generated recommendation for user %d", user_id)
    except Exception as exc:
        logger.error("_force_run_agent failed for user %d: %s", user_id, exc)
    finally:
        db.close()