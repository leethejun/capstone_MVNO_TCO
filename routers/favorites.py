from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import FavoritePlan, Plan, User
from schemas import FavoriteCreate, FavoriteItem, FavoriteResolveRequest
from services.auth import get_current_user
from services.favorites import favorite_key, resolve_favorites

router = APIRouter(prefix="/api/favorites", tags=["Favorites"])


@router.post("/resolve", response_model=List[FavoriteItem], summary="비로그인 즐겨찾기를 현재 상품·TCO로 조회")
def resolve_guest_favorites(body: FavoriteResolveRequest, db: Session = Depends(get_db)):
    return resolve_favorites(db, body.items, body.target_months)


@router.get("", response_model=List[FavoriteItem], summary="내 즐겨찾기 요금제 조회")
def list_favorites(target_months: int = Query(12, ge=1, le=48), db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    rows = db.query(FavoritePlan).filter(FavoritePlan.user_id == user.user_id)\
        .order_by(FavoritePlan.created_at.desc(), FavoritePlan.favorite_id.desc()).all()
    return resolve_favorites(db, rows, target_months)


@router.post("", response_model=FavoriteItem, summary="요금제 즐겨찾기 추가 (이미 있으면 기존 항목 반환)")
def add_favorite(body: FavoriteCreate, target_months: int = Query(12, ge=1, le=48),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(Plan).options(joinedload(Plan.telecom)).filter(Plan.plan_id == body.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="해당 요금제를 찾을 수 없습니다.")
    key = favorite_key(plan)
    favorite = db.query(FavoritePlan).filter_by(user_id=user.user_id, **key).first()
    if favorite is None:
        favorite = FavoritePlan(user_id=user.user_id, plan_id=plan.plan_id, **key)
        db.add(favorite)
    else:
        favorite.plan_id = plan.plan_id
    try:
        db.commit()
    except IntegrityError:
        # 같은 요청이 동시에 들어온 경우 먼저 저장된 항목을 사용한다.
        db.rollback()
        favorite = db.query(FavoritePlan).filter_by(user_id=user.user_id, **key).first()
    db.refresh(favorite)
    return resolve_favorites(db, [favorite], target_months)[0]


@router.delete("/{favorite_id}", status_code=204, summary="즐겨찾기 삭제")
def delete_favorite(favorite_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    favorite = db.query(FavoritePlan).filter(FavoritePlan.favorite_id == favorite_id,
                                             FavoritePlan.user_id == user.user_id).first()
    if not favorite:
        raise HTTPException(status_code=404, detail="즐겨찾기를 찾을 수 없습니다.")
    db.delete(favorite)
    db.commit()
    return Response(status_code=204)
