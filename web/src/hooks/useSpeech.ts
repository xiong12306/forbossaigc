import { useCallback, useEffect, useRef, useState } from "react";

// Web Speech API 在标准 lib.dom.d.ts 中类型不全，统一用 any 兜底
type AnySpeechRecognition = any;

interface SpeechSupport {
  recognition: boolean;
  synthesis: boolean;
}

/**
 * 封装 Web Speech API：
 * - SpeechRecognition：语音识别（中文），支持开始/停止录音
 * - SpeechSynthesis：语音合成（中文播报）
 * 浏览器不支持时优雅降级
 */
export function useSpeech() {
  const [isRecording, setIsRecording] = useState(false);
  const [supported, setSupported] = useState<SpeechSupport>({
    recognition: false,
    synthesis: false,
  });
  const recognitionRef = useRef<AnySpeechRecognition | null>(null);

  useEffect(() => {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    setSupported({
      recognition: !!SR,
      synthesis: "speechSynthesis" in window,
    });
  }, []);

  /** 开始录音，识别结果通过 onResult 回调返回 */
  const startRecording = useCallback(
    (onResult: (text: string) => void) => {
      const SR =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;
      if (!SR) return;
      // 已在录音则先停
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          /* ignore */
        }
      }
      const rec: AnySpeechRecognition = new SR();
      rec.lang = "zh-CN";
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onresult = (e: any) => {
        const text = (e.results?.[0]?.[0]?.transcript ?? "") as string;
        if (text) onResult(text);
      };
      rec.onend = () => setIsRecording(false);
      rec.onerror = () => setIsRecording(false);
      try {
        rec.start();
        recognitionRef.current = rec;
        setIsRecording(true);
      } catch {
        setIsRecording(false);
      }
    },
    []
  );

  /** 停止录音 */
  const stopRecording = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    setIsRecording(false);
  }, []);

  /** 朗读中文文本 */
  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window) || !text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    u.rate = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }, []);

  return { isRecording, supported, startRecording, stopRecording, speak };
}
