from typing import List, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from services.scheduler.tasks import job_crawl_mvno_plans, job_send_lifecycle_notifications

scheduler = BackgroundScheduler(timezone="Asia/Seoul")

def start_scheduler():
    """APScheduler 백그라운드 스케줄러 초기화 및 정기 작업 등록"""
    if not scheduler.running:
        # 1. 매일 새벽 02:00 정기 크롤링 작업
        scheduler.add_job(
            job_crawl_mvno_plans,
            trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Seoul"),
            id="daily_mvno_crawler",
            name="매일 새벽 02:00 알뜰폰 요금제 전수 자동 크롤링",
            replace_existing=True
        )

        # 2. 매일 자정 00:00 프로모션 환승 알림 배치 작업
        scheduler.add_job(
            job_send_lifecycle_notifications,
            trigger=CronTrigger(hour=0, minute=0, timezone="Asia/Seoul"),
            id="midnight_lifecycle_notifications",
            name="매일 자정 00:00 프로모션 만료 D-14/7/3 환승 알림 배치",
            replace_existing=True
        )

        scheduler.start()
        print("✅ [APScheduler] 백그라운드 정기 스케줄러 가동 완료 (새벽 2시 크롤링 / 자정 환승 알림)")

def shutdown_scheduler():
    """스케줄러 정상 종료"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("🛑 [APScheduler] 스케줄러 종료 완료")

def get_scheduler_jobs() -> List[Dict[str, Any]]:
    """현재 등록된 스케줄러 작업 목록 및 다음 실행 시간 조회"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
        })
    return jobs
