import React, { useState, useCallback, useMemo } from 'react';
import {
  ClockIcon,
  CalendarIcon,
  DocumentTextIcon,
  UserGroupIcon,
  ChartBarIcon,
  FunnelIcon,
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  EyeIcon,
  MagnifyingGlassIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface EntityTimelineProps {
  entities: Entity[];
  relationships?: Relationship[];
  documents?: any[];
  onEntityClick?: (entity: Entity) => void;
  onDocumentClick?: (document: any) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  className?: string;
  maxEvents?: number;
  autoPlay?: boolean;
}

interface TimelineEvent {
  id: string;
  timestamp: string;
  type:
    | 'entity_created'
    | 'entity_mentioned'
    | 'relationship_formed'
    | 'document_added';
  title: string;
  description: string;
  entityId?: string;
  relationshipId?: string;
  documentId?: string;
  importance: 'low' | 'medium' | 'high';
  metadata?: Record<string, any>;
}

interface TimelineFilter {
  eventTypes: TimelineEvent['type'][];
  entityTypes: Entity['type'][];
  dateRange: {
    start: string;
    end: string;
  } | null;
  importance: TimelineEvent['importance'][];
  searchTerm: string;
}

export const EntityTimeline: React.FC<EntityTimelineProps> = ({
  entities = [],
  relationships = [],
  documents = [],
  onEntityClick,
  onDocumentClick,
  onRelationshipClick,
  className,
  maxEvents = 100,
  autoPlay = false,
}) => {
  const [filters, setFilters] = useState<TimelineFilter>({
    eventTypes: [],
    entityTypes: [],
    dateRange: null,
    importance: [],
    searchTerm: '',
  });

  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [currentDateIndex, setCurrentDateIndex] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(
    null
  );

  // Generate timeline events from entities, relationships, and documents
  const timelineEvents = useMemo((): TimelineEvent[] => {
    const events: TimelineEvent[] = [];

    // Entity creation events
    entities.forEach((entity) => {
      events.push({
        id: `entity-created-${entity.id}`,
        timestamp: entity.first_seen,
        type: 'entity_created',
        title: `Entity "${entity.name}" appeared`,
        description: `New ${entity.type} entity detected with ${entity.confidence * 100}% confidence`,
        entityId: entity.id,
        importance:
          entity.confidence > 0.8
            ? 'high'
            : entity.confidence > 0.6
              ? 'medium'
              : 'low',
        metadata: {
          entityType: entity.type,
          confidence: entity.confidence,
          aliases: entity.aliases,
        },
      });
    });

    // Relationship formation events
    relationships.forEach((relationship) => {
      const sourceEntity = entities.find(
        (e) => e.id === relationship.source_entity_id
      );
      const targetEntity = entities.find(
        (e) => e.id === relationship.target_entity_id
      );

      events.push({
        id: `relationship-formed-${relationship.id}`,
        timestamp: relationship.first_seen,
        type: 'relationship_formed',
        title: `Relationship "${relationship.relationship_type}" formed`,
        description: `Connected ${sourceEntity?.name || 'Unknown'} and ${targetEntity?.name || 'Unknown'}`,
        relationshipId: relationship.id,
        importance:
          relationship.confidence > 0.8
            ? 'high'
            : relationship.confidence > 0.6
              ? 'medium'
              : 'low',
        metadata: {
          sourceEntityId: relationship.source_entity_id,
          targetEntityId: relationship.target_entity_id,
          relationshipType: relationship.relationship_type,
          confidence: relationship.confidence,
          weight: relationship.weight,
        },
      });
    });

    // Document addition events
    documents.forEach((document) => {
      events.push({
        id: `document-added-${document.id}`,
        timestamp: document.upload_timestamp,
        type: 'document_added',
        title: `Document "${document.title}" added`,
        description: `${document.file_type.toUpperCase()} document uploaded and processed`,
        documentId: document.id,
        importance: 'medium',
        metadata: {
          fileType: document.file_type,
          fileSize: document.file_size,
          processingStatus: document.processing_status,
        },
      });
    });

    // Sort events by timestamp (newest first)
    return events.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [entities, relationships, documents]);

  // Filter timeline events
  const filteredEvents = useMemo(() => {
    let filtered = timelineEvents;

    // Filter by event types
    if (filters.eventTypes.length > 0) {
      filtered = filtered.filter((event) =>
        filters.eventTypes.includes(event.type)
      );
    }

    // Filter by entity types
    if (filters.entityTypes.length > 0) {
      filtered = filtered.filter((event) => {
        if (event.entityId) {
          const entity = entities.find((e) => e.id === event.entityId);
          return entity && filters.entityTypes.includes(entity.type);
        }
        return true; // Keep non-entity events
      });
    }

    // Filter by importance
    if (filters.importance.length > 0) {
      filtered = filtered.filter((event) =>
        filters.importance.includes(event.importance)
      );
    }

    // Filter by date range
    if (filters.dateRange) {
      const start = new Date(filters.dateRange.start);
      const end = new Date(filters.dateRange.end);
      filtered = filtered.filter((event) => {
        const eventDate = new Date(event.timestamp);
        return eventDate >= start && eventDate <= end;
      });
    }

    // Filter by search term
    if (filters.searchTerm) {
      const term = filters.searchTerm.toLowerCase();
      filtered = filtered.filter(
        (event) =>
          event.title.toLowerCase().includes(term) ||
          event.description.toLowerCase().includes(term)
      );
    }

    return filtered.slice(0, maxEvents);
  }, [timelineEvents, filters, entities, maxEvents]);

  // Get unique dates for timeline navigation
  const uniqueDates = useMemo(() => {
    const dates = new Set<string>();
    filteredEvents.forEach((event) => {
      dates.add(new Date(event.timestamp).toDateString());
    });
    return Array.from(dates).sort(
      (a, b) => new Date(b).getTime() - new Date(a).getTime()
    );
  }, [filteredEvents]);

  // Get events for current date
  const eventsForCurrentDate = useMemo(() => {
    if (currentDateIndex >= uniqueDates.length) return [];
    const currentDate = uniqueDates[currentDateIndex];
    return filteredEvents.filter(
      (event) => new Date(event.timestamp).toDateString() === currentDate
    );
  }, [filteredEvents, uniqueDates, currentDateIndex]);

  // Update filters
  const updateFilters = useCallback((newFilters: Partial<TimelineFilter>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  }, []);

  // Play/pause animation
  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  // Navigate timeline
  const goToNextDate = useCallback(() => {
    setCurrentDateIndex((prev) => Math.max(0, prev - 1));
  }, []);

  const goToPreviousDate = useCallback(() => {
    setCurrentDateIndex((prev) => Math.min(uniqueDates.length - 1, prev + 1));
  }, [uniqueDates.length]);

  // Auto-play effect
  React.useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentDateIndex((prev) => {
        if (prev >= uniqueDates.length - 1) {
          setIsPlaying(false);
          return 0; // Loop back to start
        }
        return prev + 1;
      });
    }, 3000); // 3 seconds per date

    return () => clearInterval(interval);
  }, [isPlaying, uniqueDates.length]);

  // Get event icon
  const getEventIcon = (type: TimelineEvent['type']) => {
    switch (type) {
      case 'entity_created':
        return (
          <UserGroupIcon className="h-5 w-5 text-[var(--nous-sol-safe)]" />
        );
      case 'relationship_formed':
        return <ArrowPathIcon className="h-5 w-5 text-[var(--nous-terra)]" />;
      case 'document_added':
        return <DocumentTextIcon className="h-5 w-5 text-[var(--nous-fg-3)]" />;
      default:
        return <ClockIcon className="h-5 w-5 text-muted-foreground" />;
    }
  };

  // Get event color
  const getEventColor = (importance: TimelineEvent['importance']) => {
    switch (importance) {
      case 'high':
        return 'border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10';
      case 'medium':
        return 'border-[var(--nous-corona)]/40 bg-[var(--nous-corona)]/10';
      case 'low':
        return 'border-border bg-[var(--nous-bg-2)]';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getImportanceBadgeColor = (importance: TimelineEvent['importance']) => {
    switch (importance) {
      case 'high':
        return 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]';
      case 'medium':
        return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
      case 'low':
        return 'bg-[var(--nous-bg-3)] text-foreground';
    }
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Timeline Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <ClockIcon className="h-5 w-5 mr-2" />
              Entity Timeline
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={togglePlay}
                disabled={uniqueDates.length === 0}
              >
                {isPlaying ? (
                  <PauseIcon className="h-4 w-4" />
                ) : (
                  <PlayIcon className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={goToNextDate}
                disabled={currentDateIndex >= uniqueDates.length - 1}
              >
                <ArrowLeftIcon className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={goToPreviousDate}
                disabled={currentDateIndex === 0}
              >
                <ArrowRightIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Timeline Progress */}
          {uniqueDates.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-foreground">
                  {formatDate(
                    uniqueDates[currentDateIndex] || new Date().toISOString()
                  )}
                </span>
                <span className="text-sm text-muted-foreground">
                  {currentDateIndex + 1} of {uniqueDates.length} dates
                </span>
              </div>
              <Progress
                value={((currentDateIndex + 1) / uniqueDates.length) * 100}
                className="h-2"
              />
            </div>
          )}

          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Search */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                <MagnifyingGlassIcon className="h-4 w-4 inline mr-1" />
                Search Events
              </label>
              <input
                type="text"
                value={filters.searchTerm}
                onChange={(e) => updateFilters({ searchTerm: e.target.value })}
                placeholder="Search events..."
                className="w-full px-3 py-2 border border-border rounded-md text-sm"
              />
            </div>

            {/* Event Type Filter */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Event Types
              </label>
              <div className="space-y-1">
                {[
                  'entity_created',
                  'relationship_formed',
                  'document_added',
                ].map((type) => (
                  <label key={type} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={filters.eventTypes.includes(type as any)}
                      onChange={(e) => {
                        const newTypes = e.target.checked
                          ? [...filters.eventTypes, type as any]
                          : filters.eventTypes.filter((t) => t !== type);
                        updateFilters({ eventTypes: newTypes });
                      }}
                      className="rounded border-border text-[var(--nous-sol)] focus:ring-[var(--nous-sol)] mr-2"
                    />
                    <span className="text-sm">
                      {type
                        .replace('_', ' ')
                        .replace(/\b\w/g, (l) => l.toUpperCase())}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Entity Type Filter */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Entity Types
              </label>
              <div className="space-y-1">
                {[
                  'person',
                  'organization',
                  'location',
                  'concept',
                  'date',
                  'product',
                ].map((type) => (
                  <label key={type} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={filters.entityTypes.includes(type as any)}
                      onChange={(e) => {
                        const newTypes = e.target.checked
                          ? [...filters.entityTypes, type as any]
                          : filters.entityTypes.filter((t) => t !== type);
                        updateFilters({ entityTypes: newTypes });
                      }}
                      className="rounded border-border text-[var(--nous-sol)] focus:ring-[var(--nous-sol)] mr-2"
                    />
                    <span className="text-sm capitalize">{type}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Importance Filter */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Importance
              </label>
              <div className="space-y-1">
                {['high', 'medium', 'low'].map((importance) => (
                  <label key={importance} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={filters.importance.includes(importance as any)}
                      onChange={(e) => {
                        const newImportance = e.target.checked
                          ? [...filters.importance, importance as any]
                          : filters.importance.filter((i) => i !== importance);
                        updateFilters({ importance: newImportance });
                      }}
                      className="rounded border-border text-[var(--nous-sol)] focus:ring-[var(--nous-sol)] mr-2"
                    />
                    <span className="text-sm capitalize">{importance}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Filter Summary */}
          <div className="mt-4 flex items-center justify-between">
            <div className="text-sm text-foreground">
              Showing {filteredEvents.length} of {timelineEvents.length} events
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setFilters({
                  eventTypes: [],
                  entityTypes: [],
                  dateRange: null,
                  importance: [],
                  searchTerm: '',
                })
              }
            >
              <FunnelIcon className="h-4 w-4 mr-2" />
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Timeline Events */}
      {uniqueDates.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8">
            <ClockIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              No events found in the current timeline.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <CalendarIcon className="h-5 w-5 mr-2" />
              {formatDate(
                uniqueDates[currentDateIndex] || new Date().toISOString()
              )}
              <Badge variant="outline" className="ml-3">
                {eventsForCurrentDate.length} events
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {eventsForCurrentDate.map((event, index) => (
                <div
                  key={event.id}
                  className={cn(
                    'flex items-start space-x-4 p-4 rounded-lg border cursor-pointer hover:shadow-md transition-shadow',
                    getEventColor(event.importance),
                    selectedEvent?.id === event.id &&
                      'ring-2 ring-[var(--nous-sol)]'
                  )}
                  onClick={() => setSelectedEvent(event)}
                >
                  {/* Event Icon */}
                  <div className="flex-shrink-0 mt-1">
                    {getEventIcon(event.type)}
                  </div>

                  {/* Event Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-foreground">
                        {event.title}
                      </h4>
                      <div className="flex items-center space-x-2">
                        <Badge
                          className={getImportanceBadgeColor(event.importance)}
                        >
                          {event.importance}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatTime(event.timestamp)}
                        </span>
                      </div>
                    </div>

                    <p className="text-sm text-foreground mb-2">
                      {event.description}
                    </p>

                    {/* Event Actions */}
                    <div className="flex items-center space-x-2">
                      {event.entityId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            const entity = entities.find(
                              (ent) => ent.id === event.entityId
                            );
                            if (entity) onEntityClick?.(entity);
                          }}
                        >
                          <EyeIcon className="h-4 w-4 mr-1" />
                          View Entity
                        </Button>
                      )}
                      {event.relationshipId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            const relationship = relationships.find(
                              (rel) => rel.id === event.relationshipId
                            );
                            if (relationship)
                              onRelationshipClick?.(relationship);
                          }}
                        >
                          <EyeIcon className="h-4 w-4 mr-1" />
                          View Relationship
                        </Button>
                      )}
                      {event.documentId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            const document = documents.find(
                              (doc) => doc.id === event.documentId
                            );
                            if (document) onDocumentClick?.(document);
                          }}
                        >
                          <EyeIcon className="h-4 w-4 mr-1" />
                          View Document
                        </Button>
                      )}
                    </div>

                    {/* Event Metadata */}
                    {event.metadata &&
                      Object.keys(event.metadata).length > 0 && (
                        <div className="mt-3 pt-3 border-t border-border">
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(event.metadata).map(
                              ([key, value]) => (
                                <Badge
                                  key={key}
                                  variant="secondary"
                                  className="text-xs"
                                >
                                  {key}:{' '}
                                  {typeof value === 'object'
                                    ? JSON.stringify(value)
                                    : value}
                                </Badge>
                              )
                            )}
                          </div>
                        </div>
                      )}
                  </div>
                </div>
              ))}
            </div>

            {eventsForCurrentDate.length === 0 && (
              <div className="text-center py-8">
                <CalendarIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  No events found for this date.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Event Detail Modal */}
      {selectedEvent && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Event Details
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedEvent(null)}
              >
                ×
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-foreground mb-2">
                  {selectedEvent.title}
                </h4>
                <p className="text-sm text-foreground">
                  {selectedEvent.description}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium text-foreground">
                    Timestamp:
                  </span>
                  <div>
                    {formatDate(selectedEvent.timestamp)} at{' '}
                    {formatTime(selectedEvent.timestamp)}
                  </div>
                </div>
                <div>
                  <span className="font-medium text-foreground">
                    Importance:
                  </span>
                  <Badge
                    className={getImportanceBadgeColor(
                      selectedEvent.importance
                    )}
                  >
                    {selectedEvent.importance}
                  </Badge>
                </div>
              </div>

              {selectedEvent.metadata && (
                <div>
                  <h5 className="font-medium text-foreground mb-2">
                    Metadata:
                  </h5>
                  <div className="bg-[var(--nous-bg-2)] rounded p-3 text-sm">
                    {Object.entries(selectedEvent.metadata).map(
                      ([key, value]) => (
                        <div key={key}>
                          <span className="font-medium">{key}:</span>{' '}
                          {typeof value === 'object'
                            ? JSON.stringify(value)
                            : value}
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default EntityTimeline;
