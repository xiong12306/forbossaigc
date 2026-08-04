import { useState, useRef, type RefObject } from "react";
import { Send, Mic, Square, Image as ImageIcon, X, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useSpeech } from "@/hooks/useSpeech";

interface Props {
  onSend: (text: string, images?: string[]) => void;
  onUpload: (file: File) => Promise<string>;
  loading: boolean;
  inputRef?: RefObject<HTMLInputElement>;
}

const QUICK_TYPES = [
  { value: "main", label: "商品主图", emoji: "📸" },
  { value: "detail", label: "详情图", emoji: "🔍" },
  { value: "scene", label: "场景图", emoji: "🏠" },
  { value: "poster", label: "营销海报", emoji: "🎨" },
  { value: "carousel", label: "轮播图", emoji: "🎞️" },
] as const;

/**
 * 底部输入区：文字输入 + 图片上传 + 快捷出图按钮 + 语音按钮
 * 上传图片后直接显示快捷类型按钮，点击一键生成
 */
export default function InputBar({ onSend, onUpload, loading, inputRef }: Props) {
  const [value, setValue] = useState("");
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const { isRecording, supported, startRecording, stopRecording } = useSpeech();
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = (quickType?: string) => {
    const hasImages = pendingImages.length > 0;
    if ((!value.trim() && !hasImages && !quickType) || loading) return;
    let text = value.trim();
    if (quickType && hasImages) {
      // 快捷出图：直接发指令，后端自动跳过确认
      const typeName = QUICK_TYPES.find(t => t.value === quickType)?.label || quickType;
      text = `一键出${typeName}`;
    } else if (!text && hasImages) {
      text = "根据这张图出商品主图";
    }
    onSend(text, hasImages ? pendingImages : undefined);
    setValue("");
    setPendingImages([]);
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

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const url = await onUpload(file);
        setPendingImages((prev) => [...prev, url]);
      }
    } catch (err) {
      console.error("上传失败:", err);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeImage = (idx: number) => {
    setPendingImages((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="px-4 pb-4 pt-2">
      {/* 图片预览区 + 快捷出图按钮 */}
      <AnimatePresence>
        {pendingImages.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-3"
          >
            {/* 图片预览 */}
            <div className="flex gap-2 mb-2 flex-wrap items-center">
              {pendingImages.map((url, idx) => (
                <div key={idx} className="relative w-14 h-14 rounded-lg overflow-hidden border border-gold-500/30 flex-shrink-0">
                  <img src={url} alt={`参考图${idx + 1}`} className="w-full h-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeImage(idx)}
                    className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              <span className="text-xs text-ivory-400/60">选好类型，一键出图：</span>
            </div>
            {/* 快捷类型按钮 */}
            <div className="flex gap-2 flex-wrap">
              {QUICK_TYPES.map((t) => (
                <motion.button
                  key={t.value}
                  type="button"
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => submit(t.value)}
                  disabled={loading || uploading}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-gold-500/10 border border-gold-500/30 text-gold-300 hover:bg-gold-500/20 hover:border-gold-500/50 disabled:opacity-40 disabled:cursor-not-allowed transition text-sm"
                >
                  <span>{t.emoji}</span>
                  <span>{t.label}</span>
                  <Sparkles className="w-3 h-3 ml-0.5" />
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center gap-2 bg-brown-800/60 backdrop-blur border border-gold-500/20 rounded-full pl-3 pr-1.5 py-1.5 focus-within:border-gold-500/50 transition">
        {/* 图片上传按钮 */}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={loading || uploading}
          className="w-8 h-8 rounded-full flex items-center justify-center text-gold-400 hover:bg-brown-700/60 disabled:opacity-40 transition flex-shrink-0"
          aria-label="上传图片"
        >
          {uploading ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-4 h-4 border-2 border-gold-400/30 border-t-gold-400 rounded-full"
            />
          ) : (
            <ImageIcon className="w-4 h-4" />
          )}
        </button>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          disabled={loading}
          placeholder={loading ? "助手思考中…" : "发张图或说点什么，回车发送"}
          className="flex-1 bg-transparent outline-none text-sm text-ivory-500 placeholder:text-ivory-400/40 disabled:opacity-50 min-w-0"
        />
        {supported.recognition && (
          <motion.button
            type="button"
            onClick={toggleMic}
            disabled={loading}
            whileTap={{ scale: 0.92 }}
            className={`relative w-9 h-9 rounded-full flex items-center justify-center transition flex-shrink-0 ${
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
          onClick={() => submit()}
          disabled={loading || uploading || (!value.trim() && pendingImages.length === 0)}
          className="w-9 h-9 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed transition shadow-gold-glow flex-shrink-0"
          aria-label="发送"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
