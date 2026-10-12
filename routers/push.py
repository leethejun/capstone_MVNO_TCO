from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, PushDevice
from schemas import PushDeviceInput, PushDeviceDelete
from services.auth import get_current_user
from services.push import register_device, unregister_device
from services.firebase_service import firebase_app

router = APIRouter(prefix='/api/push', tags=['Push'])


@router.post('/devices')
def register(data: PushDeviceInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return register_device(data, user, db)


@router.delete('/devices')
def unregister(data: PushDeviceDelete, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return unregister_device(data.installation_id, user, db)


@router.post('/test')
def test_push(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from firebase_admin import messaging
    devices = db.query(PushDevice).filter(PushDevice.user_id == user.user_id, PushDevice.is_active == True).all()
    if not devices:
        raise HTTPException(status_code=400, detail='먼저 푸시 알림을 켜주세요.')
    sent = 0
    for device in devices:
        try:
            messaging.send(messaging.Message(token=device.token, data={
                'title': 'Alddle test notification' if device.language == 'en' else '알뜰알뜰 테스트 알림',
                'body': 'You are ready to receive switching reminders.' if device.language == 'en' else '환승 알림을 받을 준비가 완료되었습니다.',
                'tag': 'alddle-test', 'url': '/'
            }), app=firebase_app())
            sent += 1
        except messaging.UnregisteredError:
            device.is_active = False
        except Exception:
            continue
    db.commit()
    if not sent:
        raise HTTPException(status_code=502, detail='푸시 전송에 실패했습니다. 기기 연결과 서버 Firebase 설정을 확인해주세요.')
    return {'sent': sent, 'failed': len(devices) - sent}
