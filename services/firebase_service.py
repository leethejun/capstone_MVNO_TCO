"""Firebase Admin 초기화: 비밀키는 런타임 파일로만 읽는다."""
import os
from functools import lru_cache
from threading import Lock

_app_lock = Lock()


@lru_cache(maxsize=1)
def firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    project = os.getenv('FIREBASE_PROJECT_ID', '').strip()
    if not project:
        raise RuntimeError('FIREBASE_PROJECT_ID가 설정되지 않았습니다.')
    path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '').strip()
    credential = credentials.Certificate(path) if path else credentials.ApplicationDefault()
    with _app_lock:
        try:
            return firebase_admin.get_app('alddle')
        except ValueError:
            return firebase_admin.initialize_app(credential, {'projectId': project}, name='alddle')


def verify_google_token(token):
    from firebase_admin import auth
    claims = auth.verify_id_token(token, app=firebase_app(), check_revoked=True)
    if claims.get('firebase', {}).get('sign_in_provider') != 'google.com':
        raise ValueError('Google 로그인이 필요합니다.')
    if not claims.get('email_verified') or not claims.get('email'):
        raise ValueError('확인된 Google 이메일이 필요합니다.')
    return claims
