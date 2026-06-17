export default function ChatMessage({ message }: { message: { role: string; content: string } }) {
  const isAssistant = message.role === "assistant";

  if (isAssistant) {
    return (
      <div className="flex items-start w-full max-w-2xl mr-auto relative ml-12 mb-8">
        <div className="absolute -left-12 -top-6 text-8xl font-black text-brutal-accent opacity-5 z-0 transform -rotate-12 select-none">
          K.
        </div>
        <div className="font-headline-lg font-black text-lg md:text-2xl text-brutal-text leading-snug tracking-normal break-words z-10 relative">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-end w-full mb-8">
      <div className="bg-brutal-text text-brutal-bg font-mono text-base md:text-lg p-6 md:p-8 w-full max-w-xl border-4 md:border-8 border-brutal-accent shadow-[-8px_8px_0_0_#1a0101] md:shadow-[-16px_16px_0_0_#1a0101] transform rotate-1">
        {message.content}
      </div>
    </div>
  );
}
