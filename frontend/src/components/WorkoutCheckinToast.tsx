import React from 'react';
import { Dumbbell, X, Flame } from 'lucide-react';

export interface CheckinNotificationData {
  id: string;
  title: string;
  body: string;
  workout_id: string;
  workout_title: string;
  prompt: string;
}

interface WorkoutCheckinToastProps {
  notification: CheckinNotificationData | null;
  onOpenChat: () => void;
  onDismiss: () => void;
}

export const WorkoutCheckinToast: React.FC<WorkoutCheckinToastProps> = ({
  notification,
  onOpenChat,
  onDismiss,
}) => {
  if (!notification) return null;

  return (
    <div className="fixed top-safe-toast left-3.5 right-3.5 sm:left-auto sm:right-6 sm:w-[420px] z-50 animate-in fade-in slide-in-from-top-6 duration-300">
      <div className="bg-[#19221f]/95 backdrop-blur-xl border border-[#79c5a6]/50 shadow-2xl shadow-[#218d79]/25 rounded-3xl p-4 space-y-3 relative overflow-hidden">
        {/* Glow accent */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-[#79c5a6]/10 rounded-full blur-2xl pointer-events-none" />

        <div className="flex items-start justify-between gap-2.5 relative z-10">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-[#79c5a6]/15 border border-[#79c5a6]/30 flex items-center justify-center text-[#79c5a6] shrink-0 shadow-lg shadow-[#218d79]/10">
              <Dumbbell className="w-5 h-5 animate-pulse" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-extrabold text-[#e6eee8] tracking-tight truncate">
                  {notification.title}
                </h3>
                <span className="text-[10px] font-bold bg-[#79c5a6] text-[#10261b] px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0">
                  20 мин
                </span>
              </div>
              <p className="text-xs text-[#a4b8aa] mt-0.5 truncate">
                «{notification.workout_title}»
              </p>
            </div>
          </div>

          <button
            onClick={onDismiss}
            className="text-[#91a797] hover:text-[#e6eee8] p-2 -mr-1.5 -mt-1.5 rounded-xl hover:bg-[#33473b] active:scale-90 transition-all shrink-0"
            title="Закрыть"
            aria-label="Закрыть уведомление"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-zinc-300 leading-relaxed relative z-10">
          {notification.body}
        </p>

        <div className="flex items-center space-x-2 pt-1 relative z-10">
          <button
            onClick={onOpenChat}
            className="flex-1 bg-[#79c5a6] hover:bg-[#90d4b8] active:scale-95 text-[#10261b] font-bold text-xs px-4 py-2.5 rounded-2xl transition-all flex items-center justify-center space-x-2 shadow-lg shadow-[#218d79]/20"
          >
            <Flame className="w-4 h-4 fill-[#fffdf5]" />
            <span>Рассказать тренеру</span>
          </button>
          <button
            onClick={onDismiss}
            className="bg-[#33473b] hover:bg-[#c3d4c7] active:scale-95 text-[#a4b8aa] hover:text-[#e6eee8] font-medium text-xs px-3.5 py-2.5 rounded-2xl transition-all"
          >
            Позже
          </button>
        </div>
      </div>
    </div>
  );
};
