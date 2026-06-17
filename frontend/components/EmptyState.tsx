export default function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03]">
      <p className="font-headline-lg font-black text-4xl md:text-5xl text-center max-w-2xl md:max-w-4xl text-brutal-text uppercase leading-none tracking-tighter">
        CONFESS YOUR GUILT.<br/>THE TRIAL HAS ALREADY BEGUN.
      </p>
    </div>
  );
}
