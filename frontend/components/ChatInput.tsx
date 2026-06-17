"use client";

import { useRef, useEffect } from "react";

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  handleSend: () => void;
  isLoading: boolean;
}

export default function ChatInput({ input, setInput, handleSend, isLoading }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "96px"; // min-height
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 300)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full bg-brutal-bg shrink-0 z-20 p-8 pb-12">
      <div className="w-full flex flex-col relative max-w-5xl mx-auto">
        <div className="relative flex items-end w-full">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full bg-brutal-accent border-4 border-brutal-text text-brutal-text focus:border-error focus:outline-none focus:ring-0 resize-none font-mono text-xl p-6 pr-32 h-24 min-h-[96px] max-h-[300px] overflow-y-auto leading-relaxed shadow-[8px_8px_0_0_#fff5e6] rounded-none uppercase placeholder:text-outline"
            placeholder="ENTER YOUR DEFENSE..."
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="absolute right-6 bottom-6 bg-brutal-text text-brutal-bg font-mono font-bold px-6 py-3 uppercase tracking-widest hover:bg-error hover:text-brutal-text transition-colors duration-200 border-2 border-brutal-bg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Submit
          </button>
        </div>
        <div className="mt-6 flex justify-between w-full font-mono text-sm font-bold tracking-widest uppercase text-outline">
          <span>{isLoading ? "System: Waiting..." : "System: Ready"}</span>
          <span>Press Enter to Submit</span>
        </div>
      </div>
    </div>
  );
}
