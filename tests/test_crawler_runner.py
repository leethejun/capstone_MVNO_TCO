import unittest
from threading import Event
from unittest.mock import patch, Mock
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from services.crawler import runner
from services.scheduler.manager import scheduler, start_scheduler, shutdown_scheduler
from services.auth import require_admin


class RunnerTests(unittest.TestCase):
    def test_background_duplicate_and_failure(self):
        entered, finish = Event(), Event()
        db = Mock()
        def pipeline(**kwargs):
            entered.set()
            finish.wait(5)
            raise ValueError('test failure')
        with patch.object(runner, 'SessionLocal', return_value=db), patch.object(runner, 'run_comprehensive_crawler_pipeline', side_effect=pipeline):
            accepted, state = runner.start_refresh()
            self.assertTrue(accepted)
            self.assertEqual(state['status'], 'running')
            self.assertTrue(entered.wait(2))
            self.assertFalse(runner.start_refresh(source='scheduled')[0])
            finish.set()
            runner._executor.submit(lambda: None).result(timeout=5)
        self.assertEqual(runner.get_run_state()['status'], 'failed')
        self.assertEqual(runner.get_run_state()['result']['error'], 'test failure')
        db.close.assert_called_once()

    def test_admin_allowlist(self):
        with patch.dict('os.environ', {'FIREBASE_ADMIN_UIDS': 'allowed'}):
            self.assertEqual(require_admin(Mock(firebase_uid='allowed')).firebase_uid, 'allowed')
            with self.assertRaises(HTTPException) as denied:
                require_admin(Mock(firebase_uid='other'))
            self.assertEqual(denied.exception.status_code, 403)

    def test_monthly_schedule_keeps_daily_notifications(self):
        start_scheduler()
        try:
            now = datetime(2026, 10, 11, tzinfo=ZoneInfo('Asia/Seoul'))
            crawler = scheduler.get_job('monthly_mvno_crawler')
            next_run = crawler.trigger.get_next_fire_time(None, now)
            self.assertEqual((next_run.month, next_run.day, next_run.hour), (11, 1, 2))
            reminder = scheduler.get_job('midnight_lifecycle_notifications').trigger.get_next_fire_time(None, now)
            self.assertEqual((reminder.month, reminder.day, reminder.hour), (10, 11, 0))
        finally:
            shutdown_scheduler()
