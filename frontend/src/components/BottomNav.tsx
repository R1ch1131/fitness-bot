import React from 'react';
import { LayoutDashboard, Dumbbell, BookOpen, MessageSquare, Calendar } from 'lucide-react';

export type TabType = 'dashboard' | 'workouts' | 'library' | 'chat' | 'weekly';

interface BottomNavProps {
  currentTab: TabType | null;
  onTabChange: (tab: TabType) => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onTabChange }) => {
  const tabs = [
    { id: 'dashboard', label: 'Обзор', icon: LayoutDashboard },
    { id: 'workouts', label: 'Зал', icon: Dumbbell },
    { id: 'library', label: 'Книги', icon: BookOpen },
    { id: 'chat', label: 'AI Тренер', icon: MessageSquare },
    { id: 'weekly', label: 'Неделя', icon: Calendar },
  ] as const;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-zinc-950/90 backdrop-blur-xl border-t border-zinc-800/80 pb-safe">
      <div className="flex items-center justify-around px-2 pt-2 pb-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onTabChange(tab.id)}
              className={`flex flex-col items-center justify-center w-16 py-1 transition-all duration-200 active:scale-95 ${
                isActive ? 'text-emerald-400 font-semibold' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <div className="relative">
                <Icon className={`w-5 h-5 transition-transform duration-200 ${isActive ? 'scale-110' : ''}`} />
                {isActive && (
                  <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 bg-emerald-400 rounded-full" />
                )}
              </div>
              <span className="text-[10px] mt-1 tracking-tight">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
