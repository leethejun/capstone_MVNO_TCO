import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import BottomNav from './components/BottomNav';
import UserModal from './components/UserModal';
import SubscribeModal from './components/SubscribeModal';
import RankPage from './pages/RankPage';
import SubscriptionPage from './pages/SubscriptionPage';
import NotificationPage from './pages/NotificationPage';
import { getUser } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('rank'); // 'rank' | 'subscription' | 'notification'
  const [currentUser, setCurrentUser] = useState(null);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [selectedPlanForSubscribe, setSelectedPlanForSubscribe] = useState(null);

  // 로컬스토리지에서 기존 user_id 복원, 없으면 기본 1번 유저 시도
  useEffect(() => {
    const savedUserId = localStorage.getItem('mvno_user_id');
    const initUser = async () => {
      try {
        const idToLoad = savedUserId ? Number(savedUserId) : 1;
        const user = await getUser(idToLoad);
        setCurrentUser(user);
        localStorage.setItem('mvno_user_id', user.user_id);
      } catch (err) {
        console.log('초기 사용자 로드 실패, 신규 로그인 필요', err);
      }
    };
    initUser();
  }, []);

  const handleSelectUser = (user) => {
    setCurrentUser(user);
    if (user && user.user_id) {
      localStorage.setItem('mvno_user_id', user.user_id);
    }
  };

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
