import { getMessaging, getToken, deleteToken, isSupported, onMessage } from 'firebase/messaging';
import { getApp } from 'firebase/app';
import { auth, authHeaders } from './firebase';

const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const deviceKey = 'alddle_push_installation';
const disabledKey = 'alddle_push_disabled';
function installationId() {
  let id = localStorage.getItem(deviceKey);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(deviceKey, id); }
  return id;
}
async function messagingInstance() {
  if (!auth || !await isSupported()) throw new Error('이 브라우저는 푸시 알림을 지원하지 않습니다. 아이폰은 홈 화면에 앱을 추가한 뒤 이용해주세요.');
  return getMessaging(getApp());
}
async function registerToken(requestPermission) {
  if (!auth?.currentUser) throw new Error('Google 로그인 후 알림을 켜주세요.');
  if (!('Notification' in window)) throw new Error('이 브라우저는 알림을 지원하지 않습니다.');
  const permission = requestPermission ? await Notification.requestPermission() : Notification.permission;
  if (permission !== 'granted') throw new Error('브라우저 알림 권한을 허용해주세요.');
  const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;
  if (!vapidKey) throw new Error('푸시 알림 설정을 준비 중입니다.');
  const messaging = await messagingInstance();
  const script = import.meta.env.DEV ? '/src/firebase-messaging-sw.js' : '/firebase-messaging-sw.js';
  const registration = await navigator.serviceWorker.register(script, { type: 'module', scope: '/' });
  await navigator.serviceWorker.ready;
  const token = await getToken(messaging, { vapidKey, serviceWorkerRegistration: registration });
  if (!token) throw new Error('기기 등록에 실패했습니다. 다시 시도해주세요.');
  const response = await fetch(`${base}/push/devices`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...await authHeaders() },
    body: JSON.stringify({ installation_id: installationId(), token }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || '알림 기기 등록 실패');
  }
  return true;
}
export async function enablePush() {
  const enabled = await registerToken(true);
  localStorage.removeItem(disabledKey);
  return enabled;
}
export async function refreshPush() {
  if (!localStorage.getItem(disabledKey) && 'Notification' in window && Notification.permission === 'granted' && import.meta.env.VITE_FIREBASE_VAPID_KEY) {
    return registerToken(false);
  }
  return false;
}
export async function disablePush() {
  const id = localStorage.getItem(deviceKey);
  if (id && auth?.currentUser) {
    const response = await fetch(`${base}/push/devices`, { method: 'DELETE',
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify({ installation_id: id }),
    });
    if (!response.ok) throw new Error('알림 기기 연결을 해제하지 못했습니다. 다시 시도해주세요.');
  }
  localStorage.setItem(disabledKey, '1');
  if (auth && await isSupported()) await deleteToken(getMessaging(getApp()));
}

export async function watchForegroundPush(callback) {
  if (!auth || !await isSupported()) return () => {};
  return onMessage(getMessaging(getApp()), async (payload) => {
    const data = payload.data || {};
    const registration = await navigator.serviceWorker.getRegistration('/');
    if (registration && Notification.permission === 'granted') {
      await registration.showNotification(data.title || '알뜰알뜰 환승 알림', {
        body: data.body || '', tag: data.tag || 'alddle-transfer', icon: '/favicon.svg',
        data: { url: '/#notifications' },
      });
    }
    callback?.();
  });
}

export async function sendTestPush() {
  const response = await fetch(`${base}/push/test`, { method: 'POST', headers: await authHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.detail || '테스트 알림 전송 실패');
  return result;
}
