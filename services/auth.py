import os
from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_db
from models import User
from services.firebase_service import verify_google_token


def resolve_google_user(claims, db):
    uid = claims.get('uid') or claims.get('sub')
    email = str(claims.get('email', '')).strip().lower()
    if not uid or not email or not claims.get('email_verified'):
        raise HTTPException(status_code=401, detail='확인된 Google 계정이 필요합니다.')
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if user:
        return user
    # 기존 이메일 계정의 구독은 검증된 Google 이메일에만 연결한다.
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user and user.firebase_uid and user.firebase_uid != uid:
        raise HTTPException(status_code=409, detail='다른 인증 계정에 이미 연결된 이메일입니다.')
    if user is None:
        user = User(email=email, firebase_uid=uid, default_target_months=12)
        db.add(user)
    else:
        user.firebase_uid = uid
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.query(User).filter(User.firebase_uid == uid).first()
        if user is None:
            raise HTTPException(status_code=409, detail='계정 연결 충돌입니다. 다시 로그인해주세요.')
    db.refresh(user)
    return user


def get_current_user(x_firebase_id_token: str = Header(None), db: Session = Depends(get_db)):
    # nginx 사이트 Basic 인증과 충돌하지 않도록 별도 헤더를 사용한다.
    if not x_firebase_id_token:
        raise HTTPException(status_code=401, detail='Google 로그인이 필요합니다.')
    try:
        claims = verify_google_token(x_firebase_id_token)
    except RuntimeError:
        raise HTTPException(status_code=503, detail='서버 Firebase 설정이 완료되지 않았습니다.')
    except Exception:
        raise HTTPException(status_code=401, detail='로그인이 만료되었거나 인증 정보가 올바르지 않습니다.')
    return resolve_google_user(claims, db)


def require_admin(user: User = Depends(get_current_user)):
    admin_uids = {value.strip() for value in os.getenv('FIREBASE_ADMIN_UIDS', '').split(',') if value.strip()}
    if user.firebase_uid not in admin_uids:
        raise HTTPException(status_code=403, detail='관리자 권한이 필요합니다.')
    return user
