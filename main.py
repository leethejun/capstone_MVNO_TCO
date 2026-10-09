from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

import models
from database import engine, get_db
from routers import plans, users, subscriptions, crawler, notifications
from services.scheduler.manager import start_scheduler, shutdown_scheduler

# 서버 스타트업 시 ORM에 정의된 테이블 자동 생성 (없을 경우에만 생성)
models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 기동 시 정기 스케줄러(새벽 2시 크롤링 / 자정 환승 알림) 자동 가동
    start_scheduler()
    yield
    # 서버 종료 시 스케줄러 안전 종료
    try:
        print("\n[main.py] Lifespan shutdown: 스케줄러 종료...")
        shutdown_scheduler()
    except Exception as e:
        print(f"[main.py] Lifespan shutdown 오류 (비중요): {e}")

app = FastAPI(
    title="알뜰폰 TCO 최적화 API",
    description="비정형 요금제 데이터 정형화 및 생애주기 TCO 최적화 백엔드",
    version="1.0.0",
    lifespan=lifespan
)

# Flutter / React Native 및 프론트엔드 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(plans.router)
app.include_router(users.router)
app.include_router(subscriptions.router)
app.include_router(crawler.router)
app.include_router(notifications.router)

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "service": "알뜰폰 TCO 최적화 API",
        "docs_url": "/docs"
    }

# DB 연동 테스트용 헬스체크 API
@app.get("/health/db")
def check_db_connection(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).fetchone()
        return {
            "status": "success",
            "db_connected": True,
            "query_result": result[0]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 연결 실패: {str(e)}"
        )
