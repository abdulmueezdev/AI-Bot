import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export default function MessageBubble({ role, content, timestamp }: MessageBubbleProps) {
  const isAlucard = role === 'assistant';
  const isSystem = role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <span className="text-xs text-[#8B0000] font-medium italic bg-red-950/20 px-3 py-1 rounded-full border border-red-900/30">
          {content}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex w-full mb-6 ${isAlucard ? 'justify-start' : 'justify-end'}`}>
      <div className={`flex max-w-[85%] sm:max-w-[75%] ${isAlucard ? 'flex-row' : 'flex-row-reverse'}`}>
        
        {isAlucard && (
          <div className="flex-shrink-0 mr-3 mt-1">
            <div className="w-8 h-8 rounded-full bg-[#8B0000] flex items-center justify-center text-white font-serif font-bold text-sm shadow-md">
              A
            </div>
          </div>
        )}

        <div className="flex flex-col">
          <div className={`flex items-baseline mb-1 ${isAlucard ? 'justify-start mr-2' : 'justify-end ml-2'}`}>
            <span className="text-xs font-semibold text-gray-400">
              {isAlucard ? 'Alucard' : 'You'}
            </span>
            <span className="text-[10px] text-gray-600 ml-2">
              {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          <div 
            className={`px-4 py-3 rounded-2xl shadow-sm ${
              isAlucard 
                ? 'bg-[#111111] border border-[#8B0000]/30 text-gray-200 rounded-tl-none' 
                : 'bg-neutral-800 text-gray-100 rounded-tr-none'
            }`}
          >
            {isAlucard ? (
              <div className="prose prose-invert prose-sm prose-p:leading-relaxed prose-pre:bg-black/50 prose-pre:border prose-pre:border-gray-800">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>
            )}
          </div>
        </div>
        
      </div>
    </div>
  );
}
