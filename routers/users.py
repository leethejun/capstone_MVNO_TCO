from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserResponse, UserPreferences
from services.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_preferences(preferences: UserPreferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if preferences.default_target_months not in (6, 12, 24, 36, 48):
        raise HTTPException(status_code=422, detail="지원하지 않는 유지기간입니다.")
    user.default_target_months = preferences.default_target_months
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, user: User = Depends(get_current_user)):
    if user_id != user.user_id:
        raise HTTPException(status_code=403, detail="본인 계정만 조회할 수 있습니다.")
    return user
