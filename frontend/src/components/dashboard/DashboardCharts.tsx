'use client';

import { motion } from 'framer-motion';
import {
  Activity,
  FileText,
  Image as ImageIcon,
  Music,
  Video,
} from 'lucide-react';
import React from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { THEME } from '../../theme/constants';

interface UploadTrendsProps {
  data: Array<{ date: string; uploads: number }>;
}

export const UploadTrendsChart: React.FC<UploadTrendsProps> = ({ data }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="h-full"
    >
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4" style={{ color: THEME.colors.accent }} />
        <span
          className="text-sm font-medium"
          style={{ color: THEME.colors.textMuted }}
        >
          Upload Trends
        </span>
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 5, right: 0, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorUploads" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor={THEME.colors.accent}
                stopOpacity={0.3}
              />
              <stop
                offset="95%"
                stopColor={THEME.colors.accent}
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={THEME.colors.surfaceHover}
          />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: THEME.colors.textMuted }}
            axisLine={{ stroke: THEME.colors.surfaceHover }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: THEME.colors.textMuted }}
            axisLine={{ stroke: THEME.colors.surfaceHover }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: THEME.colors.surface,
              border: `1px solid ${THEME.colors.primaryMuted}`,
              borderRadius: THEME.radius.md,
              fontSize: '12px',
              color: THEME.colors.text,
            }}
          />
          <Area
            type="monotone"
            dataKey="uploads"
            stroke={THEME.colors.accent}
            strokeWidth={2}
            fill="url(#colorUploads)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
};

interface DocumentTypeDistributionProps {
  data: Array<{ type: string; count: number; color: string }>;
}

export const DocumentTypeDistribution: React.FC<
  DocumentTypeDistributionProps
> = ({ data }) => {
  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'PDF':
      case 'Text':
        return <FileText className="h-3 w-3" />;
      case 'Image':
        return <ImageIcon className="h-3 w-3" />;
      case 'Video':
        return <Video className="h-3 w-3" />;
      case 'Audio':
        return <Music className="h-3 w-3" />;
      default:
        return <FileText className="h-3 w-3" />;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="h-full"
    >
      <div
        className="text-sm font-medium mb-3"
        style={{ color: THEME.colors.textMuted }}
      >
        Document Types
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={30}
            outerRadius={50}
            paddingAngle={2}
            dataKey="count"
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: THEME.colors.surface,
              border: `1px solid ${THEME.colors.primaryMuted}`,
              borderRadius: THEME.radius.md,
              fontSize: '12px',
              color: THEME.colors.text,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="mt-3 space-y-1">
        {data.map((item, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-xs"
          >
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <div
                className="flex items-center gap-1"
                style={{ color: THEME.colors.textSubtle }}
              >
                {getTypeIcon(item.type)}
                <span>{item.type}</span>
              </div>
            </div>
            <span
              className="font-medium"
              style={{ color: THEME.colors.textMuted }}
            >
              {item.count}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

interface SearchActivityProps {
  data: Array<{ time: string; searches: number }>;
}

export const SearchActivitySparkline: React.FC<SearchActivityProps> = ({
  data,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="h-full"
    >
      <div className="text-sm font-medium text-foreground mb-2">
        Search Activity
      </div>
      <ResponsiveContainer width="100%" height={60}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 0, left: 0, bottom: 0 }}
        >
          <Line
            type="monotone"
            dataKey="searches"
            stroke={THEME.colors.warning}
            strokeWidth={2}
            dot={false}
            activeDot={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex justify-between text-xs text-muted-foreground mt-1">
        <span>24h ago</span>
        <span className="font-medium text-foreground">
          +{data[data.length - 1]?.searches || 0} searches
        </span>
      </div>
    </motion.div>
  );
};
