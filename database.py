import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 환경변수 DATABASE_URL 로드
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://alddle_user@localhost:3306/alddle_db?charset=utf8mb4"
)

# SQLAlchemy 엔진 생성
# pool_pre_ping=True: 오랜 시간 커넥션이 없어도 연결 끊김 오류를 자동 방지
engine = create_engine(
    DATABASE_URL,
    pool_recycle=3600,
    pool_pre_ping=True
)

# DB 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 모델들이 상속받을 Base 클래스
Base = declarative_base()

# FastAPI Dependency Injection용 DB 세션 생성기
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
