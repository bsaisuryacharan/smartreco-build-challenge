import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def send_daily_digest() -> None:
    """Runs daily: sends personalized recommendation emails to active users."""
    from app.database import SessionLocal
    from app.models import User, UserEvent, Recommendation

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        active_ids = (
            db.query(UserEvent.user_id)
            .filter(UserEvent.created_at >= cutoff)
            .distinct()
            .all()
        )
        logger.info("Daily digest: %d active users", len(active_ids))

        for (uid,) in active_ids:
            user = db.get(User, uid)
            if not user:
                continue
            rec = (
                db.query(Recommendation)
                .filter(Recommendation.user_id == uid)
                .order_by(Recommendation.generated_at.desc())
                .first()
            )
            if not rec:
                # Generate one on the spot if missing
                _generate_and_store(uid, db)
                rec = (
                    db.query(Recommendation)
                    .filter(Recommendation.user_id == uid)
                    .order_by(Recommendation.generated_at.desc())
                    .first()
                )
            if rec:
                _send_email(user.email, rec.narrative)
    finally:
        db.close()


def _generate_and_store(user_id: int, db) -> None:
    from app.models import UserEvent, Product, Recommendation
    from app.services.agent import run_agent

    events_raw = (
        db.query(UserEvent)
        .filter(UserEvent.user_id == user_id)
        .order_by(UserEvent.created_at.desc())
        .limit(20)
        .all()
    )
    enriched = []
    for ev in events_raw:
        meta = {}
        if ev.metadata_:
            try:
                meta = json.loads(ev.metadata_)
            except Exception:
                pass
        category = ""
        if ev.product_id:
            p = db.get(Product, ev.product_id)
            if p:
                category = p.category
                meta["title"] = p.title
        enriched.append({
            "event_type": ev.event_type,
            "product_id": ev.product_id,
            "metadata_": meta,
            "category": category,
        })

    try:
        result = run_agent(user_id, enriched)
        rec = Recommendation(
            user_id=user_id,
            narrative=result["narrative"],
            product_ids=json.dumps(result["product_ids"]),
            trigger_event_count=len(enriched),
        )
        db.add(rec)
        db.commit()
    except Exception as exc:
        logger.error("Digest agent run failed for user %d: %s", user_id, exc)


def _send_email(to_email: str, narrative: str) -> None:
    subject = "Your SmartReco Daily Learning Digest"
    body = (
        f"Hi there,\n\n"
        f"Here's your personalized learning digest for today:\n\n"
        f"{narrative}\n\n"
        f"Keep learning — your next breakthrough is just one course away!\n\n"
        f"— The SmartReco Team"
    )

    if not settings.SMTP_HOST:
        logger.info("[DIGEST] %s | %s...", to_email, narrative[:80])
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.DIGEST_FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Digest sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send digest to %s: %s", to_email, exc)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        send_daily_digest,
        trigger="cron",
        hour=settings.DIGEST_HOUR,
        minute=0,
        id="daily_digest",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — daily digest fires at %02d:00", settings.DIGEST_HOUR)
    return _scheduler