"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  BarChart3,
  Clock,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  AlertCircle,
} from "lucide-react";

interface StatItem {
  id: string;
  title: string;
  value: string;
  change: number;
  changeType: "increase" | "decrease" | "neutral";
  icon: React.ReactNode;
  iconBg: string;
  trend: number[];
  description?: string;
}

export const StatsCardEnhanced: React.FC<{ stat: StatItem; index: number }> = ({
  stat,
  index,
}) => {
  const [currentTrendIndex, setCurrentTrendIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTrendIndex((prev) => (prev + 1) % stat.trend.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [stat.trend.length]);

  const containerVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.5,
        delay: index * 0.1,
        type: "spring",
        stiffness: 100,
      },
    },
    hover: {
      scale: 1.02,
      transition: { duration: 0.2 },
    },
  };

  const backgroundVariants = {
    rest: {
      background: "linear-gradient(135deg, rgba(251, 191, 36, 0.05) 0%, rgba(251, 146, 60, 0.05) 100%)",
    },
    hover: {
      background: "linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(251, 146, 60, 0.1) 100%)",
    },
  };

  const getTrendColor = () => {
    if (stat.changeType === "increase") return "from-emerald-400 to-green-600";
    if (stat.changeType === "decrease") return "from-rose-400 to-red-600";
    return "from-gray-400 to-gray-600";
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      whileHover="hover"
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className="relative group overflow-hidden rounded-2xl bg-white/70 backdrop-blur-xl border border-amber-200/20 shadow-lg hover:shadow-2xl transition-all duration-500"
    >
      {/* Animated gradient background */}
      <motion.div
        variants={backgroundVariants}
        initial="rest"
        animate={isHovered ? "hover" : "rest"}
        className="absolute inset-0 transition-all duration-500"
      />

      {/* Decorative pattern overlay */}
      <div className="absolute inset-0 opacity-5">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id={`grid-${index}`} width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill={`url(#grid-${index})`} />
        </svg>
      </div>

      {/* Floating particles */}
      <motion.div
        className="absolute top-2 right-2 w-2 h-2 bg-amber-400/30 rounded-full"
        animate={{
          y: [0, -5, 0],
          opacity: [0.3, 0.8, 0.3],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute bottom-4 right-4 w-1 h-1 bg-orange-400/30 rounded-full"
        animate={{
          y: [0, -3, 0],
          opacity: [0.3, 0.7, 0.3],
        }}
        transition={{
          duration: 2.5,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 0.5,
        }}
      />

      <div className="relative p-6">
        <div className="flex items-start justify-between mb-4">
          <motion.div
            animate={{
              rotate: isHovered ? [0, -5, 5, 0] : 0,
              scale: isHovered ? 1.1 : 1,
            }}
            transition={{
              duration: 0.5,
              ease: "easeInOut",
            }}
            className={`p-3 rounded-xl ${stat.iconBg} shadow-lg group-hover:shadow-xl transition-all duration-300`}
          >
            {stat.icon}
          </motion.div>

          {/* Animated trend sparkline */}
          <div className="flex items-end space-x-0.5 h-8">
            {stat.trend.map((value, idx) => (
              <motion.div
                key={idx}
                className={`w-1 rounded-full transition-all duration-300 ${
                  idx === currentTrendIndex
                    ? "bg-gradient-to-t from-amber-500 to-orange-400"
                    : "bg-amber-200"
                }`}
                animate={{
                  height: `${16 + (value / 100) * 16}px`,
                }}
                transition={{
                  duration: 0.5,
                  delay: idx * 0.05,
                }}
              />
            ))}
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 + index * 0.1 }}
          className="space-y-2"
        >
          <p className="text-sm font-medium text-gray-600">{stat.title}</p>
          <motion.div
            className="flex items-baseline gap-2"
            initial={{ x: -20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{
              type: "spring",
              stiffness: 200,
              delay: 0.3 + index * 0.1,
            }}
          >
            <p className="text-3xl font-bold text-gray-900 tabular-nums">
              {stat.value}
            </p>
            {Math.abs(stat.change) > 0 && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.5 + index * 0.1 }}
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                  stat.changeType === "increase"
                    ? "bg-emerald-100 text-emerald-700"
                    : stat.changeType === "decrease"
                    ? "bg-red-100 text-red-700"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {stat.changeType === "increase" ? (
                  <TrendingUp className="h-3 w-3 mr-0.5" />
                ) : stat.changeType === "decrease" ? (
                  <TrendingDown className="h-3 w-3 mr-0.5" />
                ) : (
                  <Activity className="h-3 w-3 mr-0.5" />
                )}
                {Math.abs(stat.change)}%
              </motion.div>
            )}
          </motion.div>

          {stat.description && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 + index * 0.1 }}
              className="text-xs text-gray-500"
            >
              {stat.description}
            </motion.p>
          )}
        </motion.div>

        {/* Performance indicator */}
        {Math.abs(stat.change) > 20 && (
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.7 + index * 0.1 }}
            className="absolute top-2 left-2"
          >
            <div className={`p-1.5 rounded-lg bg-gradient-to-br ${getTrendColor()} shadow-lg`}>
              <Zap className="h-3 w-3 text-white" />
            </div>
          </motion.div>
        )}

        {/* Animated accent line */}
        <motion.div
          className="absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-amber-400 to-orange-400"
          initial={{ width: 0 }}
          animate={{ width: isHovered ? "100%" : "30%" }}
          transition={{
            duration: 0.5,
            delay: 0.5 + index * 0.1,
            ease: "easeInOut",
          }}
        />
      </div>
    </motion.div>
  );
};