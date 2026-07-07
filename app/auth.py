from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import User, Organization, get_db, settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(credentials: HTTPAuthCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_token(token)

    user_id: Optional[str] = payload.get("sub")
    org_id: Optional[str] = payload.get("org_id")

    if user_id is None or org_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return user


async def get_current_org(current_user: User = Depends(get_current_user)) -> Organization:
    return current_user.organization


def check_rate_limit(org: Organization, db: Session) -> bool:
    """Check if org has exceeded monthly query limit based on plan."""
    from app.models import Query

    if org.plan == "free":
        limit = 5
    elif org.plan == "pro":
        limit = 1000
    elif org.plan == "business":
        limit = None  # Unlimited
    else:
        limit = None

    if limit is None:
        return True

    # Count queries in last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    query_count = db.query(Query).filter(
        Query.org_id == org.id,
        Query.created_at >= thirty_days_ago
    ).count()

    return query_count < limit
