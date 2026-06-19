export default function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.015] md:opacity-[0.03] z-0 overflow-hidden px-4">
      <p className="font-headline-lg font-black text-2xl md:text-5xl text-center w-full max-w-2xl md:max-w-4xl text-brutal-text uppercase leading-none tracking-tighter">
        CONFESS YOUR GUILT.<br/>THE TRIAL HAS ALREADY BEGUN.
      </p>
    </div>
  );
}
