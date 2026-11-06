from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.core.encryption import encrypt_json
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):

    user = db.query(User).filter(
        User.username == request.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    roles = [
        user_role.role.role_name
        for user_role in user.user_roles
    ]

    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        roles=roles,
    )

    return LoginResponse(
        access_token=token,
    )


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    roles = [
        user_role.role.role_name
        for user_role in current_user.user_roles
    ]

    user_data = {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "roles": roles,
    }

    encrypted_data = encrypt_json(user_data)

    return {
        "encrypted": True,
        "data": encrypted_data,
    }