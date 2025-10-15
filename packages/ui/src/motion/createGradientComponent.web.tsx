import { motion } from 'framer-motion';

export type GradientProps = {
  colors: string[];
};

export const GradientComponent = ({ colors }: GradientProps) => (
  <motion.div
    aria-hidden
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 0.7, scale: 1 }}
    transition={{ duration: 1.2, ease: 'easeInOut' }}
    style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      background: `radial-gradient(circle at 20% 20%, ${colors[0]}40, transparent 60%), radial-gradient(circle at 80% 30%, ${colors[1] ?? colors[0]}55, transparent 70%)`,
      filter: 'blur(80px)'
    }}
  />
);
