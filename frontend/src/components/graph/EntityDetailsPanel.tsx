/**
 * Entity Details Panel - Displays entity information from backend
 *
 * This component ONLY displays entity data provided by backend APIs.
 * NO relationship processing or analytics computation included.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { entityService } from '../../services/entityService';
import { EntityDetails, GraphNode, GraphEdge } from '../../types/graph-api';

// Local types for entity details data
interface DocumentReference {
  id: string;
  title: string;
  snippet?: string;
  page_number?: number;
  confidence: number;
  relevance_score: number;
}

interface TimelineEvent {
  timestamp: string;
  type: string;
  description: string;
  metadata?: Record<string, unknown>;
}

interface EntityDetailsPanelProps {
  entityId: string;
  onClose?: () => void;
  onRelationshipClick?: (relationshipId: string) => void;
  onRelatedEntityClick?: (entityId: string) => void;
  className?: string;
}

export const EntityDetailsPanel: React.FC<EntityDetailsPanelProps> = ({
  entityId,
  onClose,
  onRelationshipClick,
  onRelatedEntityClick,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'relationships' | 'documents' | 'timeline'
  >('overview');

  // Fetch entity details from backend - NO processing logic
  const {
    data: entityDetails,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['entityDetails', entityId],
    queryFn: () => entityService.getEntityDetails(entityId),
    enabled: !!entityId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  // Fetch similar entities from backend
  const { data: similarEntities, isLoading: isSimilarLoading } = useQuery({
    queryKey: ['similarEntities', entityId],
    queryFn: () => entityService.findSimilarEntities(entityId, 10, 0.5),
    enabled: !!entityId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (!entityId) {
    return (
      <div className={`entity-details-panel ${className}`}>
        <div className="p-4 text-center text-muted-foreground">
          Select an entity to view details
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className={`entity-details-panel ${className}`}>
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-foreground">
            Loading entity details...
          </span>
        </div>
      </div>
    );
  }

  if (error || !entityDetails) {
    return (
      <div className={`entity-details-panel ${className}`}>
        <div className="p-4 text-red-600 text-center">
          <h3 className="text-lg font-semibold mb-2">
            Failed to load entity details
          </h3>
          <p className="text-sm">
            {(error as Error)?.message || 'Entity not found'}
          </p>
        </div>
      </div>
    );
  }

  const {
    entity,
    relationships,
    documents,
    related_entities,
    mention_contexts,
    timeline,
  } = entityDetails;

  const renderOverview = () => (
    <div className="space-y-4">
      {/* Basic Information */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="font-semibold text-lg mb-3">{entity.label}</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="font-medium text-foreground">Type:</span>
            <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
              {entity.type}
            </span>
          </div>
          <div>
            <span className="font-medium text-foreground">Confidence:</span>
            <span className="ml-2 font-semibold">
              {(entity.confidence * 100).toFixed(1)}%
            </span>
          </div>
          <div>
            <span className="font-medium text-foreground">Relationships:</span>
            <span className="ml-2">{relationships.length}</span>
          </div>
          <div>
            <span className="font-medium text-foreground">Documents:</span>
            <span className="ml-2">{documents.length}</span>
          </div>
        </div>
      </div>

      {/* Metadata */}
      {Object.keys(entity.metadata || {}).length > 0 && (
        <div>
          <h4 className="font-semibold mb-2">Metadata</h4>
          <div className="bg-gray-50 p-3 rounded-lg text-sm">
            {Object.entries(entity.metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between py-1">
                <span className="font-medium text-foreground">{key}:</span>
                <span className="text-foreground">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Similar Entities */}
      {similarEntities && similarEntities.length > 0 && (
        <div>
          <h4 className="font-semibold mb-2">Similar Entities</h4>
          <div className="space-y-2">
            {similarEntities.map(
              ({
                entity: similarEntity,
                similarity,
              }: {
                entity: GraphNode;
                similarity: number;
              }) => (
                <div
                  key={similarEntity.id}
                  className="flex items-center justify-between p-2 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer"
                  onClick={() => onRelatedEntityClick?.(similarEntity.id)}
                >
                  <div>
                    <div className="font-medium text-sm">
                      {similarEntity.label}
                    </div>
                    <div className="text-xs text-foreground">
                      {similarEntity.type}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-blue-600">
                      {(similarity * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">
                      similarity
                    </div>
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );

  const renderRelationships = () => (
    <div className="space-y-3">
      {relationships.length === 0 ? (
        <div className="text-center text-muted-foreground py-4">
          No relationships found for this entity
        </div>
      ) : (
        relationships.map((relationship: GraphEdge) => (
          <div
            key={relationship.id}
            className="border border-border rounded-lg p-3 hover:border-blue-300 cursor-pointer"
            onClick={() => onRelationshipClick?.(relationship.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="font-medium text-sm">{relationship.type}</div>
                <div className="text-xs text-foreground mt-1">
                  {relationship.source === entityId ? (
                    <>
                      To:{' '}
                      <span className="font-medium">{relationship.target}</span>
                    </>
                  ) : (
                    <>
                      From:{' '}
                      <span className="font-medium">{relationship.source}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold">
                  {relationship.weight.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground">weight</div>
              </div>
            </div>
            {relationship.metadata &&
              Object.keys(relationship.metadata).length > 0 && (
                <div className="mt-2 text-xs text-foreground">
                  {Object.entries(relationship.metadata)
                    .slice(0, 2)
                    .map(([key, value]) => (
                      <span key={key} className="mr-3">
                        {key}: {String(value)}
                      </span>
                    ))}
                </div>
              )}
          </div>
        ))
      )}
    </div>
  );

  const renderDocuments = () => (
    <div className="space-y-3">
      {documents.length === 0 ? (
        <div className="text-center text-muted-foreground py-4">
          No documents found for this entity
        </div>
      ) : (
        documents.map((doc: DocumentReference, index: number) => (
          <div
            key={doc.id || index}
            className="border border-border rounded-lg p-3"
          >
            <div className="font-medium text-sm mb-1">{doc.title}</div>
            <div className="text-xs text-foreground mb-2">
              {doc.page_number && `Page ${doc.page_number} • `}
              Relevance: {(doc.relevance_score * 100).toFixed(1)}%
            </div>
            {doc.snippet && (
              <div className="text-sm text-foreground bg-gray-50 p-2 rounded italic">
                "{doc.snippet}"
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );

  const renderTimeline = () => (
    <div className="space-y-3">
      {timeline.length === 0 ? (
        <div className="text-center text-muted-foreground py-4">
          No timeline events available
        </div>
      ) : (
        timeline.map((event: TimelineEvent, index: number) => (
          <div key={index} className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-2 h-2 bg-blue-600 rounded-full mt-2"></div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground">
                {event.type
                  .replace(/_/g, ' ')
                  .replace(/\b\w/g, (l: string) => l.toUpperCase())}
              </div>
              <div className="text-xs text-muted-foreground">
                {new Date(event.timestamp).toLocaleString()}
              </div>
              <div className="text-sm text-foreground mt-1">
                {event.description}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div className={`entity-details-panel ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Entity Details</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
            aria-label="Close panel"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {[
          { key: 'overview', label: 'Overview' },
          {
            key: 'relationships',
            label: 'Relationships',
            count: relationships.length,
          },
          { key: 'documents', label: 'Documents', count: documents.length },
          { key: 'timeline', label: 'Timeline' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-gray-100 text-foreground rounded-full">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div
        className="p-4 overflow-y-auto"
        style={{ maxHeight: 'calc(100% - 120px)' }}
      >
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'relationships' && renderRelationships()}
        {activeTab === 'documents' && renderDocuments()}
        {activeTab === 'timeline' && renderTimeline()}
      </div>
    </div>
  );
};

export default EntityDetailsPanel;
