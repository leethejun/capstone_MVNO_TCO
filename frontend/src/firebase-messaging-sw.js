import { initializeApp } from 'firebase/app';
import { getMessaging, onBackgroundMessage } from 'firebase/messaging/sw';
import { firebaseConfig, firebaseConfigured } from './firebase-config';

// Firebase가 클릭 핸들러를 설치하기 전에 앱의 클릭 동작을 등록한다.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    const url = new URL('/#notifications', self.location.origin).href;
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) { await existing.navigate(url); return existing.focus(); }
    return self.clients.openWindow(url);
  })());
});
if (firebaseConfigured) {
  const messaging = getMessaging(initializeApp(firebaseConfig));
  onBackgroundMessage(messaging, (payload) => {
    const data = payload.data || {};
    return self.registration.showNotification(data.title || '알뜰알뜰 환승 알림', {
      body: data.body || '', icon: '/favicon.svg',
      tag: data.tag || 'alddle-transfer', data: { url: '/#notifications' },
    });
  });
}
