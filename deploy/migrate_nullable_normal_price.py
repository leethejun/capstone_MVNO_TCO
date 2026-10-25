"""정상가 미공개는 NULL. python -m deploy.migrate_nullable_normal_price --apply"""
import argparse
from sqlalchemy import inspect,text
from database import engine


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    with engine.begin() as conn:
        column=next(c for c in inspect(conn).get_columns('plans') if c['name']=='normal_price')
        if column['nullable']:print('normal_price already nullable');return
        if not args.apply:print('미리보기: plans.normal_price INT NULL (--apply로 적용)');return
        if conn.dialect.name!='mysql':raise ValueError('이 마이그레이션은 운영 MySQL 전용')
        conn.execute(text('ALTER TABLE plans MODIFY COLUMN normal_price INT NULL'))
        print('normal_price nullable migration complete')


if __name__=='__main__':main()
