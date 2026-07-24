import { useEffect, useRef, type RefObject } from "react";
import { AnimatePresence } from "framer-motion";
import MessageBubble from "./MessageBubble";
import InputBar from "./InputBar";
import type { ChatMessage } from "@/types";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => void;
  inputRef?: RefObject<HTMLInputElement>;
}

/**
 * 中间聊天流：消息气泡列表 + 底部输入栏，自动滚动到底部
 */
export default function ChatStream({ messages, loading, onSend, inputRef }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-3">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="font-serif text-3xl text-gold-400 mb-2">
              向老板 AI 下达指令
            </div>
            <p className="text-sm text-ivory-400/60 max-w-md">
              试着说：「小帮小帮，给保温杯出 3 张主图，轻奢暖色调」
            </p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </AnimatePresence>
        {loading && (
          <div className="flex justify-start">
            <div className="bg-brown-800/80 border border-gold-500/30 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-gold-400/70 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <InputBar onSend={onSend} loading={loading} inputRef={inputRef} />
    </div>
  );
}
