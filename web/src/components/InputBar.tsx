import { useState, type RefObject } from "react";
import { Send, Mic, Square } from "lucide-react";
import { motion } from "framer-motion";
import { useSpeech } from "@/hooks/useSpeech";

interface Props {
  onSend: (text: string) => void;
  loading: boolean;
  inputRef?: RefObject<HTMLInputElement>;
}

/**
 * 底部输入区：文字输入 + 发送按钮 + 语音按钮（录音态红色脉冲）
 */
export default function InputBar({ onSend, loading, inputRef }: Props) {
  const [value, setValue] = useState("");
  const { isRecording, supported, startRecording, stopRecording } = useSpeech();

  const submit = () => {
    const v = value.trim();
    if (!v || loading) return;
    onSend(v);
    setValue("");
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const toggleMic = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording((text) => {
        setValue((v) => (v ? v + " " : "") + text);
        inputRef?.current?.focus();
      });
    }
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="flex items-center gap-2 bg-brown-800/60 backdrop-blur border border-gold-500/20 rounded-full pl-5 pr-1.5 py-1.5 focus-within:border-gold-500/50 transition">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          disabled={loading}
          placeholder={loading ? "助手思考中…" : "对 BossAIGC 说点什么，回车发送"}
          className="flex-1 bg-transparent outline-none text-sm text-ivory-500 placeholder:text-ivory-400/40 disabled:opacity-50"
        />
        {supported.recognition && (
          <motion.button
            type="button"
            onClick={toggleMic}
            disabled={loading}
            whileTap={{ scale: 0.92 }}
            className={`relative w-9 h-9 rounded-full flex items-center justify-center transition ${
              isRecording
                ? "bg-red-500/20 text-red-400"
                : "text-gold-400 hover:bg-brown-700/60"
            }`}
            aria-label="语音输入"
          >
            {isRecording && (
              <motion.span
                className="absolute inset-0 rounded-full bg-red-500/40"
                animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
              />
            )}
            {isRecording ? (
              <Square className="w-3.5 h-3.5 relative z-10" />
            ) : (
              <Mic className="w-4 h-4 relative z-10" />
            )}
          </motion.button>
        )}
        <button
          type="button"
          onClick={submit}
          disabled={loading || !value.trim()}
          className="w-9 h-9 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed transition shadow-gold-glow"
          aria-label="发送"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
