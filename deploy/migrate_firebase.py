"""기존 사용자/구독을 보존하며 Google UID와 FCM 기기·발송 이력 스키마를 추가."""
from sqlalchemy import inspect, text
from database import engine
from models import Base, PushDevice, PushDelivery


def migrate():
    if engine.dialect.name == 'mysql':
        with engine.begin() as connection:
            connection.execute(text('SET SESSION lock_wait_timeout = 10'))
            users = {column['name'] for column in inspect(connection).get_columns('users')}
            notifications = {column['name'] for column in inspect(connection).get_columns('notifications')}
            if 'firebase_uid' not in users:
                connection.execute(text('ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(128) NULL, '
                                        'ADD UNIQUE KEY uq_users_firebase_uid (firebase_uid)'))
            if 'push_status' not in notifications:
                connection.execute(text("ALTER TABLE notifications ADD COLUMN push_status VARCHAR(20) NOT NULL DEFAULT 'NOT_SENT'"))
            if 'push_attempts' not in notifications:
                connection.execute(text('ALTER TABLE notifications ADD COLUMN push_attempts INT NOT NULL DEFAULT 0'))
    Base.metadata.create_all(engine, tables=[PushDevice.__table__, PushDelivery.__table__])
    if engine.dialect.name == 'mysql':
        with engine.begin() as connection:
            connection.execute(text('SET SESSION lock_wait_timeout = 10'))
            columns = {column['name'] for column in inspect(connection).get_columns('push_devices')}
            if 'language' not in columns:
                connection.execute(text("ALTER TABLE push_devices ADD COLUMN language VARCHAR(2) NOT NULL DEFAULT 'ko'"))
    print('Firebase UID / push device / delivery migration complete')


if __name__ == '__main__':
    migrate()
