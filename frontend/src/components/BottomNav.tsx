import React from 'react';
import { LayoutDashboard, Gamepad2, BookOpen, MessageSquare, Calendar, Zap, ArrowUpRight } from 'lucide-react';

export type TabType = 'dashboard' | 'media' | 'library' | 'chat' | 'weekly';

interface BottomNavProps {
  currentTab: TabType | null;
  onTabChange: (tab: TabType) => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onTabChange }) => {
  const tabs = [
    { id: 'dashboard', label: 'Обзор', icon: LayoutDashboard },
    { id: 'media', label: 'Досуг', icon: Gamepad2 },
    { id: 'library', label: 'Книги', icon: BookOpen },
    { id: 'chat', label: 'AI Тренер', icon: MessageSquare },
    { id: 'weekly', label: 'Неделя', icon: Calendar },
  ] as const;

  return (
    <nav className="pulse-nav" aria-label="Основная навигация">
      <div className="pulse-nav-brand"><Zap size={22} fill="currentColor" /><span>FitPulse</span></div>
      <span className="pulse-nav-caption">ТВОЁ ПРОСТРАНСТВО</span>
      <div className="pulse-nav-items">
        {tabs.map(tab => { const Icon = tab.icon; const active = currentTab === tab.id; return <button key={tab.id} aria-current={active ? 'page' : undefined} onClick={() => onTabChange(tab.id)} className={active ? 'is-active' : ''}><Icon size={20} strokeWidth={1.8} /><span>{tab.label}</span>{active && <ArrowUpRight className="pulse-nav-arrow" size={16} />}</button>; })}
      </div>
      <div className="pulse-nav-footer"><span className="pulse-mini-mark"><Zap size={17} /></span><strong>Хорошо быть собой.</strong><p>Дай себе время расти.</p><small>FITPULSE / PERSONAL SPACE</small></div>
    </nav>
  );
};
