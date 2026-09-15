import { motion } from 'framer-motion';

interface QuoteCardProps {
  text: string;
  author: string;
  source?: string;
}

export default function QuoteCard({ text, author, source }: QuoteCardProps) {
  return (
    <motion.blockquote 
      className="relative my-4 p-6 pl-8 border-l-4 border-indigo-500 bg-slate-900/50 rounded-r-lg shadow-sm"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="absolute top-4 left-2 text-4xl text-indigo-500/20 font-serif leading-none">"</div>
      <p className="text-slate-300 italic text-lg leading-relaxed relative z-10">
        {text}
      </p>
      <footer className="mt-3 text-sm text-slate-400 font-medium flex items-center gap-2">
        <div className="w-4 h-[1px] bg-indigo-500/50" />
        <span className="text-indigo-400">{author}</span>
        {source && <span className="text-slate-500">— {source}</span>}
      </footer>
    </motion.blockquote>
  );
}
