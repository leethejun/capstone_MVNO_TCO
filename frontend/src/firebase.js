import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from 'firebase/auth';
import { firebaseConfig, firebaseConfigured } from './firebase-config';

export const auth = firebaseConfigured ? getAuth(initializeApp(firebaseConfig)) : null;
export { firebaseConfigured };
export function observeAuth(callback) {
  if (!auth) { callback(null); return () => {}; }
  return onAuthStateChanged(auth, callback);
}
export async function googleLogin() {
  if (!auth) throw new Error('Google 로그인 설정을 준비 중입니다. 잠시 후 다시 시도해주세요.');
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  await signInWithPopup(auth, provider);
}
export async function firebaseLogout() {
  if (auth) await signOut(auth);
}
export async function authHeaders() {
  if (!auth?.currentUser) throw new Error('Google 로그인이 필요합니다.');
  return { 'X-Firebase-ID-Token': await auth.currentUser.getIdToken() };
}
