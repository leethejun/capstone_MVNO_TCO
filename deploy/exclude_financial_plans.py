"""기존 은행 금융 결합 요금제를 추천에서 제외하고 구독 이력을 보존한다."""
from database import SessionLocal
from models import Plan,Telecom
from services.crawler.bank_eligibility import requires_financial_product


def exclude():
    db=SessionLocal()
    try:
        records=db.query(Plan,Telecom.name).join(Telecom).filter(Plan.is_active==True).all()
        ids=[]
        for plan,name in records:
            if requires_financial_product(dict(telecom_name=name,title=plan.title,raw_text=plan.raw_text or '')):
                plan.is_active=False;ids.append(plan.plan_id)
        db.commit();print({'excluded_financial_plans':len(ids)})
    except Exception:
        db.rollback();raise
    finally:db.close()


if __name__=='__main__':exclude()
