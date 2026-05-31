"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      {/* Kafka avatar — crimson dot, left side only */}
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-[#8B0000] flex items-center justify-center text-xs font-bold text-white mr-3 mt-1 shrink-0">
          K
        </div>
      )}

      <div
        className={cn(
          "max-w-xl px-4 py-3 rounded-2xl text-sm leading-relaxed",
          isUser
            ? "bg-neutral-800 text-white rounded-tr-sm"
            : "bg-transparent text-neutral-200 rounded-tl-sm"
        )}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
