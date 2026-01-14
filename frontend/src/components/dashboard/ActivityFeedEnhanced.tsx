"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  FileText,
  Upload,
  Search,
  Download,
  Share,
  Clock,
  User,
  Bot,
  Image,
  Video,
  Music,
  Filter,
  MoreVertical,
  CheckCircle,
  AlertCircle,
  Info,
  TrendingUp,
} from "lucide-react";

interface ActivityItem {
  id: string;
  type: "upload" | "search" | "download" | "share" | "analysis";
  title: string;
  description: string;
  timestamp: string;
  user?: {
    name: string;
    avatar?: string;
    email: string;
  };
  metadata?: {
    fileType?: string;
    fileSize?: string;
    duration?: string;
    status?: "success" | "processing" | "failed";
  };
}

const sampleActivities: ActivityItem[] = [
  {
    id: "1",
    type: "upload",
    title: "New document uploaded",
    description: "Q4_Financial_Report_2024.pdf uploaded successfully",
    timestamp: "2 minutes ago",
    user: {
      name: "John Doe",
      email: "john@company.com",
    },
    metadata: {
      fileType: "PDF",
      fileSize: "2.4 MB",
      status: "success",
    },
  },
  {
    id: "2",
    type: "search",
    title: "Search query executed",
    description: "Found 12 results for \"machine learning optimization\"",
    timestamp: "5 minutes ago",
    user: {
      name: "AI Assistant",
      email: "ai@system.com",
    },
    metadata: {
      duration: "0.34s",
      status: "success",
    },
  },
  {
    id: "3",
    type: "analysis",
    title: "Document analysis completed",
    description: "Extracted 45 entities and 8 topics from Product_Demo.mp4",
    timestamp: "10 minutes ago",
    user: {
      name: "AI Assistant",
      email: "ai@system.com",
    },
    metadata: {
      fileType: "Video",
      fileSize: "124 MB",
      status: "success",
    },
  },
  {
    id: "4",
    type: "share",
    title: "Document shared",
    description: "Team_Meeting_Notes.docx shared with 3 team members",
    timestamp: "15 minutes ago",
    user: {
      name: "Sarah Wilson",
      email: "sarah@company.com",
    },
    metadata: {
      fileType: "Document",
      status: "success",
    },
  },
  {
    id: "5",
    type: "download",
    title: "Document downloaded",
    description: "Research_Paper.pdf downloaded by external user",
    timestamp: "20 minutes ago",
    user: {
      name: "External User",
      email: "guest@temp.com",
    },
    metadata: {
      fileType: "PDF",
      status: "success",
    },
  },
];

const activityConfig = {
  upload: {
    icon: Upload,
    color: "text-emerald-500",
    bgColor: "bg-emerald-100",
    borderColor: "border-emerald-200",
  },
  search: {
    icon: Search,
    color: "text-blue-500",
    bgColor: "bg-blue-100",
    borderColor: "border-blue-200",
  },
  download: {
    icon: Download,
    color: "text-purple-500",
    bgColor: "bg-purple-100",
    borderColor: "border-purple-200",
  },
  share: {
    icon: Share,
    color: "text-amber-500",
    bgColor: "bg-amber-100",
    borderColor: "border-amber-200",
  },
  analysis: {
    icon: Bot,
    color: "text-indigo-500",
    bgColor: "bg-indigo-100",
    borderColor: "border-indigo-200",
  },
};

interface ActivityFeedEnhancedProps {
  className?: string;
}

export function ActivityFeedEnhanced({ className }: ActivityFeedEnhancedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>(sampleActivities);
  const [filter, setFilter] = useState<string | null>(null);
  const [hoveredActivity, setHoveredActivity] = useState<string | null>(null);

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      const newActivity: ActivityItem = {
        id: Date.now().toString(),
        type: ["upload", "search", "analysis"][Math.floor(Math.random() * 3)] as ActivityItem["type"],
        title: "New activity detected",
        description: "System processing new request",
        timestamp: "Just now",
        user: {
          name: "System",
          email: "system@auto.com",
        },
        metadata: {
          status: "processing",
        },
      };

      setActivities((prev) => [newActivity, ...prev.slice(0, 9)]);
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  const getFileIcon = (fileType?: string) => {
    switch (fileType?.toLowerCase()) {
      case "pdf":
      case "document":
        return <FileText className="h-3 w-3" />;
      case "image":
        return <Image className="h-3 w-3" />;
      case "video":
        return <Video className="h-3 w-3" />;
      case "audio":
        return <Music className="h-3 w-3" />;
      default:
        return <FileText className="h-3 w-3" />;
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-3 w-3 text-[var(--phosphor-green)]" />;
      case "processing":
        return <div className="h-3 w-3 rounded-full border-2 border-[var(--phosphor-green)] border-t-transparent animate-spin" />;
      case "failed":
        return <AlertCircle className="h-3 w-3 text-red-500" />;
      default:
        return <Info className="h-3 w-3 text-[var(--terminal-text-dim)]" />;
    }
  };

  const filteredActivities = filter
    ? activities.filter((a) => a.type === filter)
    : activities;

  return (
    <motion.div
      className={cn(
        "relative overflow-hidden rounded-xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] shadow-xl",
        className
      )}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Background decoration */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="activity-pattern" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#activity-pattern)" />
        </svg>
      </div>

      {/* Header */}
      <motion.div
        className="relative border-b border-[var(--terminal-border)] p-5"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
              <Clock className="h-4 w-4 text-[var(--terminal-text-dim)]" />
            </div>
            <div>
              <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)] uppercase tracking-wider">Neural Activity</h3>
              <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase">Real-time system events</p>
            </div>
          </div>
        </div>

        {/* Filter buttons */}
        <div className="flex gap-2 overflow-x-auto pb-1 terminal-scrollbar">
          <button
            onClick={() => setFilter(null)}
            className={cn(
              "px-3 py-1 rounded-full text-[10px] font-mono transition-all border",
              !filter
                ? "bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)] border-[var(--phosphor-green)]/30"
                : "bg-[var(--terminal-bg)] text-[var(--terminal-text-dim)] border-[var(--terminal-border)] hover:text-[var(--terminal-text)]"
            )}
          >
            ALL_STREAMS
          </button>
          {Object.entries(activityConfig).map(([key, config]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={cn(
                "px-3 py-1 rounded-full text-[10px] font-mono transition-all border flex items-center gap-1.5",
                filter === key
                  ? "bg-white/10 text-white border-white/30"
                  : "bg-[var(--terminal-bg)] text-[var(--terminal-text-dim)] border-[var(--terminal-border)] hover:text-[var(--terminal-text)]"
              )}
            >
              {key.toUpperCase()}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Activity List */}
      <div className="relative p-5 max-h-[500px] overflow-y-auto terminal-scrollbar">
        <AnimatePresence mode="popLayout">
          {filteredActivities.map((activity, index) => {
            const config = activityConfig[activity.type];
            const Icon = config.icon;
            const isHovered = hoveredActivity === activity.id;

            return (
              <motion.div
                key={activity.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: index * 0.03 }}
                className="relative flex items-start gap-4 mb-4 last:mb-0"
                onHoverStart={() => setHoveredActivity(activity.id)}
                onHoverEnd={() => setHoveredActivity(null)}
              >
                {/* Visual link */}
                <div className={cn(
                  "w-1 h-10 rounded-full mt-1 shrink-0 transition-all duration-300",
                  isHovered ? "opacity-100 h-12" : "opacity-30",
                  activity.type === 'upload' && 'bg-[var(--phosphor-green)]',
                  activity.type === 'search' && 'bg-blue-400',
                  activity.type === 'share' && 'bg-[var(--amber-gold)]',
                  activity.type === 'analysis' && 'bg-purple-400',
                  activity.type === 'download' && 'bg-cyan-400'
                )} />

                {/* Activity content */}
                <div className={cn(
                  "flex-1 min-w-0 bg-[var(--terminal-bg)]/40 rounded-lg p-3 border transition-all duration-300",
                  isHovered ? "border-[var(--terminal-border-glow)] bg-[var(--terminal-bg)]/60" : "border-[var(--terminal-border)]"
                )}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-[11px] font-mono font-bold text-[var(--terminal-text)]">
                          {activity.title.toUpperCase()}
                        </p>
                        {activity.metadata?.status && (
                          getStatusIcon(activity.metadata.status)
                        )}
                      </div>
                      <p className="text-xs font-mono text-[var(--terminal-text-muted)] mb-3 leading-relaxed">
                        {activity.description}
                      </p>

                      {/* User info and metadata */}
                      <div className="flex items-center gap-3 text-[9px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-tighter">
                        <div className="flex items-center gap-1.5">
                          <div className="h-4 w-4 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] flex items-center justify-center">
                            {activity.user?.email.includes("ai") ? (
                              <Bot className="h-2.5 w-2.5 text-[var(--phosphor-green)]" />
                            ) : (
                              <User className="h-2.5 w-2.5" />
                            )}
                          </div>
                          <span className="font-bold">{activity.user?.name}</span>
                        </div>

                        {activity.metadata?.fileType && (
                          <div className="flex items-center gap-1">
                            <span>{activity.metadata.fileType}</span>
                            {activity.metadata.fileSize && (
                              <span>• {activity.metadata.fileSize}</span>
                            )}
                          </div>
                        )}

                        <span>• {activity.timestamp}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Empty state */}
        {filteredActivities.length === 0 && (
          <div className="text-center py-12">
            <Clock className="h-8 w-8 mx-auto mb-3 text-[var(--terminal-border)]" />
            <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase">No data streams detected</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--terminal-border)] p-3 bg-[var(--terminal-bg)]/50">
        <div className="flex items-center justify-between text-[9px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-3 w-3 text-[var(--phosphor-green)]" />
            <span>{activities.length} session logs</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Live Node</span>
            <div className="w-1 h-1 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}