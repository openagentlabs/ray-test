"""
Authentication service for user management and JWT token handling
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.user_database import user_db
from app.models.schemas import UserInDB, UserLogin, TokenData

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "your-secret-key-here-change-in-production"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 60 min — matches Cognito access token validity
REFRESH_TOKEN_EXPIRE_DAYS = 3

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user"""
    user = user_db.get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
):
    """Create a JWT access token. Optional ``session_id`` is emitted as claim ``sid``."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    if session_id:
        to_encode["sid"] = session_id
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(username: str) -> str:
    """Create a signed JWT refresh token with expiry and token type."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": username, "type": "refresh", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_refresh_token_expiry() -> datetime:
    """Get refresh token expiry timestamp."""
    return datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode a JWT access token (includes optional ``sid`` session claim)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return TokenData(username=username, session_id=payload.get("sid"))
    except JWTError:
        return None


def resolve_user_from_refresh_token(refresh_token: str) -> Optional[UserInDB]:
    """Validate refresh JWT + DB entry and return the user (used for refresh + session issuance)."""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        username = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    verified = user_db.verify_refresh_token(refresh_token)
    if not verified:
        return None
    _token_record_id, user_id = verified
    user = user_db.get_user_by_id(user_id)
    if not user or not user.is_active:
        return None
    return user

def get_current_user(token: str) -> Optional[UserInDB]:
    """Get current user from token"""
    token_data = verify_token(token)
    if token_data is None:
        return None
    user = user_db.get_user_by_username(username=token_data.username)
    if user is None:
        return None
    return user

def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Validate refresh JWT + DB entry and return a new access token (no new server session id)."""
    user = resolve_user_from_refresh_token(refresh_token)
    if not user:
        return None
    access_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token({"sub": user.username}, expires_delta=access_expires)
