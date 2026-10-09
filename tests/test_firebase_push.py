import unittest
from datetime import date, datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from models import Base, User, Telecom, Plan, UserSubscription, Notification, NoticeType, PushDevice, PushDelivery
from schemas import PushDeviceInput
from services.auth import get_current_user, resolve_google_user, require_admin
from services.push import register_device, unregister_device, send_to_devices


class FirebasePushTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(email='one@gmail.com', firebase_uid='uid-one')
        self.other = User(email='two@gmail.com', firebase_uid='uid-two')
        telecom = Telecom(name='test')
        self.db.add_all([self.user, self.other, telecom]); self.db.flush()
        plan = Plan(telecom_id=telecom.telecom_id, title='test', base_data_gb=1, discount_price=1000,
                    normal_price=2000, discount_months=6, scraped_at=datetime.now())
        self.db.add(plan); self.db.flush()
        sub = UserSubscription(user_id=self.user.user_id, plan_id=plan.plan_id, start_date=date.today(),
                               target_months=12, discount_end_date=date.today())
        self.db.add(sub); self.db.flush()
        self.notice = Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.D_1,
                                   scheduled_date=date.today())
        self.db.add(self.notice); self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def register(self, installation='installation-one', token='token-one-' * 5):
        return register_device(PushDeviceInput(installation_id=installation, token=token), self.user, self.db)

    def test_missing_and_invalid_auth_denied(self):
        with self.assertRaises(HTTPException) as error:
            get_current_user(None, self.db)
        self.assertEqual(error.exception.status_code, 401)
        with patch('services.auth.verify_google_token', side_effect=ValueError('revoked')):
            with self.assertRaises(HTTPException) as error:
                get_current_user('invalid', self.db)
        self.assertEqual(error.exception.status_code, 401)

    def test_unverified_or_conflicting_account_denied(self):
        for claims, code in [({'uid': 'new', 'email': self.user.email, 'email_verified': False}, 401),
                             ({'uid': 'new', 'email': self.user.email, 'email_verified': True}, 409)]:
            with self.assertRaises(HTTPException) as error:
                resolve_google_user(claims, self.db)
            self.assertEqual(error.exception.status_code, code)

    def test_admin_allowlist_required(self):
        with patch.dict('os.environ', {'FIREBASE_ADMIN_UIDS': 'uid-two'}):
            with self.assertRaises(HTTPException):
                require_admin(self.user)
            self.assertEqual(require_admin(self.other), self.other)

    def test_rotation_and_foreign_device_protection(self):
        self.register(); self.register(token='rotated-token-' * 5)
        self.assertEqual(self.db.query(PushDevice).count(), 1)
        unregister_device('installation-one', self.other, self.db)
        self.assertEqual(self.db.query(PushDevice).count(), 1)
        with self.assertRaises(HTTPException) as error:
            register_device(PushDeviceInput(installation_id='installation-one', token='other-token-' * 5), self.other, self.db)
        self.assertEqual(error.exception.status_code, 409)

    def test_partial_failure_retry_does_not_duplicate_success(self):
        self.register(); self.register('installation-two', 'token-two-' * 5)
        with patch('services.push.firebase_app', return_value=object()), patch('firebase_admin.messaging.send', side_effect=['sent', RuntimeError('temporary')]) as send:
            result = send_to_devices(self.notice, self.user, 'title', 'body', self.db)
        self.assertEqual((result['sent'], result['failed']), (1, 1))
        self.db.commit()
        with patch('services.push.firebase_app', return_value=object()), patch('firebase_admin.messaging.send', return_value='sent') as send:
            result = send_to_devices(self.notice, self.user, 'title', 'body', self.db)
            self.assertEqual(send.call_count, 1)
        self.assertEqual((result['sent'], result['failed']), (2, 0))
        self.assertEqual(self.db.query(PushDelivery).count(), 2)

    def test_test_push_sends_only_to_authenticated_owner(self):
        from routers.push import test_push
        self.register()
        register_device(PushDeviceInput(installation_id='other-installation', token='other-token-' * 5), self.other, self.db)
        with patch('routers.push.firebase_app', return_value=object()), patch('firebase_admin.messaging.send', return_value='sent') as send:
            result = test_push(self.user, self.db)
        self.assertEqual(result['sent'], 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[0].token, 'token-one-' * 5)

    def test_unregistered_token_disabled(self):
        from firebase_admin.messaging import UnregisteredError
        self.register()
        with patch('services.push.firebase_app', return_value=object()), patch('firebase_admin.messaging.send', side_effect=UnregisteredError('gone')):
            result = send_to_devices(self.notice, self.user, 'title', 'body', self.db)
        self.assertEqual(result['invalid'], 1)
        self.assertFalse(self.db.query(PushDevice).one().is_active)


if __name__ == '__main__':
    unittest.main()
