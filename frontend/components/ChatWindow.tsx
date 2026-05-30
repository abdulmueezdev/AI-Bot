"use client";

import React, { useState, useRef, useEffect, useReducer } from "react";
import MessageBubble from "./MessageBubble";
import { sendMessage } from "../lib/api";

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
};

type State = {
  messages: Message[];
  isLoading: boolean;
};

type Action =
  | { type: "ADD_MESSAGE"; payload: Message }
  | { type: "SET_LOADING"; payload: boolean };

const initialState: State = {
  messages: [
    {
      id: "welcome",
      role: "assistant",
      content: "I am Alucard. State your business, mortal.",
      timestamp: new Date(),
    },
  ],
  isLoading: false,
};

function chatReducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.payload] };
    case "SET_LOADING":
      return { ...state, isLoading: action.payload };
    default:
      return state;
  }
}

export default function ChatWindow() {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state.messages, state.isLoading]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    if (!inputValue.trim() || state.isLoading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    dispatch({ type: "ADD_MESSAGE", payload: userMsg });
    setInputValue("");
    dispatch({ type: "SET_LOADING", payload: true });

    try {
      const data = await sendMessage(userMsg.content);
      
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };
      
      dispatch({ type: "ADD_MESSAGE", payload: assistantMsg });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Alucard is unavailable. Try again shortly.";
      dispatch({
        type: "ADD_MESSAGE",
        payload: {
          id: crypto.randomUUID(),
          role: "system",
          content: errorMessage,
          timestamp: new Date(),
        },
      });
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
      // Re-focus input after response
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto w-full relative bg-[#0a0a0a]">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-[#0a0a0a]/90 backdrop-blur-sm border-b border-[#1f1f1f] py-4 px-6 flex items-center justify-center shadow-sm shadow-black/50">
        <h1 className="text-xl font-serif text-gray-200 tracking-wider">
          <span className="text-[#8B0000]">A</span>LUCARD
        </h1>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 scroll-smooth">
        <div className="flex flex-col space-y-2">
          {state.messages.map((msg) => (
            <MessageBubble key={msg.id} {...msg} />
          ))}
          
          {state.isLoading && (
            <div className="flex w-full mb-6 justify-start">
              <div className="flex max-w-[85%] sm:max-w-[75%] flex-row">
                <div className="flex-shrink-0 mr-3 mt-1">
                  <div className="w-8 h-8 rounded-full bg-[#8B0000] flex items-center justify-center text-white font-serif font-bold text-sm shadow-md">
                    A
                  </div>
                </div>
                <div className="flex flex-col">
                  <div className="flex items-baseline mb-1 justify-start mr-2">
                    <span className="text-xs font-semibold text-gray-400">Alucard</span>
                  </div>
                  <div className="px-5 py-4 rounded-2xl shadow-sm bg-[#111111] border border-[#8B0000]/30 rounded-tl-none flex items-center space-x-1.5 h-11">
                    <div className="w-1.5 h-1.5 bg-[#8B0000] rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-1.5 h-1.5 bg-[#8B0000] rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-1.5 h-1.5 bg-[#8B0000] rounded-full animate-bounce"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 p-4 sm:p-6 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a] to-transparent pt-8">
        <div className="relative flex items-center max-w-3xl mx-auto">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={state.isLoading}
            placeholder={state.isLoading ? "Waiting for Alucard..." : "Speak to him..."}
            className="w-full bg-[#111111] border border-[#1f1f1f] focus:border-[#8B0000]/50 text-gray-100 placeholder-gray-600 rounded-full py-4 pl-6 pr-16 shadow-lg outline-none transition-colors disabled:opacity-50"
            aria-label="Chat input"
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || state.isLoading}
            aria-label="Send message"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-[#8B0000] hover:bg-red-800 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-full transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 ml-0.5">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
