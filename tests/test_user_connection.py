import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User
from schemas import UserCreate
from routers.users import create_user


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
        user = create_user(UserCreate(email='member@example.com', default_target_months=6), self.db)
        self.assertEqual(user.user_id, 2)
        self.assertEqual(user.default_target_months, 24)
        self.assertEqual(self.db.query(User).count(), 2)

    def test_email_case_and_surrounding_spaces(self):
        user = create_user(UserCreate(email='  MEMBER@EXAMPLE.COM  '), self.db)
        self.assertEqual(user.user_id, 2)

    def test_new_email_created_once_then_reused(self):
        first = create_user(UserCreate(email='new@example.com', default_target_months=36), self.db)
        second = create_user(UserCreate(email='new@example.com'), self.db)
        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(second.default_target_months, 36)
        self.assertEqual(self.db.query(User).count(), 3)


if __name__ == '__main__':
    unittest.main()
