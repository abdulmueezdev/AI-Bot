import { motion } from 'framer-motion';

interface DialecticSparkProps {
  isActive?: boolean;
}

export default function DialecticSpark({ isActive = true }: DialecticSparkProps) {
  if (!isActive) return null;

  return (
    <motion.div
      className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-gradient-to-tr from-red-500 to-blue-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
      animate={{
        scale: [1, 1.2, 1],
        opacity: [0.7, 1, 0.7],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  );
}
