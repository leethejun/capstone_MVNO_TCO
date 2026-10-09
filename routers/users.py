from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserResponse

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.post("", response_model=UserResponse, summary="이메일로 기존 사용자 연결 또는 신규 등록")
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    email = user_in.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="올바른 이메일 주소를 입력해주세요.")
    existing = db.query(User).filter(func.lower(User.email) == email).first()
    if existing:
        return existing

    user = User(
        email=email,
        fcm_token=user_in.fcm_token,
        default_target_months=user_in.default_target_months
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            return existing
        raise
    db.refresh(user)
    return user

@router.get("/{user_id}", response_model=UserResponse, summary="사용자 상세 조회")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user
