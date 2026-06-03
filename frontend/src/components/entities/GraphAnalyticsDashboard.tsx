/**
 * GraphAnalyticsDashboard Component
 * Displays comprehensive analytics about the knowledge graph
 */

import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  Network, 
  Database,
  Activity,
  Loader2,
  RefreshCw 
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { entityService } from '@/services/entityService';
import { EntityType } from '@/types/entity';
import toast from 'react-hot-toast';

interface EntityTypeDistribution {
  entity_type: string;
  count: number;
}

interface RelationshipTypeDistribution {
  relationship_type: string;
  count: number;
}

interface CentralityMetric {
  entity_id: string;
  entity_name: string;
  score: number;
}

interface GraphAnalytics {
  total_entities: number;
  total_relationships: number;
  entity_type_distribution: EntityTypeDistribution[];
  relationship_type_distribution: RelationshipTypeDistribution[];
  average_degree: number;
  graph_density: number | null;
  top_entities_by_degree: CentralityMetric[];
  isolated_entities_count: number;
  avg_confidence_score: number | null;
  timestamp: string;
}

interface GraphAnalyticsDashboardProps {
  onTypeClick?: (entityType: EntityType) => void;
}

export const GraphAnalyticsDashboard: React.FC<GraphAnalyticsDashboardProps> = ({ onTypeClick }) => {
  const [analytics, setAnalytics] = useState<GraphAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const data = await entityService.getAnalytics();
      
      // Convert backend format to component format
      const formattedData: GraphAnalytics = {
        total_entities: data.total_entities,
        total_relationships: data.total_relationships,
        entity_type_distribution: Object.entries(data.entity_type_counts || {}).map(
          ([entity_type, count]) => ({ entity_type, count: count as number })
        ),
        relationship_type_distribution: Object.entries(data.relationship_type_counts || {}).map(
          ([relationship_type, count]) => ({ relationship_type, count: count as number })
        ),
        average_degree: data.average_connections || 0,
        graph_density: null, // Not available from backend yet
        top_entities_by_degree: [],
        isolated_entities_count: data.orphan_entities || 0,
        avg_confidence_score: null, // Not available from backend yet
        timestamp: new Date().toISOString(),
      };
      
      setAnalytics(formattedData);
    } catch (error) {
      console.error('Error fetching analytics:', error);
      toast.error('Failed to fetch graph analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-[var(--nous-sol)] animate-spin" />
          <p className="font-mono text-sm text-[var(--nous-fg-1)]">
            COMPUTING_ANALYTICS...
          </p>
        </div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="font-mono text-sm text-[var(--nous-fg-3)]">
          No analytics data available
        </p>
      </div>
    );
  }

  const topEntityTypes = analytics.entity_type_distribution
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  const topRelationshipTypes = analytics.relationship_type_distribution
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-wider">
            Graph Analytics Dashboard
          </h2>
          <p className="text-xs font-mono text-[var(--nous-fg-3)] mt-1">
            Last updated: {new Date(analytics.timestamp).toLocaleString()}
          </p>
        </div>
        <Button
          onClick={fetchAnalytics}
          disabled={loading}
          variant="outline"
          size="sm"
          className="font-mono text-xs"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          REFRESH
        </Button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)] flex items-center gap-2">
              <Database className="w-4 h-4 text-[var(--nous-sol)]" />
              TOTAL ENTITIES
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-mono font-bold text-[var(--nous-sol)]">
              {analytics.total_entities.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)] flex items-center gap-2">
              <Network className="w-4 h-4 text-[var(--nous-helios)]" />
              RELATIONSHIPS
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-mono font-bold text-[var(--nous-helios)]">
              {analytics.total_relationships.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)] flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[var(--nous-helios)]" />
              AVG DEGREE
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-mono font-bold text-[var(--nous-helios)]">
              {analytics.average_degree.toFixed(2)}
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)] flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--purple)]" />
              GRAPH DENSITY
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-mono font-bold text-[var(--purple)]">
              {analytics.graph_density !== null 
                ? `${(analytics.graph_density * 100).toFixed(2)}%`
                : 'N/A'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)]">
              ISOLATED ENTITIES
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-mono font-bold text-[var(--nous-fg-1)]">
              {analytics.isolated_entities_count.toLocaleString()}
            </p>
            <p className="text-xs font-mono text-[var(--nous-fg-3)] mt-1">
              Entities with no relationships
            </p>
          </CardContent>
        </Card>

        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-mono text-[var(--nous-fg-3)]">
              AVG CONFIDENCE
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-mono font-bold text-[var(--nous-fg-1)]">
              {analytics.avg_confidence_score !== null
                ? `${(analytics.avg_confidence_score * 100).toFixed(1)}%`
                : 'N/A'}
            </p>
            <p className="text-xs font-mono text-[var(--nous-fg-3)] mt-1">
              Average entity confidence score
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Entity Type Distribution */}
      <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
        <CardHeader className="border-b border-[var(--nous-border-1)]">
          <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--nous-fg-1)] flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Entity Type Distribution
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="space-y-3">
            {topEntityTypes.map((item) => {
              const percentage = (item.count / analytics.total_entities) * 100;
              return (
                <button
                  key={item.entity_type}
                  onClick={() => onTypeClick?.(item.entity_type as EntityType)}
                  className="w-full space-y-1 text-left hover:bg-[var(--nous-bg-3)] p-2 rounded-md transition-colors cursor-pointer"
                  title={`Click to filter by ${item.entity_type}`}
                >
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-[var(--nous-fg-1)] font-medium">{item.entity_type}</span>
                    <span className="text-[var(--nous-fg-3)]">
                      {item.count.toLocaleString()} ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-2 bg-[var(--nous-bg-1)] rounded-full overflow-hidden border border-[var(--nous-border-1)]">
                    <div
                      className="h-full bg-[var(--nous-sol)] rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Relationship Type Distribution */}
      <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
        <CardHeader className="border-b border-[var(--nous-border-1)]">
          <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--nous-fg-1)] flex items-center gap-2">
            <PieChart className="w-4 h-4" />
            Relationship Type Distribution
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="space-y-3">
            {topRelationshipTypes.map((item) => {
              const percentage = (item.count / analytics.total_relationships) * 100;
              return (
                <div key={item.relationship_type} className="space-y-1">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-[var(--nous-fg-1)]">{item.relationship_type}</span>
                    <span className="text-[var(--nous-fg-3)]">
                      {item.count.toLocaleString()} ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-2 bg-[var(--nous-bg-1)] rounded-full overflow-hidden border border-[var(--nous-border-1)]">
                    <div
                      className="h-full bg-[var(--nous-helios)] rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Top Entities by Degree */}
      <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg">
        <CardHeader className="border-b border-[var(--nous-border-1)]">
          <CardTitle className="text-sm font-mono font-bold uppercase tracking-wider text-[var(--nous-fg-1)] flex items-center gap-2">
            <Network className="w-4 h-4" />
            Most Connected Entities
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="space-y-2">
            {analytics.top_entities_by_degree.map((item, index) => (
              <div
                key={item.entity_id}
                className="flex items-center justify-between p-2 rounded-md bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono font-bold text-[var(--nous-fg-3)] w-6">
                    #{index + 1}
                  </span>
                  <span className="text-sm font-mono text-[var(--nous-fg-1)]">
                    {item.entity_name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-[var(--nous-fg-3)]">
                    Connections:
                  </span>
                  <span className="text-sm font-mono font-bold text-[var(--nous-helios)]">
                    {Math.round(item.score)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
