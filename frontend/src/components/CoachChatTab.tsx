import React, { useState, useRef, useEffect } from 'react';
import { Send, Zap, User, Trash2 } from 'lucide-react';
import type { ChatMessage } from '../types';
import { CoachMemory } from './CoachMemory';
import { EveningReportTest } from './EveningReportTest';

interface CoachChatTabProps {
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  onSendMessage: (msg: string) => Promise<string>;
  onClearHistory: () => void;
  initialPrompt?: string | null;
  onClearInitialPrompt?: () => void;
  analysisBusy?: boolean;
  analysisError?: string;
  onRetryAnalysis?: () => void;
}

export const CoachChatTab: React.FC<CoachChatTabProps> = ({
  messages,
  setMessages,
  onSendMessage,
  onClearHistory,
  initialPrompt,
  onClearInitialPrompt,
  analysisBusy = false,
  analysisError = '',
  onRetryAnalysis,
}) => {
  const [showPrompts, setShowPrompts] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const isBusy = isLoading || analysisBusy;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const latestReport = [...messages].reverse().find(message => /^evening-\d{4}-/.test(message.id));
  const quickPrompts = [
    '🍳 Что съесть на ужин (400 ккал)?',
    '🥗 Разбери рацион за сегодня',
    '💻 План на 30 мин изучения JavaScript',
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
  }, [messages, isBusy]);

  useEffect(() => {
    if (initialPrompt && initialPrompt.trim()) {
      setInput(initialPrompt.trim());
      onClearInitialPrompt?.();
      inputRef.current?.focus();
    }
  }, [initialPrompt]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isBusy) return;

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
    <div className="pulse-coach flex-1 flex flex-col min-h-0 w-full max-w-4xl mx-auto px-3 pb-[calc(4.75rem+env(safe-area-inset-bottom,0px))]">

      {latestReport && <button type="button" className="coach-report-link" onClick={() => document.getElementById(`message-${latestReport.id}`)?.scrollIntoView({behavior:'smooth', block:'center'})}>🌙 Вечерний отчёт · {latestReport.timestamp} ↗</button>}
      {/* Top Header Bar for Chat */}
      <div className="coach-chat-heading flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-[#79c5a6] animate-pulse" />
          <h2>AI-тренер</h2>
          {messages.length > 1 && (
            <span className="text-[10px] text-[#91a797]">({messages.length} сообщ.)</span>
          )}
        </div>
        {messages.length > 1 && (
          <button
            onClick={onClearHistory}
            disabled={isBusy}
            title="Очистить историю сообщений"
            className="flex items-center space-x-1 text-[11px] text-[#91a797] hover:text-rose-400 active:scale-95 transition-all px-2 py-0.5 rounded-lg hover:bg-rose-500/10"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Очистить</span>
          </button>
        )}
      </div>
      <div className="coach-tools"><CoachMemory /><EveningReportTest onMessage={message => setMessages(current => current.some(item => item.id === message.id) ? current : [...current, message])} /></div>

      {analysisError && <div role="alert" className="shrink-0 my-2 p-3 rounded-xl border border-rose-500/20 bg-rose-500/5 text-xs text-rose-300 space-y-2">
        <p>{analysisError}</p>
        <button disabled={isBusy} onClick={onRetryAnalysis} className="px-3 py-2 rounded-lg bg-[#233028] border border-[#33473b] text-[#e6eee8] disabled:opacity-40">Повторить разбор</button>
      </div>}

      {/* Messages Scroll Area */}
      <div className="coach-messages flex-1 min-h-0 overflow-y-auto space-y-3 pr-1 py-2 overscroll-contain" role="log" aria-label="Переписка с тренером">
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div
              key={m.id}
              id={`message-${m.id}`}
              className={`flex items-start space-x-2.5 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`coach-avatar w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                  isUser
                    ? 'bg-[#e7a27d]/20 border border-[#e7a27d]/40 text-[#dcaf89]'
                    : 'bg-[#79c5a6]/20 border border-[#79c5a6]/40 text-[#79c5a6]'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Zap className="w-4 h-4 fill-[#79c5a6]" />}
              </div>

              <div
                className={`coach-bubble max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-lg ${
                  isUser
                    ? 'bg-[#3c3027] text-[#e6eee8] border border-[#4338ca]/50 rounded-tr-sm'
                    : 'bg-[#19221f] text-[#d0ddd2] border border-[#33473b] rounded-tl-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{m.text}</p>
                <span className="block text-[9px] text-[#91a797] text-right mt-1.5 font-medium">
                  {m.timestamp}
                </span>
              </div>
            </div>
          );
        })}

        {isBusy && (
          <div role="status" aria-label="ИИ анализирует данные" className="flex items-start space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#79c5a6]/20 border border-[#79c5a6]/40 flex items-center justify-center text-[#79c5a6]">
              <Zap className="w-4 h-4 fill-[#79c5a6] animate-pulse" />
            </div>
            <div className="bg-[#19221f] border border-[#33473b] rounded-2xl p-3.5 text-xs text-[#a4b8aa] flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-[#79c5a6] animate-bounce" />
              <span className="w-2 h-2 rounded-full bg-[#79c5a6] animate-bounce [animation-delay:0.2s]" />
              <span className="w-2 h-2 rounded-full bg-[#79c5a6] animate-bounce [animation-delay:0.4s]" />
              <span className="text-[11px] ml-1">Тренер думает...</span>
            </div>
          </div>
        )}
        {analysisBusy && <p className="text-xs text-[#a4b8aa] pl-11">Анализирую данные выбранной недели…</p>}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Chips */}
      <div className="coach-prompts shrink-0"><button type="button" className="coach-prompts-toggle" aria-expanded={showPrompts} aria-controls="coach-quick-prompts" onClick={() => setShowPrompts(value => !value)}>{showPrompts ? 'Скрыть подсказки −' : 'Идеи для вопроса +'}</button>
      {showPrompts && <div id="coach-quick-prompts" className="flex items-center space-x-2 overflow-x-auto py-2 no-scrollbar shrink-0">
        {quickPrompts.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(q)}
            disabled={isBusy}
            className="shrink-0 bg-[#19221f] hover:bg-[#33473b] active:scale-95 border border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8] px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
          >
            {q}
          </button>
        ))}
      </div>}</div>

      {/* Input Bar */}
      <div className="pt-1 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2 bg-[#19221f] border border-[#33473b] p-1.5 rounded-2xl focus-within:border-[#79c5a6] transition-all"
        >
          <input
            ref={inputRef}
            type="text"
            aria-label="Сообщение тренеру"
            placeholder="Напиши тренеру…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isBusy}
            className="flex-1 bg-transparent px-3 py-2 text-xs text-[#e6eee8] placeholder-[#91a797] focus:outline-none"
          />
          <button
            aria-label="Отправить сообщение"
            type="submit"
            disabled={!input.trim() || isLoading}
            className="w-9 h-9 rounded-xl bg-[#79c5a6] hover:bg-[#90d4b8] disabled:opacity-40 disabled:hover:bg-[#79c5a6] active:scale-95 text-[#10261b] flex items-center justify-center transition-all shadow-md shadow-[#218d79]/20"
          >
            <Send className="w-4 h-4 fill-[#fffdf5]" />
          </button>
        </form>
      </div>
    </div>
  );
};
