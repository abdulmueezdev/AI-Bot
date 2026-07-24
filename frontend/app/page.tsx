"use client";

import { useReducer, useState, useRef, useEffect } from "react";
import ChatHeader from "@/components/ChatHeader";
import ChatMessage from "@/components/ChatMessage";
import EmptyState from "@/components/EmptyState";
import ChatInput from "@/components/ChatInput";
import { sendMessage } from "@/lib/api";

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

export default function Home() {
  const [state, dispatch] = useReducer(reducer, {
    messages: [],
    isLoading: false,
  });
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages, state.isLoading]);

  // Keep-alive ping to prevent Render instance from spinning down
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://ai-bot-tp8d.onrender.com";
    const ping = () => fetch(`${apiUrl}/health`).catch(() => {});
    ping(); // ping on load to wake it up immediately
    const interval = setInterval(ping, 10 * 60 * 1000); // every 10 minutes
    return () => clearInterval(interval);
  }, []);

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
    dispatch({ type: "SET_LOADING", loading: true });

    try {
      const reply = await sendMessage(text);
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply.response,
        },
      });
    } catch (error: any) {
      if (error.name === "AbortError") {
        dispatch({
          type: "ADD_MESSAGE",
          message: {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Waking up the system, please wait...",
          },
        });

        try {
          const retryReply = await sendMessage(text);
          dispatch({
            type: "ADD_MESSAGE",
            message: {
              id: crypto.randomUUID(),
              role: "assistant",
              content: retryReply.response,
            },
          });
        } catch (retryError) {
          dispatch({
            type: "ADD_MESSAGE",
            message: {
              id: crypto.randomUUID(),
              role: "assistant",
              content: "THE SYSTEM IS UNRESPONSIVE.",
            },
          });
        }
      } else {
        dispatch({
          type: "ADD_MESSAGE",
          message: {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "THE SYSTEM IS UNRESPONSIVE.",
          },
        });
      }
    } finally {
      dispatch({ type: "SET_LOADING", loading: false });
    }
  };

  const hasMessages = state.messages.length > 0;

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden">
      <ChatHeader />
      
      {/* CHAT AREA */}
      <main className="flex-1 overflow-y-auto w-full flex flex-col relative z-10 px-4 md:px-8">
        <div className="w-full flex flex-col min-h-full pb-32 pt-4 md:pt-12 max-w-5xl mx-auto">
          
          {!hasMessages && <EmptyState />}
          
          {/* Chat Content Container */}
          <div className="flex flex-col space-y-6 md:space-y-8 z-10 w-full relative">
            {state.messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}

            {/* Typing Indicator (Kafka) */}
            {state.isLoading && (
              <div className="flex items-start w-[85%] md:w-3/4 mr-auto relative ml-12 md:ml-24 opacity-80 mt-2 md:mt-4">
                <div className="font-headline-lg font-black text-4xl md:text-7xl text-brutal-text leading-none break-words z-10 relative">
                  <span className="blinking-cursor">▌</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} className="h-4" />
          </div>
        </div>
      </main>

      <ChatInput 
        input={input} 
        setInput={setInput} 
        handleSend={handleSend} 
        isLoading={state.isLoading} 
      />
    </div>
  );
}
