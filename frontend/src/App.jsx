import { useI18n } from './i18n/hooks';
import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import BottomNav from './components/BottomNav';
import UserModal from './components/UserModal';
import SubscribeModal from './components/SubscribeModal';
import RankPage from './pages/RankPage';
import SubscriptionPage from './pages/SubscriptionPage';
import NotificationPage from './pages/NotificationPage';
import { getMe } from './api';
import { observeAuth } from './firebase';
import { refreshPush } from './push';

export default function App() {
  const { t, locale } = useI18n();
  useEffect(() => { refreshPush().catch(() => {}); }, [locale]);
  const [activeTab, setActiveTab] = useState(window.location.hash === '#notifications' ? 'notification' : 'rank'); // 'rank' | 'subscription' | 'notification'
  const [currentUser, setCurrentUser] = useState(null);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [selectedPlanForSubscribe, setSelectedPlanForSubscribe] = useState(null);

  const [authError, setAuthError] = useState('');
  useEffect(() => {
    let generation = 0;
    const stop = observeAuth(async (firebaseUser) => {
      const current = ++generation;
      setCurrentUser(null);
      setAuthError('');
      localStorage.removeItem('mvno_user_id');
      if (!firebaseUser) return;
      try {
        const user = await getMe();
        if (current !== generation) return;
        setCurrentUser(user);
        await refreshPush().catch(() => {});
      } catch (err) {
        if (current === generation) setAuthError(err.message);
      }
    });
    return () => { generation++; stop(); };
  }, []);
  const handleSelectUser = (user) => setCurrentUser(user);

  const handleSubscribeSuccess = () => {
    // 개통 등록 성공 시 내 요금제 탭으로 이동
    setActiveTab('subscription');
  };

  return (
    <div className="min-h-screen bg-slate-200 flex justify-center items-start">
      {/* 모바일 폰 뷰포트 컨테이너 (max-w-md, 모바일 앱 형태) */}
      <div className="w-full max-w-md min-h-screen bg-slate-50 shadow-2xl relative flex flex-col border-x border-slate-200/80">
        {/* 상단 앱 바 */}
        <Header user={currentUser} onOpenUserModal={() => setIsUserModalOpen(true)} />

        {authError && <p role="alert" className="px-4 py-2 text-xs text-rose-600">{t(authError)}</p>}
        {/* 메인 화면 영역 */}
        <main className="flex-1 overflow-y-auto">
          {activeTab === 'rank' && (
            <RankPage
              onSelectPlanForSubscribe={(plan) => setSelectedPlanForSubscribe(plan)}
            />
          )}

          {activeTab === 'subscription' && (
            <SubscriptionPage
              currentUser={currentUser}
              onNavigateToRank={() => setActiveTab('rank')}
              onOpenUserModal={() => setIsUserModalOpen(true)}
            />
          )}

          {activeTab === 'notification' && (
            <NotificationPage
              currentUser={currentUser}
              onOpenUserModal={() => setIsUserModalOpen(true)}
            />
          )}
        </main>

        {/* 하단 탭 바 */}
        <BottomNav activeTab={activeTab} setActiveTab={setActiveTab} />

        {/* 유저 로그인/변경 모달 */}
        <UserModal
          isOpen={isUserModalOpen}
          onClose={() => setIsUserModalOpen(false)}
          currentUser={currentUser}
          onSelectUser={handleSelectUser}
        />

        {/* 요금제 개통 등록 모달 */}
        <SubscribeModal
          isOpen={!!selectedPlanForSubscribe}
          onClose={() => setSelectedPlanForSubscribe(null)}
          plan={selectedPlanForSubscribe}
          currentUser={currentUser}
          onSuccess={handleSubscribeSuccess}
        />
      </div>
    </div>
  );
}
