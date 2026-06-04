import React, { useState, useEffect, useCallback } from 'react';
import {
  InformationCircleIcon,
  ShareIcon,
  ClockIcon,
  DocumentTextIcon,
  UserGroupIcon,
  ChartBarIcon,
  ArrowLeftIcon,
  ArrowTopRightOnSquareIcon,
  BookmarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface EntityDetailsProps {
  entityId: string;
  entity?: Entity;
  relationships?: Relationship[];
  relatedDocuments?: any[];
  relatedEntities?: Array<{
    entity: Entity;
    relationship: Relationship;
    strength: number;
  }>;
  mentionContexts?: Array<{
    document_id: string;
    snippet: string;
    page_number?: number;
    confidence: number;
  }>;
  onClose?: () => void;
  onEntityClick?: (entityId: string) => void;
  onDocumentClick?: (documentId: string) => void;
  onRelationshipClick?: (relationshipId: string) => void;
  className?: string;
  loading?: boolean;
}

export const EntityDetails: React.FC<EntityDetailsProps> = ({
  entityId,
  entity,
  relationships = [],
  relatedDocuments = [],
  relatedEntities = [],
  mentionContexts = [],
  onClose,
  onEntityClick,
  onDocumentClick,
  onRelationshipClick,
  className,
  loading = false,
}) => {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'relationships' | 'documents' | 'timeline'
  >('overview');
  const [isBookmarked, setIsBookmarked] = useState(false);

  // Mock loading state if entity is not provided
  useEffect(() => {
    if (!entity && !loading) {
      // In a real implementation, this would fetch the entity data
      console.log('Would fetch entity data for:', entityId);
    }
  }, [entityId, entity, loading]);

  const getEntityTypeColor = (type: Entity['type']) => {
    const colors = {
      person: 'bg-blue-100 text-blue-800 border-blue-200',
      organization: 'bg-green-100 text-green-800 border-green-200',
      location: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      concept: 'bg-purple-100 text-purple-800 border-purple-200',
      date: 'bg-orange-100 text-orange-800 border-orange-200',
      product: 'bg-pink-100 text-pink-800 border-pink-200',
    };
    return (
      colors[type] || 'bg-[var(--nous-bg-3)] text-foreground border-border'
    );
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-[var(--nous-terra)]';
    if (confidence >= 0.7) return 'text-[var(--nous-corona)]';
    return 'text-[var(--nous-mars)]';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const handleBookmark = useCallback(() => {
    setIsBookmarked((prev) => !prev);
    // In a real implementation, this would make an API call
    console.log('Would bookmark entity:', entityId);
  }, [entityId]);

  const handleShare = useCallback(() => {
    // In a real implementation, this would open a share dialog
    console.log('Would share entity:', entityId);
  }, [entityId]);

  if (loading) {
    return (
      <div className={cn('p-6', className)}>
        <div className="animate-pulse">
          <div className="h-8 bg-[var(--nous-bg-3)] rounded w-3/4 mb-4"></div>
          <div className="h-4 bg-[var(--nous-bg-3)] rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-[var(--nous-bg-3)] rounded w-1/3 mb-6"></div>
          <div className="space-y-4">
            <div className="h-32 bg-[var(--nous-bg-3)] rounded"></div>
            <div className="h-32 bg-[var(--nous-bg-3)] rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!entity) {
    return (
      <div className={cn('p-6 text-center', className)}>
        <ExclamationCircleIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">
          Entity Not Found
        </h3>
        <p className="text-muted-foreground mb-4">
          The requested entity could not be loaded.
        </p>
        {onClose && (
          <Button onClick={onClose} variant="outline">
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Go Back
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className={cn('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b bg-[var(--nous-bg-2)]">
        <div className="flex items-center space-x-3">
          {onClose && (
            <Button onClick={onClose} variant="ghost" size="sm">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          )}
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              {entity.name}
            </h2>
            <div className="flex items-center space-x-2 mt-1">
              <Badge className={getEntityTypeColor(entity.type)}>
                {entity.type}
              </Badge>
              <span
                className={cn(
                  'text-sm font-medium',
                  getConfidenceColor(entity.confidence)
                )}
              >
                {Math.round(entity.confidence * 100)}% confidence
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Button onClick={handleBookmark} variant="ghost" size="sm">
            <BookmarkIcon
              className={cn(
                'h-4 w-4',
                isBookmarked && 'text-[var(--nous-fg-accent-safe)] fill-current'
              )}
            />
          </Button>
          <Button onClick={handleShare} variant="ghost" size="sm">
            <ShareIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Entity Stats */}
      <div className="px-6 py-4 bg-background border-b">
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-foreground">
              {entity.mentions}
            </div>
            <div className="text-sm text-muted-foreground">Mentions</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">
              {relationships.length}
            </div>
            <div className="text-sm text-muted-foreground">Relationships</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">
              {relatedDocuments.length}
            </div>
            <div className="text-sm text-muted-foreground">Documents</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">
              {entity.aliases.length}
            </div>
            <div className="text-sm text-muted-foreground">Aliases</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b bg-background px-6">
        <button
          onClick={() => setActiveTab('overview')}
          className={cn(
            'py-3 px-4 border-b-2 font-medium text-sm transition-colors',
            activeTab === 'overview'
              ? 'border-[var(--nous-sol)] text-[var(--nous-fg-accent-safe)]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <InformationCircleIcon className="h-4 w-4 inline mr-2" />
          Overview
        </button>
        <button
          onClick={() => setActiveTab('relationships')}
          className={cn(
            'py-3 px-4 border-b-2 font-medium text-sm transition-colors',
            activeTab === 'relationships'
              ? 'border-[var(--nous-sol)] text-[var(--nous-fg-accent-safe)]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <UserGroupIcon className="h-4 w-4 inline mr-2" />
          Relationships ({relationships.length})
        </button>
        <button
          onClick={() => setActiveTab('documents')}
          className={cn(
            'py-3 px-4 border-b-2 font-medium text-sm transition-colors',
            activeTab === 'documents'
              ? 'border-[var(--nous-sol)] text-[var(--nous-fg-accent-safe)]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <DocumentTextIcon className="h-4 w-4 inline mr-2" />
          Documents ({relatedDocuments.length})
        </button>
        <button
          onClick={() => setActiveTab('timeline')}
          className={cn(
            'py-3 px-4 border-b-2 font-medium text-sm transition-colors',
            activeTab === 'timeline'
              ? 'border-[var(--nous-sol)] text-[var(--nous-fg-accent-safe)]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <ClockIcon className="h-4 w-4 inline mr-2" />
          Timeline
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Description */}
            {entity.description && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Description</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-foreground">{entity.description}</p>
                </CardContent>
              </Card>
            )}

            {/* Aliases */}
            {entity.aliases.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Also Known As</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {entity.aliases.map((alias, index) => (
                      <Badge key={index} variant="secondary">
                        {alias}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Key Metrics */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Key Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium text-foreground">
                        Confidence Score
                      </span>
                      <span
                        className={cn(
                          'text-sm font-bold',
                          getConfidenceColor(entity.confidence)
                        )}
                      >
                        {Math.round(entity.confidence * 100)}%
                      </span>
                    </div>
                    <Progress value={entity.confidence * 100} className="h-2" />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-muted-foreground">
                        First Seen
                      </div>
                      <div className="font-medium">
                        {formatDate(entity.first_seen)}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">
                        Last Seen
                      </div>
                      <div className="font-medium">
                        {formatDate(entity.last_seen)}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recent Contexts */}
            {mentionContexts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Recent Mentions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {mentionContexts.slice(0, 3).map((context, index) => (
                      <div
                        key={index}
                        className="p-3 bg-[var(--nous-bg-2)] rounded-lg"
                      >
                        <p className="text-sm text-foreground italic">
                          "{context.snippet}"
                        </p>
                        <div className="flex justify-between items-center mt-2">
                          <Badge variant="outline" className="text-xs">
                            {Math.round(context.confidence * 100)}% confidence
                          </Badge>
                          {context.page_number && (
                            <span className="text-xs text-muted-foreground">
                              Page {context.page_number}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'relationships' && (
          <div className="space-y-4">
            {relationships.length === 0 ? (
              <div className="text-center py-8">
                <UserGroupIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  No relationships found for this entity.
                </p>
              </div>
            ) : (
              relationships.map((relationship) => (
                <Card
                  key={relationship.id}
                  className="hover:shadow-md transition-shadow cursor-pointer"
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <Badge className="bg-[var(--nous-sol)]/15 text-[var(--nous-fg-accent-safe)]">
                            {relationship.relationship_type}
                          </Badge>
                          <span
                            className={cn(
                              'text-sm font-medium',
                              getConfidenceColor(relationship.confidence)
                            )}
                          >
                            {Math.round(relationship.confidence * 100)}%
                          </span>
                        </div>
                        <p className="text-sm text-foreground mt-2">
                          {relationship.context}
                        </p>
                        <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
                          <span>Weight: {relationship.weight}</span>
                          <span>
                            Documents: {relationship.document_ids.length}
                          </span>
                          <span>{formatDate(relationship.first_seen)}</span>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="space-y-4">
            {relatedDocuments.length === 0 ? (
              <div className="text-center py-8">
                <DocumentTextIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  No documents found containing this entity.
                </p>
              </div>
            ) : (
              relatedDocuments.map((document) => (
                <Card
                  key={document.id}
                  className="hover:shadow-md transition-shadow cursor-pointer"
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-medium text-foreground">
                          {document.title}
                        </h4>
                        <p className="text-sm text-foreground mt-1">
                          {document.filename}
                        </p>
                        <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{document.file_type}</Badge>
                          <span>{formatDate(document.upload_timestamp)}</span>
                          <span>
                            {(document.file_size / 1024 / 1024).toFixed(2)} MB
                          </span>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Entity Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center space-x-3">
                    <CheckCircleIcon className="h-5 w-5 text-[var(--nous-terra)]" />
                    <div>
                      <div className="font-medium">First Appearance</div>
                      <div className="text-sm text-muted-foreground">
                        {formatDate(entity.first_seen)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <ClockIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <div>
                      <div className="font-medium">Last Mention</div>
                      <div className="text-sm text-muted-foreground">
                        {formatDate(entity.last_seen)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <ChartBarIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <div>
                      <div className="font-medium">Total Mentions</div>
                      <div className="text-sm text-muted-foreground">
                        {entity.mentions} occurrences across documents
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Document Timeline */}
            {relatedDocuments.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Document History</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {relatedDocuments
                      .sort(
                        (a, b) =>
                          new Date(b.upload_timestamp).getTime() -
                          new Date(a.upload_timestamp).getTime()
                      )
                      .map((document) => (
                        <div
                          key={document.id}
                          className="flex items-center space-x-3 p-3 bg-[var(--nous-bg-2)] rounded-lg"
                        >
                          <DocumentTextIcon className="h-5 w-5 text-muted-foreground" />
                          <div className="flex-1">
                            <div className="font-medium text-sm">
                              {document.title}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {formatDate(document.upload_timestamp)}
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EntityDetails;
