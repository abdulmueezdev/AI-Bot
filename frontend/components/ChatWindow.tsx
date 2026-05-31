"use client";

import { useEffect, useRef, useCallback, useReducer, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ArrowUpIcon } from "lucide-react";
import MessageBubble from "./MessageBubble";
import { sendMessage } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type State = {
  messages: Message[];
  isLoading: boolean;
};

type Action =
  | { type: "ADD_MESSAGE"; message: Message }
  | { type: "SET_LOADING"; loading: boolean };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };
    case "SET_LOADING":
      return { ...state, isLoading: action.loading };
    default:
      return state;
  }
}

// ── Auto-resize hook ───────────────────────────────────────────────────────
function useAutoResizeTextarea(minHeight: number, maxHeight = 200) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = `${minHeight}px`;
      if (!reset) {
        el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
      }
    },
    [minHeight, maxHeight]
  );

  useEffect(() => {
    if (textareaRef.current)
      textareaRef.current.style.height = `${minHeight}px`;
  }, [minHeight]);

  useEffect(() => {
    const handler = () => adjustHeight();
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function ChatWindow() {
  const [state, dispatch] = useReducer(reducer, {
    messages: [],
    isLoading: false,
  });
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea(60, 200);



  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages, state.isLoading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || state.isLoading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    dispatch({ type: "ADD_MESSAGE", message: userMsg });
    setInput("");
    adjustHeight(true);
    dispatch({ type: "SET_LOADING", loading: true });

    try {
      // sendMessage from lib/api.ts — DO NOT change api.ts
      const reply = await sendMessage(text);
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply.response,
        },
      });
    } catch {
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Something went wrong. Try again.",
        },
      });
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasMessages = state.messages.length > 0;

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0a] text-white">

      {/* ── Message area ── */}
      <div className="flex-1 overflow-y-auto px-4 py-8">
        {!hasMessages ? (
          // Empty state — centered heading
          <div className="flex flex-col items-center justify-center h-full">
            <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
              Speak with Alucard
            </h1>
            <p className="text-neutral-500 text-sm">
              Franz Kafka — Prague, 1922
            </p>
          </div>
        ) : (
          // Message list
          <div className="max-w-3xl mx-auto space-y-6">
            {state.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Typing indicator */}
            {state.isLoading && (
              <div className="flex items-center gap-2 text-neutral-500 text-sm">
                <span className="w-2 h-2 bg-[#8B0000] rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-[#8B0000] rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-[#8B0000] rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Input box (v0-style, pinned to bottom) ── */}
      <div className="px-4 pb-6 pt-2">
        <div className="max-w-3xl mx-auto">
          {/* Heading shown above input only when no messages yet */}
          {!hasMessages && (
            <div />  // heading is in the empty state above
          )}

          <div className="relative bg-neutral-900 rounded-xl border border-neutral-800">
            <div className="overflow-y-auto">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  adjustHeight();
                }}
                onKeyDown={handleKeyDown}
                placeholder="Write to Kafka..."
                className={cn(
                  "w-full px-4 py-3",
                  "resize-none",
                  "bg-transparent",
                  "border-none",
                  "text-white text-sm",
                  "focus:outline-none",
                  "focus-visible:ring-0 focus-visible:ring-offset-0",
                  "placeholder:text-neutral-500 placeholder:text-sm",
                  "min-h-[60px]"
                )}
                style={{ overflow: "hidden" }}
              />
            </div>

            {/* Bottom bar — send button only, no extra buttons */}
            <div className="flex items-center justify-end p-3">
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || state.isLoading}
                className={cn(
                  "px-1.5 py-1.5 rounded-lg text-sm transition-colors border flex items-center gap-1",
                  input.trim() && !state.isLoading
                    ? "bg-[#8B0000] border-[#8B0000] text-white hover:bg-[#a00000]"
                    : "border-zinc-700 text-zinc-600 cursor-not-allowed"
                )}
              >
                <ArrowUpIcon className="w-4 h-4" />
                <span className="sr-only">Send</span>
              </button>
            </div>
          </div>

          <p className="text-center text-neutral-700 text-xs mt-3">
            Alucard may make errors — always verify with primary sources.
          </p>
        </div>
      </div>
    </div>
  );
}
