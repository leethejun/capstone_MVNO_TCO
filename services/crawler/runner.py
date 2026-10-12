"""Shared background runner for scheduled and administrator refreshes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
from database import SessionLocal
from services.crawler.pipeline import run_comprehensive_crawler_pipeline

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='crawler')
_lock = Lock()
_state = {'status': 'idle', 'started_at': None, 'finished_at': None, 'source': None, 'result': None}


def get_run_state():
    with _lock:
        return deepcopy(_state)


def _now():
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat()


def _run(max_pages, include_direct):
    db = None
    try:
        db = SessionLocal()
        result = run_comprehensive_crawler_pipeline(max_pages=max_pages, include_direct=include_direct, db=db)
    except Exception as exc:
        result = {'success': False, 'error': str(exc)}
    finally:
        if db is not None:
            db.close()
    with _lock:
        _state.update(status='completed' if result.get('success') else 'failed', finished_at=_now(), result=result)


def start_refresh(source='manual', max_pages=0, include_direct=True):
    # The deployed server uses one uvicorn worker; both entry points share this lock.
    with _lock:
        if _state['status'] == 'running':
            return False, deepcopy(_state)
        _state.update(status='running', started_at=_now(), finished_at=None, source=source, result=None)
        try:
            _executor.submit(_run, max_pages, include_direct)
        except Exception:
            _state.update(status='failed', finished_at=_now())
            raise
        return True, deepcopy(_state)
