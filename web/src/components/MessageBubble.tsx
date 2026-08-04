import { motion } from "framer-motion";
import type { ChatMessage } from "@/types";

interface Props {
  message: ChatMessage;
}

/**
 * 单条消息气泡：老板右对齐暖象牙底，助手左对齐深褐底琥珀金描边
 */
export default function MessageBubble({ message }: Props) {
  const isBoss = message.role === "boss";
  return (
    <motion.div
      initial={{ opacity: 0, x: isBoss ? 20 : -20, y: 6 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ type: "spring", stiffness: 280, damping: 24 }}
      className={`flex ${isBoss ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
          isBoss
            ? "bg-ivory-400 text-brown-900 rounded-br-md"
            : "bg-brown-800/80 text-ivory-500 border border-gold-500/30 rounded-bl-md"
        }`}
      >
        {/* 老板上传的参考图 */}
        {message.images && message.images.length > 0 && (
          <div className={`flex gap-2 flex-wrap mb-2 ${message.text ? "" : ""}`}>
            {message.images.map((url, idx) => (
              <img
                key={idx}
                src={url}
                alt={`参考图${idx + 1}`}
                className="max-w-[200px] max-h-[200px] rounded-lg object-cover"
              />
            ))}
          </div>
        )}
        {message.text}
        {message.followUp && (
          <div className="mt-2 pt-2 border-t border-gold-500/20 text-gold-300 text-xs">
            {message.followUp}
          </div>
        )}
      </div>
    </motion.div>
  );
}
