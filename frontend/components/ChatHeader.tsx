export default function ChatHeader() {
  return (
    <header className="flex justify-between items-start w-full max-w-full overflow-hidden px-4 md:px-8 py-4 md:py-8 bg-transparent z-10 shrink-0 box-border">
      {/* Left: Monogram */}
      <div className="flex items-center shrink-0">
        <div className="w-12 h-12 md:w-16 md:h-16 bg-brutal-accent flex items-center justify-center border-4 border-brutal-text shadow-[4px_4px_0_0_#fff5e6] transform -rotate-6">
          <span className="font-headline-lg font-black text-2xl md:text-3xl text-brutal-text">K.</span>
        </div>
      </div>
      {/* Center: Title */}
      <div className="text-left flex-1 ml-4 md:ml-8 mt-1 md:mt-2 overflow-hidden">
        <h1 className="font-headline-lg font-black text-2xl md:text-4xl lg:text-5xl text-brutal-text uppercase tracking-tighter m-0 leading-none truncate">Franz Kafka</h1>
        <p className="hidden sm:block font-mono text-xs md:text-sm text-outline mt-1 md:mt-2 font-bold tracking-widest">PRAGUE · 1922</p>
      </div>
      {/* Right: Actions/Indicator */}
      <div className="flex flex-col items-end space-y-2 md:space-y-4 mt-1 md:mt-2 shrink-0 ml-2">
        <div className="flex items-center space-x-1 md:space-x-2 border-2 border-brutal-text px-2 md:px-3 py-1 bg-brutal-accent shadow-[2px_2px_0_0_#fff5e6]">
          <div className="w-2 h-2 md:w-3 md:h-3 bg-error animate-pulse rounded-none"></div>
          <span className="font-mono text-[10px] md:text-sm font-bold tracking-widest text-brutal-text uppercase whitespace-nowrap">RAG ACTIVE</span>
        </div>
        <button 
          onClick={() => window.location.reload()}
          className="text-brutal-text hover:text-error transition-colors duration-300 focus:outline-none border-b-2 border-brutal-text pb-1 font-mono text-[10px] md:text-sm uppercase tracking-widest whitespace-nowrap"
        >
          Clear Record
        </button>
      </div>
    </header>
  );
}
