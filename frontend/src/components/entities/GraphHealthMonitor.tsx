/**
 * GraphHealthMonitor Component
 * Monitors and displays the health status of the knowledge graph
 */

import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Database,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { api } from '@/services/api-client';
import toast from 'react-hot-toast';

interface HealthIssue {
  type: 'warning' | 'error' | 'info';
  category: string;
  message: string;
  count?: number;
  action?: string;
}

interface GraphHealthStatus {
  overall_status: 'healthy' | 'degraded' | 'critical';
  health_score: number;
  total_entities: number;
  total_relationships: number;
  issues: HealthIssue[];
  metrics: {
    isolated_entities: number;
    entities_without_confidence: number;
    low_confidence_entities: number;
    orphaned_relationships: number;
    duplicate_relationships: number;
    avg_relationship_strength: number;
    weakly_connected_components: number;
  };
  database_size?: number;
  uptime?: number;
  last_check: string;
}

interface BackendGraphHealthStatus {
  status?: 'healthy' | 'degraded' | 'unhealthy' | 'critical';
  node_count?: number;
  relationship_count?: number;
  database_size?: string | number;
  uptime?: string | number;
}

const toNumber = (value: unknown, fallback: number = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
};

const normalizeHealthStatus = (
  raw: Partial<GraphHealthStatus & BackendGraphHealthStatus>
): GraphHealthStatus => {
  const normalizedStatus = raw.overall_status
    ? raw.overall_status
    : raw.status === 'unhealthy'
      ? 'critical'
      : raw.status === 'critical'
        ? 'critical'
        : raw.status === 'degraded'
          ? 'degraded'
          : 'healthy';

  const totalEntities = toNumber(raw.total_entities, toNumber(raw.node_count, 0));
  const totalRelationships = toNumber(
    raw.total_relationships,
    toNumber(raw.relationship_count, 0)
  );

  return {
    overall_status: normalizedStatus,
    health_score: toNumber(raw.health_score, normalizedStatus === 'healthy' ? 100 : 50),
    total_entities: totalEntities,
    total_relationships: totalRelationships,
    issues: Array.isArray(raw.issues) ? raw.issues : [],
    metrics: {
      isolated_entities: toNumber(raw.metrics?.isolated_entities, 0),
      entities_without_confidence: toNumber(
        raw.metrics?.entities_without_confidence,
        0
      ),
      low_confidence_entities: toNumber(raw.metrics?.low_confidence_entities, 0),
      orphaned_relationships: toNumber(raw.metrics?.orphaned_relationships, 0),
      duplicate_relationships: toNumber(raw.metrics?.duplicate_relationships, 0),
      avg_relationship_strength: toNumber(raw.metrics?.avg_relationship_strength, 0),
      weakly_connected_components: toNumber(
        raw.metrics?.weakly_connected_components,
        0
      ),
    },
    database_size: toNumber(raw.database_size, 0),
    uptime: toNumber(raw.uptime, 0),
    last_check: raw.last_check ?? new Date().toISOString(),
  };
};

export const GraphHealthMonitor: React.FC = () => {
  const [health, setHealth] = useState<GraphHealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchHealth();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchHealth, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const data = await api.get<
        Partial<GraphHealthStatus & BackendGraphHealthStatus>
      >(
        'knowledge-graph/health'
      );
      setHealth(normalizeHealthStatus(data));
    } catch (error) {
      console.error('Error fetching health:', error);
      toast.error('Failed to fetch graph health');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'var(--phosphor-green)';
      case 'degraded':
        return 'var(--amber-gold)';
      case 'critical':
        return '#ff6b6b';
      default:
        return 'var(--terminal-text-dim)';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle2 className="w-6 h-6" />;
      case 'degraded':
        return <AlertTriangle className="w-6 h-6" />;
      case 'critical':
        return <XCircle className="w-6 h-6" />;
      default:
        return <Activity className="w-6 h-6" />;
    }
  };

  const getIssueIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <XCircle className="w-4 h-4 text-[#ff6b6b]" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-[var(--amber-gold)]" />;
      case 'info':
        return <Activity className="w-4 h-4 text-[var(--cyan)]" />;
      default:
        return <Activity className="w-4 h-4" />;
    }
  };

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Activity className="w-8 h-8 text-[var(--phosphor-green)] animate-pulse" />
          <p className="font-mono text-sm text-[var(--terminal-text)]">
            CHECKING_GRAPH_HEALTH...
          </p>
        </div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="font-mono text-sm text-[var(--terminal-text-dim)]">
          No health data available
        </p>
      </div>
    );
  }

  const connectivityScore =
    health.total_entities > 0
      ? Math.max(0, 100 - (health.metrics.isolated_entities / health.total_entities) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-mono font-bold text-[var(--terminal-text)] uppercase tracking-wider">
            Graph Health Monitor
          </h2>
          <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-1">
            Last check: {new Date(health.last_check).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => setAutoRefresh(!autoRefresh)}
            variant="outline"
            size="sm"
            className="font-mono text-xs"
          >
            {autoRefresh ? 'Auto-refresh: ON' : 'Auto-refresh: OFF'}
          </Button>
          <Button
            onClick={fetchHealth}
            disabled={loading}
            variant="outline"
            size="sm"
            className="font-mono text-xs"
          >
            <RefreshCw
              className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`}
            />
            REFRESH
          </Button>
        </div>
      </div>

      {/* Overall Status */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div
                className="p-4 rounded-lg"
                style={{
                  backgroundColor: `${getStatusColor(health.overall_status)}20`,
                }}
              >
                <div style={{ color: getStatusColor(health.overall_status) }}>
                  {getStatusIcon(health.overall_status)}
                </div>
              </div>
              <div>
                <p className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
                  Overall Status
                </p>
                <p
                  className="text-3xl font-mono font-bold uppercase mt-1"
                  style={{ color: getStatusColor(health.overall_status) }}
                >
                  {health.overall_status}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
                Health Score
              </p>
              <p className="text-5xl font-mono font-bold text-[var(--terminal-text)] mt-1">
                {health.health_score}
                <span className="text-2xl text-[var(--terminal-text-dim)]">
                  /100
                </span>
              </p>
              <Progress value={health.health_score} className="w-32 h-2 mt-2" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-4 h-4 text-[var(--phosphor-green)]" />
              <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                TOTAL ENTITIES
              </span>
            </div>
            <p className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
              {health.total_entities.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-4 h-4 text-[var(--cyan)]" />
              <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                RELATIONSHIPS
              </span>
            </div>
            <p className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
              {health.total_relationships.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-[var(--amber-gold)]" />
              <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                ISOLATED
              </span>
            </div>
            <p className="text-2xl font-mono font-bold text-[var(--amber-gold)]">
              {health.metrics.isolated_entities.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-[var(--purple)]" />
              <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                AVG STRENGTH
              </span>
            </div>
            <p className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
              {(health.metrics.avg_relationship_strength * 100).toFixed(0)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Metrics */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)]">
          <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--terminal-text)]">
            Detailed Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Low Confidence Entities
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.low_confidence_entities}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Missing Confidence Scores
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.entities_without_confidence}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Weakly Connected Components
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.weakly_connected_components}
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Orphaned Relationships
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.orphaned_relationships}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Duplicate Relationships
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.duplicate_relationships}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[var(--terminal-bg)]">
                <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                  Isolated Entities
                </span>
                <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                  {health.metrics.isolated_entities}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Issues */}
      {health.issues.length > 0 && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardHeader className="border-b border-[var(--terminal-border)]">
            <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--terminal-text)]">
              Health Issues ({health.issues.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="space-y-2">
              {health.issues.map((issue, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]"
                >
                  {getIssueIcon(issue.type)}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge
                        variant="outline"
                        className="font-mono text-[10px] border-[var(--terminal-border)]"
                      >
                        {issue.category}
                      </Badge>
                      {issue.count && (
                        <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                          ({issue.count})
                        </span>
                      )}
                    </div>
                    <p className="text-xs font-mono text-[var(--terminal-text)]">
                      {issue.message}
                    </p>
                    {issue.action && (
                      <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-1">
                        → {issue.action}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Health Score Breakdown */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)]">
          <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--terminal-text)]">
            Health Score Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="space-y-3">
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[var(--terminal-text)]">
                  Data Quality
                </span>
                <span className="text-[var(--terminal-text-dim)]">
                  {Math.max(
                    0,
                    100 - health.metrics.entities_without_confidence * 2
                  )}
                  %
                </span>
              </div>
              <Progress
                value={Math.max(
                  0,
                  100 - health.metrics.entities_without_confidence * 2
                )}
                className="h-2"
              />
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[var(--terminal-text)]">
                  Connectivity
                </span>
                <span className="text-[var(--terminal-text-dim)]">
                  {connectivityScore.toFixed(0)}
                  %
                </span>
              </div>
              <Progress
                value={connectivityScore}
                className="h-2"
              />
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-[var(--terminal-text)]">
                  Relationship Quality
                </span>
                <span className="text-[var(--terminal-text-dim)]">
                  {(health.metrics.avg_relationship_strength * 100).toFixed(0)}%
                </span>
              </div>
              <Progress
                value={health.metrics.avg_relationship_strength * 100}
                className="h-2"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
