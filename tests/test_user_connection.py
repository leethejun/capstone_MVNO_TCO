import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User
from services.auth import resolve_google_user


class UserConnectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        User.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([User(email='test@example.com', default_target_months=12),
                         User(email='member@example.com', default_target_months=24)])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_existing_email_returns_matching_account_not_demo(self):
        user = resolve_google_user({'uid': 'google-member', 'email': 'member@example.com', 'email_verified': True}, self.db)
        self.assertEqual(user.user_id, 2)
        self.assertEqual(user.default_target_months, 24)
        self.assertEqual(self.db.query(User).count(), 2)

    def test_email_case_and_surrounding_spaces(self):
        user = resolve_google_user({'uid': 'google-member', 'email': '  MEMBER@EXAMPLE.COM  ', 'email_verified': True}, self.db)
        self.assertEqual(user.user_id, 2)

    def test_new_email_created_once_then_reused(self):
        first = resolve_google_user({'uid': 'new-uid', 'email': 'new@example.com', 'email_verified': True}, self.db)
        second = resolve_google_user({'uid': 'new-uid', 'email': 'new@example.com', 'email_verified': True}, self.db)
        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(second.default_target_months, 12)
        self.assertEqual(self.db.query(User).count(), 3)


if __name__ == '__main__':
    unittest.main()
