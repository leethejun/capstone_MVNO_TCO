import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import PushDevice, PushDelivery
from services.firebase_service import firebase_app


def register_device(data, user, db):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    device = db.query(PushDevice).filter(PushDevice.installation_id == data.installation_id).first()
    token_device = db.query(PushDevice).filter(PushDevice.token_hash == token_hash).first()
    if (device and device.user_id != user.user_id) or (token_device and token_device.user_id != user.user_id):
        raise HTTPException(status_code=409, detail='기기가 다른 계정에 연결되어 있습니다. 이전 계정에서 로그아웃해주세요.')
    if token_device and token_device != device:
        device = token_device
        device.installation_id = data.installation_id
    if not device:
        device = PushDevice(user_id=user.user_id, installation_id=data.installation_id)
        db.add(device)
    device.token = data.token
    device.token_hash = token_hash
    device.is_active = True
    device.updated_at = datetime.now()
    db.commit()
    return {'registered': True}


def unregister_device(installation_id, user, db):
    # 알림 토큰 자체를 API 응답에 노출하지 않는다.
    device = db.query(PushDevice).filter(PushDevice.installation_id == installation_id,
                                       PushDevice.user_id == user.user_id).first()
    if device:
        # 성공 발송 이력은 DB cascade를 통해 정리한다.
        db.delete(device)
        db.commit()
    return {'removed': True}


def send_to_devices(notification, user, title, body, db: Session):
    from firebase_admin import messaging
    devices = db.query(PushDevice).filter(PushDevice.user_id == user.user_id, PushDevice.is_active == True).all()
    result = {'sent': 0, 'failed': 0, 'invalid': 0, 'devices': len(devices)}
    for device in devices:
        delivery = db.query(PushDelivery).filter(PushDelivery.notification_id == notification.notification_id,
                                                PushDelivery.device_id == device.device_id).first()
        if delivery and delivery.delivered_at:
            result['sent'] += 1
            continue
        try:
            # data-only 메시지는 서비스 워커가 한 번만 표시하도록 한다.
            messaging.send(messaging.Message(token=device.token, data={
                'title': title, 'body': body, 'notification_id': str(notification.notification_id),
                'url': '/', 'tag': f'notification-{notification.notification_id}'
            }, webpush=messaging.WebpushConfig(headers={'TTL': '86400', 'Urgency': 'normal'})), app=firebase_app())
        except messaging.UnregisteredError:
            device.is_active = False
            result['invalid'] += 1
            continue
        except Exception:
            # 인증/설정/일시적 장애를 성공으로 기록하거나 토큰을 삭제하지 않는다.
            result['failed'] += 1
            continue
        if delivery is None:
            delivery = PushDelivery(notification_id=notification.notification_id, device_id=device.device_id)
            db.add(delivery)
        delivery.delivered_at = datetime.now()
        result['sent'] += 1
    db.flush()
    return result
