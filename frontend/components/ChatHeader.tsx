export default function ChatHeader() {
  return (
    <header className="flex justify-between items-start w-full px-8 py-8 bg-transparent z-10 shrink-0">
      {/* Left: Monogram */}
      <div className="flex items-center">
        <div className="w-16 h-16 bg-brutal-accent flex items-center justify-center border-4 border-brutal-text shadow-[4px_4px_0_0_#fff5e6] transform -rotate-6">
          <span className="font-headline-lg font-black text-3xl text-brutal-text">K.</span>
        </div>
      </div>
      {/* Center: Title */}
      <div className="text-left flex-1 ml-8 mt-2">
        <h1 className="font-headline-lg font-black text-5xl text-brutal-text uppercase tracking-tighter m-0 leading-none">Franz Kafka</h1>
        <p className="font-mono text-sm text-outline mt-2 font-bold tracking-widest">PRAGUE · 1922</p>
      </div>
      {/* Right: Actions/Indicator */}
      <div className="flex flex-col items-end space-y-4 mt-2">
        <div className="flex items-center space-x-2 border-2 border-brutal-text px-3 py-1 bg-brutal-accent shadow-[2px_2px_0_0_#fff5e6]">
          <div className="w-3 h-3 bg-error animate-pulse rounded-none"></div>
          <span className="font-mono text-sm font-bold tracking-widest text-brutal-text uppercase">RAG ACTIVE</span>
        </div>
        <button 
          onClick={() => window.location.reload()}
          className="text-brutal-text hover:text-error transition-colors duration-300 focus:outline-none border-b-2 border-brutal-text pb-1 font-mono text-sm uppercase tracking-widest"
        >
          Clear Record
        </button>
      </div>
    </header>
  );
}
