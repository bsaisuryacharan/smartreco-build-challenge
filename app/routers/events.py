import json
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.models import User, UserEvent, Recommendation, Product

router = APIRouter()
logger = logging.getLogger(__name__)


async def _parse_body(request: Request) -> dict:
    """Parse body from either application/json or text/plain (sendBeacon)."""
    content_type = request.headers.get("content-type", "")
    raw = await request.body()
    try:
        return json.loads(raw)
    except Exception:
        return {}


@router.post("/events/batch")
async def batch_events(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    body = await _parse_body(request)
    raw_events = body.get("events", [])

    inserted_count = 0
    for ev in raw_events:
        event_type = ev.get("event_type", "page_view")
        product_id = ev.get("product_id")
        metadata = ev.get("metadata", {})

        user_event = UserEvent(
            user_id=current_user.id,
            event_type=event_type,
            product_id=int(product_id) if product_id else None,
            metadata_=json.dumps(metadata) if metadata else None,
        )
        db.add(user_event)
        inserted_count += 1

    if inserted_count > 0:
        db.commit()

    background_tasks.add_task(check_and_trigger_recommendation, current_user.id)

    return JSONResponse({"ok": True, "inserted": inserted_count})


def check_and_trigger_recommendation(user_id: int) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        last_rec = (
            db.query(Recommendation)
            .filter(Recommendation.user_id == user_id)
            .order_by(Recommendation.generated_at.desc())
            .first()
        )

        if last_rec:
            events_since_count = (
                db.query(UserEvent)
                .filter(
                    UserEvent.user_id == user_id,
                    UserEvent.created_at > last_rec.generated_at,
                )
                .count()
            )
            last_rec_age = datetime.utcnow() - last_rec.generated_at
            should_trigger = (
                events_since_count >= 5 and last_rec_age > timedelta(minutes=5)
            )
        else:
            total_events = (
                db.query(UserEvent)
                .filter(UserEvent.user_id == user_id)
                .count()
            )
            events_since_count = total_events
            should_trigger = total_events >= 3

        if not should_trigger:
            return

        recent_events_raw = (
            db.query(UserEvent)
            .filter(UserEvent.user_id == user_id)
            .order_by(UserEvent.created_at.desc())
            .limit(20)
            .all()
        )

        enriched_events = []
        for ev in recent_events_raw:
            meta = {}
            if ev.metadata_:
                try:
                    meta = json.loads(ev.metadata_)
                except Exception:
                    meta = {}

            category = ""
            if ev.product_id:
                product = db.query(Product).filter(Product.id == ev.product_id).first()
                if product:
                    category = product.category
                    meta["title"] = product.title

            enriched_events.append(
                {
                    "event_type": ev.event_type,
                    "product_id": ev.product_id,
                    "metadata_": meta,
                    "category": category,
                }
            )

        from app.services.agent import run_agent

        result = run_agent(user_id, enriched_events)

        rec = Recommendation(
            user_id=user_id,
            narrative=result["narrative"],
            product_ids=json.dumps(result["product_ids"]),
            trigger_event_count=events_since_count,
        )
        db.add(rec)
        db.commit()
        logger.info(
            f"Recommendation generated for user {user_id} "
            f"(products: {result['product_ids']})"
        )

    except Exception as exc:
        logger.error(f"check_and_trigger_recommendation failed for user {user_id}: {exc}")
    finally:
        db.close()
