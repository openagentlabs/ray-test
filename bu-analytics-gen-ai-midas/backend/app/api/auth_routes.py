"""
Authentication API routes for user login, registration, and management
"""

import gc
import time
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.models.schemas import (
    UserCreate, UserUpdate, User, UserLogin,
)
from app.models.user_database import user_db
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    resolve_user_from_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_refresh_token,
    get_refresh_token_expiry,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.config import settings as app_settings
from app.core.logging_config import get_logger
from app.core.pod_manager.deps import get_pod_manager_service
from app.core.session.contracts import ISessionAuthenticator
from app.core.session.session_http_responses import build_session_expired_detail
from app.services.pod_manager_service import PodManagerServiceError

logger = get_logger(__name__)

# Initialize router
auth_router = APIRouter()

# Security scheme
security = HTTPBearer()

# Response models
class TokenResponse:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str

class UserResponse:
    id: int
    username: str
    full_name: str
    email: str
    is_active: bool
    created_at: str
    updated_at: str
# Refresh token request model
class RefreshRequest(BaseModel):
    refresh_token: str


async def get_current_user_dependency(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Resolve current user from JWT and optional server-side session (Redis / memory).
    SessionValidationMiddleware may already validate the Bearer token and set request.state.session_user.
    """
    cached = getattr(request.state, "session_user", None)
    if cached is not None:
        return cached
    sm: ISessionAuthenticator = request.app.state.session_manager
    user = await sm.authenticate_access_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_session_expired_detail(),
            headers={"WWW-Authenticate": "Bearer"},
        )
    pod_manager_service = get_pod_manager_service(request)
    if pod_manager_service is not None:
        try:
            await pod_manager_service.ensure_lease(user.username)
        except PodManagerServiceError as exc:
            logger.warning(
                "pod_manager lease ensure failed for user '%s': %s",
                user.username,
                str(exc),
            )
    return user

def _require_legacy_password_login() -> None:
    """Gate for legacy username/password endpoints. Cognito is the supported path."""
    if not app_settings.ENABLE_LEGACY_PASSWORD_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Legacy password login is disabled. Use /api/v1/auth/cognito/login-url to "
                "begin the Cognito federated sign-in flow."
            ),
        )


@auth_router.post("/register", response_model=User)
async def register_user(user_create: UserCreate):
    """
    Register a new user (legacy path; disabled by default).
    """
    _require_legacy_password_login()
    logger.info(f"User registration request for username: {user_create.username}")
    
    try:
        # Check if username already exists
        if user_db.user_exists(user_create.username):
            logger.warning(f"Registration failed: Username {user_create.username} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Create user
        created_user = user_db.create_user(user_create)
        
        if not created_user:
            logger.error(f"Failed to create user: {user_create.username}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        # Return user without password hash
        user_response = User(
            id=created_user.id,
            username=created_user.username,
            full_name=created_user.full_name,
            email=created_user.email,
            is_active=created_user.is_active,
            created_at=created_user.created_at,
            updated_at=created_user.updated_at
        )
        
        logger.info(f"User registered successfully: {created_user.username} (ID: {created_user.id})")
        return user_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@auth_router.post("/login")
async def login_user(request: Request, user_login: UserLogin, response: Response):
    """
    Login user and return access token (legacy path; disabled by default).
    """
    _require_legacy_password_login()
    logger.info(f"Login attempt for username: {user_login.username}")
    
    try:
        # Authenticate user
        user = authenticate_user(user_login.username, user_login.password)
        
        if not user:
            logger.warning(f"Login failed: Invalid credentials for username {user_login.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed: Inactive user {user_login.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        sm: ISessionAuthenticator = request.app.state.session_manager
        session_id = await sm.create_session(user.username)
        pod_manager_service = get_pod_manager_service(request)
        if pod_manager_service is not None:
            try:
                await pod_manager_service.acquire_lease(user.username)
            except PodManagerServiceError as exc:
                logger.warning("pod_manager lease acquire failed for '%s': %s", user.username, str(exc))
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires,
            session_id=session_id,
        )

        # Create and persist refresh token
        refresh_token = create_refresh_token(user.username)
        refresh_expires_at = get_refresh_token_expiry()
        persisted = user_db.create_refresh_token(user.id, refresh_token, refresh_expires_at)
        if not persisted:
            logger.error("Failed to persist refresh token")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create refresh token")

        # Optionally set HttpOnly cookie for refresh token (can also be sent in body)
        try:
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                samesite="lax",
                secure=False,
                max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
            )
        except Exception:
            # If cookies fail, we'll rely on body-only
            pass
        
        logger.info(f"User logged in successfully: {user.username} (ID: {user.id})")

        ttl_sec = sm.ttl_seconds

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            "refresh_token": refresh_token,
            "session_id": session_id,
            "session_created_at": int(time.time()),
            "session_ttl_seconds": ttl_sec,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "is_active": user.is_active
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@auth_router.get("/me", response_model=User)
async def get_current_user_info(current_user = Depends(get_current_user_dependency)):
    """
    Get current user information (requires authentication)
    """
    logger.info(f"User info request for: {current_user.username}")
    
    return User(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@auth_router.get("/users", response_model=List[User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(get_current_user_dependency)
):
    """
    List all users (requires authentication)
    """
    logger.info(f"List users request from: {current_user.username}")
    
    try:
        users = user_db.list_users(skip=skip, limit=limit)
        logger.info(f"Retrieved {len(users)} users")
        return users
        
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@auth_router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user = Depends(get_current_user_dependency)
):
    """
    Update user information (requires authentication)
    """
    logger.info(f"User update request for ID {user_id} from: {current_user.username}")
    
    try:
        # Check if user exists
        existing_user = user_db.get_user_by_id(user_id)
        if not existing_user:
            logger.warning(f"User update failed: User ID {user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user
        updated_user = user_db.update_user(user_id, user_update)
        
        if not updated_user:
            logger.error(f"Failed to update user ID {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
        
        logger.info(f"User updated successfully: {updated_user.username} (ID: {updated_user.id})")

        # If user was deactivated, revoke all refresh tokens
        if user_update.is_active is not None and not user_update.is_active:
            try:
                revoked_count = user_db.revoke_all_refresh_tokens_for_user(user_id)
                logger.info(f"Revoked {revoked_count} refresh tokens for deactivated user ID {user_id}")
            except Exception as e:
                logger.error(f"Failed to revoke tokens for user {user_id} on deactivation: {str(e)}")
        
        return User(
            id=updated_user.id,
            username=updated_user.username,
            full_name=updated_user.full_name,
            email=updated_user.email,
            is_active=updated_user.is_active,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@auth_router.post("/refresh")
async def refresh_token_endpoint(body: RefreshRequest, request: Request):
    """
    Exchange a refresh token for a new access token.
    """
    logger.info("Access token refresh request")
    try:
        provided_token = getattr(body, 'refresh_token', None)
        if not provided_token:
            # Try to read from cookie if body not provided
            provided_token = request.cookies.get("refresh_token")
        if not provided_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token")

        user = resolve_user_from_refresh_token(provided_token)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

        sm: ISessionAuthenticator = request.app.state.session_manager
        new_sid = await sm.create_session(user.username)
        pod_manager_service = get_pod_manager_service(request)
        if pod_manager_service is not None:
            try:
                await pod_manager_service.acquire_lease(user.username)
            except PodManagerServiceError as exc:
                logger.warning("pod_manager lease acquire failed for '%s': %s", user.username, str(exc))
        access_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access = create_access_token(
            data={"sub": user.username},
            expires_delta=access_expires,
            session_id=new_sid,
        )

        ttl_sec = sm.ttl_seconds

        return {
            "access_token": new_access,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": new_sid,
            "session_created_at": int(time.time()),
            "session_ttl_seconds": ttl_sec,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh token exchange failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@auth_router.post("/logout")
async def logout_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user=Depends(get_current_user_dependency),
):
    """
    Invalidate server-side session, revoke refresh tokens, and clear cookie on client.
    """
    try:
        sm: ISessionAuthenticator = request.app.state.session_manager
        await sm.invalidate_access_token(credentials.credentials)
        pod_manager_service = get_pod_manager_service(request)
        if pod_manager_service is not None:
            try:
                await pod_manager_service.release_lease(current_user.username)
            except PodManagerServiceError as exc:
                logger.warning("pod_manager lease release failed for '%s': %s", current_user.username, str(exc))
        revoked = user_db.revoke_all_refresh_tokens_for_user(current_user.id)
        logger.info(f"User {current_user.username} logged out, revoked {revoked} tokens")
        gc.collect()
        return {"message": "Logged out", "revoked": revoked}
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@auth_router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user = Depends(get_current_user_dependency)
):
    """
    Delete a user (requires authentication)
    """
    logger.info(f"User deletion request for ID {user_id} from: {current_user.username}")
    
    try:
        # Check if user exists
        existing_user = user_db.get_user_by_id(user_id)
        if not existing_user:
            logger.warning(f"User deletion failed: User ID {user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent self-deletion
        if user_id == current_user.id:
            logger.warning(f"User {current_user.username} attempted self-deletion")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # Delete user
        success = user_db.delete_user(user_id)
        
        if not success:
            logger.error(f"Failed to delete user ID {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        logger.info(f"User deleted successfully: {existing_user.username} (ID: {user_id})")
        
        return {
            "message": f"User {existing_user.username} deleted successfully",
            "deleted_user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User deletion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@auth_router.post("/verify-token")
async def verify_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Verify if the provided access token is valid
    """
    logger.info("Token verification request")
    
    try:
        sm: ISessionAuthenticator = request.app.state.session_manager
        user = await sm.authenticate_access_token(credentials.credentials)
        
        if not user:
            logger.warning("Token verification failed: Invalid token or session")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"Token verified successfully for user: {user.username}")
        
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "is_active": user.is_active
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
