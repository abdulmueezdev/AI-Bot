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
    <div className="w-full max-w-full box-border bg-brutal-bg shrink-0 z-20 p-4 pb-6 md:p-8 md:pb-12 border-t-2 border-brutal-text md:border-none">
      <div className="w-full flex flex-col relative max-w-5xl mx-auto box-border">
        <div className="relative flex items-end w-full box-border">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 w-full box-border bg-brutal-accent border-4 border-brutal-text text-brutal-text focus:border-error focus:outline-none focus:ring-0 resize-none font-mono text-base md:text-xl p-4 pr-24 md:p-6 md:pr-32 h-20 md:h-24 min-h-[80px] md:min-h-[96px] max-h-[200px] md:max-h-[300px] overflow-y-auto leading-relaxed shadow-[4px_4px_0_0_#fff5e6] md:shadow-[8px_8px_0_0_#fff5e6] rounded-none uppercase placeholder:text-outline"
            placeholder="ENTER YOUR DEFENSE..."
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="absolute right-2 bottom-2 md:right-6 md:bottom-6 bg-brutal-text text-brutal-bg font-mono font-bold px-3 py-2 md:px-6 md:py-3 uppercase tracking-widest hover:bg-error hover:text-brutal-text transition-colors duration-200 border-2 border-brutal-bg disabled:opacity-50 disabled:cursor-not-allowed text-xs md:text-base shrink-0 whitespace-nowrap"
          >
            Submit
          </button>
        </div>
        <div className="mt-4 md:mt-6 flex justify-between w-full font-mono text-[10px] md:text-sm font-bold tracking-widest uppercase text-outline whitespace-nowrap">
          <span>{isLoading ? "SYSTEM: WAITING..." : "SYSTEM: READY"}</span>
          <span className="hidden sm:inline">PRESS ENTER TO SUBMIT</span>
          <span className="sm:hidden">↵ SUBMIT</span>
        </div>
      </div>
    </div>
  );
}
