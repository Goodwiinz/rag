'use client';

import { cn } from '@/lib/utils';
import { LucideIcon, Minus, TrendingDown, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

interface StatsCardProps {
  title: string;
  value: number;
  suffix?: string;
  prefix?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon: LucideIcon;
  iconColor?: string;
  delay?: number;
}

export function StatsCard({
  title,
  value,
  suffix = '',
  prefix = '',
  trend = 'neutral',
  trendValue,
  icon: Icon,
  iconColor = 'text-amber-500',
  delay = 0,
}: StatsCardProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  // Motion values for interactive effects
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const rotateX = useTransform(mouseY, [-100, 100], [5, -5]);
  const rotateY = useTransform(mouseX, [-100, 100], [-5, 5]);
  const scale = useSpring(1, { stiffness: 300, damping: 20 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    mouseX.set(x);
    mouseY.set(y);
  };

  const handleMouseEnter = () => scale.set(1.05);
  const handleMouseLeave = () => {
    scale.set(1);
    mouseX.set(0);
    mouseY.set(0);
  };

  // Staggered entrance animation
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  // Count-up animation
  useEffect(() => {
    if (!isVisible) return;

    const duration = 1200;
    const steps = 40;
    const stepDuration = duration / steps;
    const increment = value / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      // Ease-out curve
      const progress = step / steps;
      const easeOut = 1 - Math.pow(1 - progress, 3);
      current = Math.round(value * easeOut);
      setDisplayValue(current);

      if (step >= steps) {
        setDisplayValue(value);
        clearInterval(timer);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [value, isVisible]);

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColors = {
    up: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    down: 'text-rose-500 bg-rose-500/10 border-rose-500/20',
    neutral: 'text-muted-foreground bg-muted/50 border-border',
  };

  return (
    <motion.div
      className="relative perspective-1000"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 30 }}
      transition={{
        duration: 0.6,
        delay: delay / 1000,
        type: "spring",
        stiffness: 100,
        damping: 10
      }}
      style={{ rotateX, rotateY, scale }}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className={cn(
          'relative overflow-hidden rounded-2xl border border-border/50',
          'bg-gradient-to-br from-card/60 via-card/40 to-card/20 backdrop-blur-sm',
          'transition-all duration-500 ease-out',
          'hover:border-amber-500/40 hover:shadow-2xl hover:shadow-amber-500/10',
          'group cursor-pointer'
        )}
      >
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-amber-500/0 via-transparent to-orange-500/0 group-hover:from-amber-500/10 group-hover:to-orange-500/5 transition-all duration-700" />

        {/* Glass reflection effect */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

        {/* Floating particles on hover */}
        <div className="absolute inset-0 overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-1000">
          {[...Array(6)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 bg-amber-500/30 rounded-full"
              animate={{
                y: [0, -50, 0],
                x: [0, Math.random() * 40 - 20, 0],
                opacity: [0, 1, 0],
              }}
              transition={{
                duration: 3 + Math.random() * 2,
                repeat: Infinity,
                delay: Math.random() * 2,
                ease: "easeInOut",
              }}
              style={{
                left: `${20 + Math.random() * 60}%`,
                top: `${20 + Math.random() * 60}%`,
              }}
            />
          ))}
        </div>

        <div className="relative p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <motion.p
                className="text-xs font-medium text-muted-foreground tracking-wider uppercase"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                {title}
              </motion.p>
              <motion.div
                className="mt-2 flex items-baseline gap-1"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
              >
                <span className="text-4xl font-bold tracking-tight text-foreground bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
                  {prefix}
                  {displayValue.toLocaleString()}
                  {suffix}
                </span>
              </motion.div>
            </div>

            <motion.div
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/10 to-orange-500/10 group-hover:from-amber-500/20 group-hover:to-orange-500/20 transition-all duration-300"
              whileHover={{
                scale: 1.1,
                rotate: [0, -5, 5, 0],
              }}
              transition={{ duration: 0.3 }}
            >
              <motion.div
                animate={{
                  rotate: [0, 360]
                }}
                transition={{
                  duration: 20,
                  repeat: Infinity,
                  ease: "linear",
                  repeatDelay: 5
                }}
              >
                <Icon className={cn('h-7 w-7', iconColor)} />
              </motion.div>
            </motion.div>
          </div>

          {trendValue && (
            <motion.div
              className="flex items-center justify-between"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <div className="flex items-center gap-2">
                <motion.span
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border',
                    trendColors[trend]
                  )}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <motion.div
                    animate={{
                      rotate: trend === 'up' ? [0, -10, 0] : trend === 'down' ? [0, 10, 0] : 0,
                    }}
                    transition={{ duration: 2, repeat: Infinity, repeatDelay: 2 }}
                  >
                    <TrendIcon className="h-3 w-3" />
                  </motion.div>
                  {trendValue}
                </motion.span>
                <span className="text-xs text-muted-foreground">vs last week</span>
              </div>

              {/* Animated sparkles for positive trends */}
              {trend === 'up' && (
                <motion.div className="flex gap-1">
                  {[...Array(3)].map((_, i) => (
                    <motion.div
                      key={i}
                      className="w-1 h-1 bg-emerald-500 rounded-full"
                      animate={{
                        scale: [1, 1.5, 1],
                        opacity: [1, 0.5, 1],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        delay: i * 0.2,
                      }}
                    />
                  ))}
                </motion.div>
              )}
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
