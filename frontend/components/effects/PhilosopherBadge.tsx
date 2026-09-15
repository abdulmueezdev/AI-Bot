import { motion } from 'framer-motion';

interface PhilosopherBadgeProps {
  name: string;
  imageUrl?: string;
}

export default function PhilosopherBadge({ name, imageUrl }: PhilosopherBadgeProps) {
  return (
    <motion.span 
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-medium text-slate-200 align-middle mx-1"
      whileHover={{ scale: 1.05, backgroundColor: '#1e293b' }}
    >
      {imageUrl ? (
        <img src={imageUrl} alt={name} className="w-4 h-4 rounded-full object-cover" />
      ) : (
        <div className="w-4 h-4 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center text-[8px] uppercase">
          {name.charAt(0)}
        </div>
      )}
      <span>{name}</span>
    </motion.span>
  );
}
