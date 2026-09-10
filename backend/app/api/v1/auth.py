from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.auth import UserLogin, Token, UserOut
from app.schemas.common import StandardResponse
from app.models.auth import User, Role

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=StandardResponse[Token])
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    # Placeholder for JWT generation (detailed in Week 12)
    return StandardResponse(
        success=True,
        message="Login successful",
        data=Token(
            access_token="mock-jwt-token-for-initial-setup",
            token_type="bearer",
            expires_in=900
        )
    )
