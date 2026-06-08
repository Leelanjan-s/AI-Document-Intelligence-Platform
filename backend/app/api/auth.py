from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.models import User, AuditLog
from app.schemas.schemas import UserLogin, Token, TokenRefreshRequest, UserOut
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, blacklist_token
from app.api.deps import get_current_user
import uuid

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login(
    response: Response,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and issue JWT Access and Refresh tokens."""
    stmt = select(User).where(User.email == login_data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )

    # Token payload
    user_data = {"sub": user.email, "role": user.role, "org_id": str(user.organization_id) if user.organization_id else None}
    
    access_token = create_access_token(data=user_data)
    refresh_token = create_refresh_token(data=user_data)

    # Set refresh token in HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in HTTPS/Production
        samesite="lax",
        max_age=7 * 24 * 3600  # 7 days
    )

    # Audit login action
    audit = AuditLog(
        organization_id=user.organization_id,
        user_id=user.id,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        action_metadata={"email": user.email}
    )
    db.add(audit)
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user)
    )

@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    refresh_body: Optional[TokenRefreshRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """Obtain a new JWT access token using the Refresh Token from request body or HttpOnly cookies."""
    refresh_token = None
    
    # 1. Try checking cookies
    if "refresh_token" in request.cookies:
        refresh_token = request.cookies.get("refresh_token")
        
    # 2. Try checking body
    if not refresh_token and refresh_body:
        refresh_token = refresh_body.refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    try:
        payload = decode_token(refresh_token)
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if not email or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
            
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is deactivated")

    # Generate new tokens
    user_data = {"sub": user.email, "role": user.role, "org_id": str(user.organization_id) if user.organization_id else None}
    new_access_token = create_access_token(data=user_data)
    new_refresh_token = create_refresh_token(data=user_data)

    # Set new refresh token in cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600
    )

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user=UserOut.model_validate(user)
    )

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Log out and revoke the active authentication session."""
    # Read access token from header to blacklist it
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        # Blacklist token for access duration (30 mins)
        blacklist_token(token, 30 * 60)

    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
