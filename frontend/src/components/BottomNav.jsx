import React from 'react';
import { Search, CalendarCheck, BellRing } from 'lucide-react';

export default function BottomNav({ activeTab, setActiveTab, unreadNotifCount = 0 }) {
  const tabs = [
    { id: 'rank', label: '요금제 랭킹', icon: Search },
    { id: 'subscription', label: '내 요금제', icon: CalendarCheck },
    { id: 'notification', label: '환승 알림', icon: BellRing, badge: unreadNotifCount },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 max-w-md mx-auto bg-white/95 backdrop-blur-md border-t border-slate-200 px-6 py-2 flex justify-around shadow-lg">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative flex flex-col items-center justify-center py-1 px-3 rounded-xl transition ${
              isActive ? 'text-indigo-600 font-semibold' : 'text-slate-400 hover:text-slate-600 font-medium'
            }`}
          >
            <div className="relative">
              <Icon className={`w-5 h-5 transition-transform ${isActive ? 'scale-110' : ''}`} />
              {tab.badge > 0 && (
                <span className="absolute -top-1 -right-2 bg-rose-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center shadow-xs animate-pulse">
                  {tab.badge}
                </span>
              )}
            </div>
            <span className="text-[11px] mt-1">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
