from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User
from app.auth import decode_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return None
    user = db.query(User).filter(User.id == user_id_int).first()
    return user


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
