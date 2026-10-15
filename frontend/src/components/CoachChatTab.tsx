import React, { useState, useRef, useEffect } from 'react';
import { Send, Zap, User } from 'lucide-react';
import type { ChatMessage } from '../types';

interface CoachChatTabProps {
  onSendMessage: (msg: string) => Promise<string>;
  initialPrompt?: string | null;
  onClearInitialPrompt?: () => void;
}

export const CoachChatTab: React.FC<CoachChatTabProps> = ({
  onSendMessage,
  initialPrompt,
  onClearInitialPrompt,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      sender: 'coach',
      text: 'Привет, бро! 💪 Я твой персональный AI-тренер и нутрициолог. Вижу все твои подходы в Hevy и каждый грамм в YAZIO. Спрашивай что угодно: разбор рациона, технику упражнений, восстановление или рецепты!',
      timestamp: 'Сейчас',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickPrompts = [
    '🍳 Что съесть на ужин (400 ккал)?',
    '🥗 Разбери рацион за сегодня',
    '💻 План на 30 мин кодинга по Python',
    '📚 Какую книгу почитать по саморазвитию?',
    '🏋️ Какая тренировка следующая?',
    '🔥 Мои стрики привычек',
    '💧 Креатин и задержка воды',
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (initialPrompt && initialPrompt.trim()) {
      handleSend(initialPrompt.trim());
      onClearInitialPrompt?.();
    }
  }, [initialPrompt]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const reply = await onSendMessage(text);
      const coachMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'coach',
        text: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, coachMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'coach',
        text: 'Ошибка связи с тренером. Проверь подключение к интернету или попробуй снова.',
        timestamp: 'Ошибка',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 w-full max-w-4xl mx-auto px-3 pb-[calc(4.75rem+env(safe-area-inset-bottom,0px))]">
      {/* Messages Scroll Area */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-3 pr-1 py-2 overscroll-contain">
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div
              key={m.id}
              className={`flex items-start space-x-2.5 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                  isUser
                    ? 'bg-[#6366f1]/20 border border-[#6366f1]/40 text-[#a5b4fc]'
                    : 'bg-[#00d084]/20 border border-[#00d084]/40 text-[#00d084]'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Zap className="w-4 h-4 fill-[#00d084]" />}
              </div>

              <div
                className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-lg ${
                  isUser
                    ? 'bg-[#25224d] text-white border border-[#4338ca]/50 rounded-tr-sm'
                    : 'bg-[#111726] text-[#e2e8f0] border border-[#1e293b] rounded-tl-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{m.text}</p>
                <span className="block text-[9px] text-[#64748b] text-right mt-1.5 font-medium">
                  {m.timestamp}
                </span>
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-start space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#00d084]/20 border border-[#00d084]/40 flex items-center justify-center text-[#00d084]">
              <Zap className="w-4 h-4 fill-[#00d084] animate-pulse" />
            </div>
            <div className="bg-[#111726] border border-[#1e293b] rounded-2xl p-3.5 text-xs text-[#94a3b8] flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-[#00d084] animate-bounce" />
              <span className="w-2 h-2 rounded-full bg-[#00d084] animate-bounce [animation-delay:0.2s]" />
              <span className="w-2 h-2 rounded-full bg-[#00d084] animate-bounce [animation-delay:0.4s]" />
              <span className="text-[11px] ml-1">Тренер думает...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Chips */}
      <div className="flex items-center space-x-2 overflow-x-auto py-2 no-scrollbar">
        {quickPrompts.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(q)}
            disabled={isLoading}
            className="shrink-0 bg-[#111726] hover:bg-[#1e293b] active:scale-95 border border-[#1e293b] text-[#94a3b8] hover:text-white px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div className="pt-1">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2 bg-[#111726] border border-[#1e293b] p-1.5 rounded-2xl focus-within:border-[#00d084] transition-all"
        >
          <input
            type="text"
            placeholder="Спроси тренера о питании или тренировках..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            className="flex-1 bg-transparent px-3 py-2 text-xs text-white placeholder-[#64748b] focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="w-9 h-9 rounded-xl bg-[#00d084] hover:bg-[#00b572] disabled:opacity-40 disabled:hover:bg-[#00d084] active:scale-95 text-[#0b0f19] flex items-center justify-center transition-all shadow-md shadow-[#00d084]/20"
          >
            <Send className="w-4 h-4 fill-[#0b0f19]" />
          </button>
        </form>
      </div>
    </div>
  );
};
