'use client';

import React, { useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import {
  BarChart3,
  TrendingUp,
  MessageSquare,
  Clock,
  Zap,
  Target,
  Brain,
  Calendar,
  Hash,
  Users,
  Activity,
  PieChart,
  LineChart,
  Award,
  Star,
  Timer,
  DollarSign,
  Cpu,
  MemoryStick,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';

export interface ChatMetrics {
  // Basic metrics
  totalMessages: number;
  totalConversations: number;
  averageMessagesPerConversation: number;
  averageResponseTime: number;
  totalTokensUsed: number;

  // Engagement metrics
  userSatisfactionScore: number;
  messageRegenerationRate: number;
  conversationCompletionRate: number;
  bookmarkRate: number;
  shareRate: number;

  // Performance metrics
  fastestResponseTime: number;
  slowestResponseTime: number;
  averageTokensPerMessage: number;
  modelAccuracy: number;

  // Time-based metrics
  messagesByHour: { [hour: number]: number };
  messagesByDay: { [day: string]: number };
  peakActivityHour: number;
  mostActiveDay: string;

  // Model usage
  modelUsage: { [modelId: string]: {
    name: string;
    usage: number;
    avgResponseTime: number;
    satisfactionScore: number;
    tokensUsed: number;
  }};

  // Topics and tags
  topTopics: Array<{
    topic: string;
    count: number;
    sentiment: 'positive' | 'neutral' | 'negative';
  }>;

  // Cost tracking
  estimatedCost: number;
  costPerMessage: number;
  costByModel: { [modelId: string]: number };

  // Errors and issues
  errorRate: number;
  commonErrors: Array<{
    error: string;
    count: number;
  }>;
}

interface ChatAnalyticsProps {
  metrics: ChatMetrics;
  timeframe?: '24h' | '7d' | '30d' | 'all';
  onTimeframeChange?: (timeframe: string) => void;
  showDetailed?: boolean;
  className?: string;
}

export function ChatAnalytics({
  metrics,
  timeframe = '7d',
  onTimeframeChange,
  showDetailed = true,
  className,
}: ChatAnalyticsProps) {
  // Format large numbers
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  // Format time
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Get satisfaction color
  const getSatisfactionColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  // Calculate hourly activity for visualization
  const hourlyActivity = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    count: metrics.messagesByHour[i] || 0,
    percentage: metrics.totalMessages > 0
      ? ((metrics.messagesByHour[i] || 0) / metrics.totalMessages) * 100
      : 0,
  }));

  const MetricCard = ({
    title,
    value,
    subtitle,
    icon,
    trend,
    color = "default",
    tooltip
  }: {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: React.ReactNode;
    trend?: { value: number; direction: 'up' | 'down' };
    color?: 'default' | 'orange' | 'green' | 'blue' | 'red';
    tooltip?: string;
  }) => (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Card className={cn(
            "transition-all hover:shadow-md",
            color === 'orange' && "border-orange-200 bg-orange-50/50",
            color === 'green' && "border-green-200 bg-green-50/50",
            color === 'blue' && "border-blue-200 bg-blue-50/50",
            color === 'red' && "border-red-200 bg-red-50/50"
          )}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "p-2 rounded-lg",
                  color === 'orange' && "bg-orange-100 text-orange-600",
                  color === 'green' && "bg-green-100 text-green-600",
                  color === 'blue' && "bg-blue-100 text-blue-600",
                  color === 'red' && "bg-red-100 text-red-600",
                  color === 'default' && "bg-muted"
                )}>
                  {icon}
                </div>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-2xl font-bold">{value}</p>
                  {subtitle && (
                    <p className="text-xs text-muted-foreground">{subtitle}</p>
                  )}
                </div>
              </div>
              {trend && (
                <div className={cn(
                  "flex items-center gap-1 text-xs",
                  trend.direction === 'up' ? 'text-green-600' : 'text-red-600'
                )}>
                  <TrendingUp className={cn(
                    "w-4 h-4",
                    trend.direction === 'down' && 'rotate-180'
                  )} />
                  {trend.value}%
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </TooltipTrigger>
      {tooltip && (
        <TooltipContent>
          <p className="text-xs">{tooltip}</p>
        </TooltipContent>
      )}
    </Tooltip>
  </TooltipProvider>
  );

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          <h2 className="text-lg font-semibold">Chat Analytics</h2>
        </div>
        {onTimeframeChange && (
          <div className="flex gap-1">
            {['24h', '7d', '30d', 'all'].map((tf) => (
              <Badge
                key={tf}
                variant={timeframe === tf ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => onTimeframeChange(tf)}
              >
                {tf === 'all' ? 'All Time' : tf}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Messages"
          value={formatNumber(metrics.totalMessages)}
          icon={<MessageSquare className="w-5 h-5" />}
          trend={{ value: 12, direction: 'up' }}
          color="orange"
          tooltip="All messages sent and received"
        />
        <MetricCard
          title="Avg Response Time"
          value={formatTime(metrics.averageResponseTime)}
          subtitle={`Fastest: ${formatTime(metrics.fastestResponseTime)}`}
          icon={<Clock className="w-5 h-5" />}
          trend={{ value: 8, direction: 'down' }}
          color="green"
          tooltip="Average time for AI to respond"
        />
        <MetricCard
          title="Satisfaction Score"
          value={`${metrics.userSatisfactionScore}%`}
          icon={<Star className="w-5 h-5" />}
          trend={{ value: 5, direction: 'up' }}
          color="blue"
          tooltip="Based on user feedback and ratings"
        />
        <MetricCard
          title="Tokens Used"
          value={formatNumber(metrics.totalTokensUsed)}
          icon={<Hash className="w-5 h-5" />}
          subtitle={`Avg: ${Math.round(metrics.averageTokensPerMessage)}/msg`}
          color="default"
          tooltip="Total tokens processed by the AI"
        />
      </div>

      {showDetailed && (
        <>
          {/* Activity Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Hourly Activity
              </CardTitle>
              <CardDescription>
                Message distribution throughout the day. Peak: {metrics.peakActivityHour}:00
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {hourlyActivity.map(({ hour, count, percentage }) => (
                  <div key={hour} className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground w-8">
                      {hour.toString().padStart(2, '0')}:00
                    </span>
                    <div className="flex-1">
                      <Progress
                        value={percentage}
                        className={cn(
                          "h-2",
                          hour === metrics.peakActivityHour && "bg-orange-100"
                        )}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-8 text-right">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Model Performance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-5 h-5" />
                Model Performance
              </CardTitle>
              <CardDescription>
                Usage and performance metrics for each AI model
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(metrics.modelUsage).map(([modelId, data]) => (
                  <div key={modelId} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{data.name}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {data.usage} conversations
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTime(data.avgResponseTime)}
                        </span>
                        <span className={cn("flex items-center gap-1", getSatisfactionColor(data.satisfactionScore))}>
                          <Star className="w-3 h-3" />
                          {data.satisfactionScore}%
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span>Usage</span>
                          <span>{((data.usage / metrics.totalConversations) * 100).toFixed(1)}%</span>
                        </div>
                        <Progress value={(data.usage / metrics.totalConversations) * 100} className="h-1" />
                      </div>
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span>Tokens</span>
                          <span>{formatNumber(data.tokensUsed)}</span>
                        </div>
                        <Progress value={(data.tokensUsed / metrics.totalTokensUsed) * 100} className="h-1" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Engagement Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Engagement
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Completion Rate</span>
                  <span className="font-medium">{metrics.conversationCompletionRate}%</span>
                </div>
                <Progress value={metrics.conversationCompletionRate} />

                <div className="flex items-center justify-between">
                  <span className="text-sm">Bookmark Rate</span>
                  <span className="font-medium">{metrics.bookmarkRate}%</span>
                </div>
                <Progress value={metrics.bookmarkRate} />

                <div className="flex items-center justify-between">
                  <span className="text-sm">Share Rate</span>
                  <span className="font-medium">{metrics.shareRate}%</span>
                </div>
                <Progress value={metrics.shareRate} />

                <div className="flex items-center justify-between">
                  <span className="text-sm">Regeneration Rate</span>
                  <span className="font-medium">{metrics.messageRegenerationRate}%</span>
                </div>
                <Progress value={metrics.messageRegenerationRate} className="bg-orange-100" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="w-5 h-5" />
                  Top Topics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-48">
                  <div className="space-y-3">
                    {metrics.topTopics.map((topic, idx) => (
                      <motion.div
                        key={topic.topic}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">#{idx + 1}</span>
                          <span className="text-sm">{topic.topic}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={topic.sentiment === 'positive' ? 'default' :
                                     topic.sentiment === 'negative' ? 'destructive' : 'secondary'}
                            className="text-xs"
                          >
                            {topic.sentiment}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {topic.count} msgs
                          </span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          {/* Cost Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="w-5 h-5" />
                Cost Analysis
              </CardTitle>
              <CardDescription>
                Estimated costs based on token usage
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold text-green-600">${metrics.estimatedCost.toFixed(2)}</p>
                  <p className="text-xs text-muted-foreground">Total Cost</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">${metrics.costPerMessage.toFixed(4)}</p>
                  <p className="text-xs text-muted-foreground">Per Message</p>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <p className="text-2xl font-bold">{formatNumber(Math.round(metrics.totalTokensUsed / metrics.estimatedCost))}</p>
                  <p className="text-xs text-muted-foreground">Tokens per $</p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Cost by Model</p>
                {Object.entries(metrics.costByModel).map(([modelId, cost]) => {
                  const modelData = metrics.modelUsage[modelId];
                  return (
                    <div key={modelId} className="flex items-center justify-between">
                      <span className="text-sm">{modelData?.name || modelId}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-muted rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-orange-400 to-orange-600"
                            style={{ width: `${(cost / metrics.estimatedCost) * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium w-16 text-right">
                          ${cost.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Error Analysis */}
          {metrics.errorRate > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5" />
                  Error Analysis
                </CardTitle>
                <CardDescription>
                  Common issues and their frequency
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Error Rate</span>
                    <Badge variant={metrics.errorRate > 5 ? 'destructive' : 'secondary'}>
                      {metrics.errorRate}%
                    </Badge>
                  </div>
                  {metrics.commonErrors.map((error, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 bg-muted/50 rounded">
                      <span className="text-sm flex-1">{error.error}</span>
                      <Badge variant="outline">{error.count} times</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default ChatAnalytics;