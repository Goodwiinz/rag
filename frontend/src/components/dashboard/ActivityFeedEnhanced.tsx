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
        return <CheckCircle className="h-3 w-3 text-emerald-500" />;
      case "processing":
        return <div className="h-3 w-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />;
      case "failed":
        return <AlertCircle className="h-3 w-3 text-red-500" />;
      default:
        return <Info className="h-3 w-3 text-gray-400" />;
    }
  };

  const filteredActivities = filter
    ? activities.filter((a) => a.type === filter)
    : activities;

  return (
    <motion.div
      className={cn(
        "relative overflow-hidden rounded-2xl bg-white/70 backdrop-blur-xl border border-amber-200/20 shadow-lg",
        className
      )}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Background decoration */}
      <div className="absolute inset-0 opacity-5">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="activity-pattern" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
              <circle cx="15" cy="15" r="1" fill="#f59e0b" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#activity-pattern)" />
        </svg>
      </div>

      {/* Header */}
      <motion.div
        className="relative border-b border-amber-200/20 p-6"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-amber-400/20 to-orange-500/20">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-800">Activity Feed</h3>
              <p className="text-sm text-gray-600">Real-time system activity</p>
            </div>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-2 rounded-lg hover:bg-gray-100/50 transition-colors"
          >
            <MoreVertical className="h-4 w-4 text-gray-400" />
          </motion.button>
        </div>

        {/* Filter buttons */}
        <div className="flex gap-2 overflow-x-auto pb-2">
          <motion.button
            onClick={() => setFilter(null)}
            className={cn(
              "px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all",
              !filter
                ? "bg-amber-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            All Activities
          </motion.button>
          {Object.entries(activityConfig).map(([key, config]) => (
            <motion.button
              key={key}
              onClick={() => setFilter(key)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1",
                filter === key
                  ? `${config.bgColor} ${config.color}`
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <config.icon className="h-3 w-3" />
              {key.charAt(0).toUpperCase() + key.slice(1)}
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* Activity List with Timeline */}
      <div className="relative p-6 max-h-[600px] overflow-y-auto">
        {/* Timeline line */}
        <div className="absolute left-10 top-0 bottom-0 w-0.5 bg-gradient-to-b from-amber-400 to-orange-400" />

        <AnimatePresence mode="popLayout">
          {filteredActivities.map((activity, index) => {
            const config = activityConfig[activity.type];
            const Icon = config.icon;
            const isHovered = hoveredActivity === activity.id;

            return (
              <motion.div
                key={activity.id}
                initial={{ opacity: 0, x: -50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 50 }}
                transition={{ delay: index * 0.05 }}
                className="relative flex items-start gap-4 mb-6 last:mb-0"
                onHoverStart={() => setHoveredActivity(activity.id)}
                onHoverEnd={() => setHoveredActivity(null)}
              >
                {/* Timeline dot */}
                <motion.div
                  className={cn(
                    "relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 bg-white shadow-lg",
                    config.borderColor
                  )}
                  whileHover={{ scale: 1.2 }}
                  transition={{ duration: 0.2 }}
                >
                  <motion.div
                    animate={{
                      rotate: isHovered ? [0, -10, 10, 0] : 0,
                    }}
                    transition={{ duration: 0.5 }}
                  >
                    <Icon className={cn("h-5 w-5", config.color)} />
                  </motion.div>
                </motion.div>

                {/* Activity content */}
                <motion.div
                  className="flex-1 min-w-0 bg-white/50 rounded-xl p-4 border border-gray-200/30 hover:shadow-lg transition-all duration-300"
                  whileHover={{ scale: 1.02, x: 5 }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-semibold text-gray-800">
                          {activity.title}
                        </p>
                        {activity.metadata?.status && (
                          getStatusIcon(activity.metadata.status)
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        {activity.description}
                      </p>

                      {/* User info and metadata */}
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        <div className="flex items-center gap-1.5">
                          {activity.user?.avatar ? (
                            <img
                              src={activity.user.avatar}
                              alt={activity.user.name}
                              className="h-5 w-5 rounded-full"
                            />
                          ) : (
                            <div className={cn(
                              "h-5 w-5 rounded-full flex items-center justify-center",
                              activity.user?.email.includes("ai") ? "bg-indigo-100" : "bg-gray-200"
                            )}>
                              {activity.user?.email.includes("ai") ? (
                                <Bot className="h-3 w-3 text-indigo-600" />
                              ) : (
                                <User className="h-3 w-3 text-gray-600" />
                              )}
                            </div>
                          )}
                          <span className="font-medium">{activity.user?.name}</span>
                        </div>

                        {activity.metadata?.fileType && (
                          <div className="flex items-center gap-1">
                            {getFileIcon(activity.metadata.fileType)}
                            <span>{activity.metadata.fileType}</span>
                            {activity.metadata.fileSize && (
                              <span>• {activity.metadata.fileSize}</span>
                            )}
                          </div>
                        )}

                        {activity.metadata?.duration && (
                          <span>• {activity.metadata.duration}</span>
                        )}

                        <span>• {activity.timestamp}</span>
                      </div>
                    </div>

                    {/* Quick action button */}
                    <AnimatePresence>
                      {isHovered && (
                        <motion.button
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.8 }}
                          className="p-1.5 rounded-lg hover:bg-gray-100/50 transition-colors ml-2"
                        >
                          <MoreVertical className="h-4 w-4 text-gray-400" />
                        </motion.button>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>

                {/* New activity indicator */}
                {activity.timestamp === "Just now" && (
                  <motion.div
                    className="absolute -right-2 top-2"
                    initial={{ scale: 0 }}
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1, repeat: 3 }}
                  >
                    <div className="h-2 w-2 bg-emerald-500 rounded-full" />
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Empty state */}
        {filteredActivities.length === 0 && (
          <motion.div
            className="text-center py-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="text-gray-400 mb-2">
              <Clock className="h-12 w-12 mx-auto" />
            </div>
            <p className="text-gray-500">No activities found</p>
            <p className="text-sm text-gray-400 mt-1">
              Try selecting a different filter
            </p>
          </motion.div>
        )}
      </div>

      {/* Footer with stats */}
      <motion.div
        className="border-t border-amber-200/20 p-4 bg-gradient-to-r from-amber-50/30 to-orange-50/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <div className="flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-3 w-3 text-amber-500" />
            <span>{activities.length} activities today</span>
          </div>
          <div className="flex items-center gap-4">
            <span>12 active users</span>
            <span>•</span>
            <span>98.5% uptime</span>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}