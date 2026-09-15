import { motion } from 'framer-motion';

interface TimelineEvent {
  year: string;
  title: string;
  description: string;
}

interface ConflictTimelineProps {
  events: TimelineEvent[];
}

export default function ConflictTimeline({ events }: ConflictTimelineProps) {
  return (
    <div className="my-6 border-l-2 border-slate-700 ml-3 pl-6 space-y-6 relative">
      {events.map((event, index) => (
        <motion.div 
          key={index} 
          className="relative"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.15 }}
        >
          <div className="absolute -left-[31px] top-1.5 w-3 h-3 rounded-full bg-red-500 ring-4 ring-slate-950" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold text-red-400 font-mono tracking-wider">{event.year}</span>
            <h4 className="text-sm font-semibold text-slate-200">{event.title}</h4>
            <p className="text-sm text-slate-400 leading-relaxed">{event.description}</p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
