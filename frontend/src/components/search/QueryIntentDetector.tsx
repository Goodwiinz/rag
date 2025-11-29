import React, { useState, useCallback, useEffect } from 'react';
import {
  ChartBarIcon,
  SparklesIcon,
  ClockIcon,
  DocumentTextIcon,
  UserGroupIcon,
  MapPinIcon,
  CalendarIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  AcademicCapIcon,
  LightBulbIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { QueryIntent } from '@/types/search';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface QueryIntentDetectorProps {
  query: string;
  onIntentDetected?: (intent: QueryIntent) => void;
  loading?: boolean;
  showDetails?: boolean;
  className?: string;
}

interface IntentDetailProps {
  intent: QueryIntent;
  isOpen: boolean;
  onClose: () => void;
}

const IntentDetail: React.FC<IntentDetailProps> = ({ intent, isOpen, onClose }) => {
  const getIntentColor = (intentType: string) => {
    switch (intentType) {
      case 'factual_lookup':
        return 'bg-blue-100 text-blue-800';
      case 'reasoning':
        return 'bg-purple-100 text-purple-800';
      case 'summarization':
        return 'bg-green-100 text-green-800';
      case 'comparison':
        return 'bg-orange-100 text-orange-800';
      case 'exploration':
        return 'bg-indigo-100 text-indigo-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getComplexityColor = (complexity: string) => {
    switch (complexity) {
      case 'simple':
        return 'bg-green-100 text-green-800';
      case 'moderate':
        return 'bg-yellow-100 text-yellow-800';
      case 'complex':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getTemporalColor = (temporal: string) => {
    switch (temporal) {
      case 'current':
        return 'bg-blue-100 text-blue-800';
      case 'historical':
        return 'bg-amber-100 text-amber-800';
      case 'future':
        return 'bg-purple-100 text-purple-800';
      case 'timeless':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getDomainColor = (domain: string) => {
    switch (domain) {
      case 'general':
        return 'bg-green-100 text-green-800';
      case 'technical':
        return 'bg-orange-100 text-orange-800';
      case 'domain_expert':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getEntityIcon = (entityType: string) => {
    const iconClass = "h-4 w-4";
    switch (entityType.toLowerCase()) {
      case 'person':
        return <UserGroupIcon className={cn(iconClass, "text-blue-600")} />;
      case 'location':
        return <MapPinIcon className={cn(iconClass, "text-green-600")} />;
      case 'date':
        return <CalendarIcon className={cn(iconClass, "text-purple-600")} />;
      case 'organization':
        return <DocumentTextIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <LightBulbIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const getModalityIcon = (modality: string) => {
    const iconClass = "h-4 w-4";
    switch (modality) {
      case 'text':
        return <DocumentTextIcon className={cn(iconClass, "text-blue-600")} />;
      case 'image':
        return <PhotoIcon className={cn(iconClass, "text-green-600")} />;
      case 'audio':
        return <MusicalNoteIcon className={cn(iconClass, "text-purple-600")} />;
      case 'video':
        return <VideoCameraIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <DocumentTextIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Query Intent Analysis</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Primary Intent */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Primary Intent</h3>
            <div className="flex items-center space-x-3">
              <Badge className={cn("text-sm", getIntentColor(intent.primary_intent))}>
                {intent.primary_intent.replace('_', ' ')}
              </Badge>
              <span className="text-sm text-gray-600">
                Confidence: {Math.round(intent.confidence * 100)}%
              </span>
            </div>
          </div>

          {/* Query Characteristics */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Query Characteristics</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-700">Complexity:</span>
                <Badge className={getComplexityColor(intent.complexity)}>
                  {intent.complexity}
                </Badge>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-700">Temporal:</span>
                <Badge className={getTemporalColor(intent.temporal_aspect)}>
                  {intent.temporal_aspect}
                </Badge>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-700">Domain:</span>
                <Badge className={getDomainColor(intent.domain_specificity)}>
                  {intent.domain_specificity.replace('_', ' ')}
                </Badge>
              </div>
              {intent.question_type && (
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-700">Question Type:</span>
                  <Badge className="bg-gray-100 text-gray-800">
                    {intent.question_type.replace('_', ' ')}
                  </Badge>
                </div>
              )}
            </div>
          </div>

          {/* Modality Preferences */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Modality Preferences</h3>
            <div className="flex flex-wrap gap-2">
              {intent.modality_preference.map((modality) => (
                <div key={modality} className="flex items-center space-x-1 bg-gray-100 rounded-full px-3 py-1">
                  {getModalityIcon(modality)}
                  <span className="text-sm font-medium text-gray-700 capitalize">
                    {modality}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Detected Entities */}
          {intent.entities.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Detected Entities ({intent.entities.length})</h3>
              <div className="space-y-2">
                {intent.entities.map((entity, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getEntityIcon(entity.type)}
                      <div>
                        <span className="font-medium text-gray-900">{entity.name}</span>
                        <span className="ml-2 text-sm text-gray-600 capitalize">{entity.type}</span>
                      </div>
                    </div>
                    <span className="text-sm text-gray-500">
                      {Math.round(entity.confidence * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Keywords */}
          {intent.keywords.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Key Terms ({intent.keywords.length})</h3>
              <div className="flex flex-wrap gap-2">
                {intent.keywords.map((keyword, index) => (
                  <div key={index} className="flex items-center space-x-2 bg-blue-50 rounded-lg px-3 py-2">
                    <span className="text-sm font-medium text-blue-900">{keyword.term}</span>
                    <span className="text-xs text-blue-600">
                      {Math.round(keyword.importance * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const QueryIntentDetector: React.FC<QueryIntentDetectorProps> = ({
  query,
  onIntentDetected,
  loading = false,
  showDetails = false,
  className,
}) => {
  const [intent, setIntent] = useState<QueryIntent | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);

  const detectIntent = useCallback(async (queryText: string): Promise<QueryIntent> => {
    // Simulate intent detection with rule-based logic
    const lowerQuery = queryText.toLowerCase().trim();

    // Detect question type
    let questionType: QueryIntent['question_type'] = undefined;
    if (lowerQuery.startsWith('what ')) questionType = 'what';
    else if (lowerQuery.startsWith('who ')) questionType = 'who';
    else if (lowerQuery.startsWith('when ')) questionType = 'when';
    else if (lowerQuery.startsWith('where ')) questionType = 'where';
    else if (lowerQuery.startsWith('why ')) questionType = 'why';
    else if (lowerQuery.startsWith('how ')) questionType = 'how';
    else if (lowerQuery.startsWith('which ')) questionType = 'which';
    else if (lowerQuery.match(/\b(is|are|do|does|can|will|should)\b/)) questionType = 'yes_no';

    // Detect primary intent
    let primaryIntent: QueryIntent['primary_intent'] = 'factual_lookup';
    let confidence = 0.8;

    if (lowerQuery.includes('compare') || lowerQuery.includes('difference') || lowerQuery.includes('versus') || lowerQuery.includes('vs')) {
      primaryIntent = 'comparison';
      confidence = 0.9;
    } else if (lowerQuery.includes('summarize') || lowerQuery.includes('summary') || lowerQuery.includes('overview') || lowerQuery.includes('recap')) {
      primaryIntent = 'summarization';
      confidence = 0.85;
    } else if (lowerQuery.includes('why') || lowerQuery.includes('explain') || lowerQuery.includes('reason') || lowerQuery.includes('analyze')) {
      primaryIntent = 'reasoning';
      confidence = 0.8;
    } else if (lowerQuery.includes('explore') || lowerQuery.includes('find') || lowerQuery.includes('search') || lowerQuery.includes('show me')) {
      primaryIntent = 'exploration';
      confidence = 0.75;
    }

    // Detect complexity
    let complexity: QueryIntent['complexity'] = 'simple';
    if (lowerQuery.split(' ').length > 15 || lowerQuery.includes('complex') || lowerQuery.includes('detailed')) {
      complexity = 'complex';
    } else if (lowerQuery.split(' ').length > 8 || lowerQuery.includes('because') || lowerQuery.includes('however')) {
      complexity = 'moderate';
    }

    // Detect temporal aspect
    let temporalAspect: QueryIntent['temporal_aspect'] = 'timeless';
    if (lowerQuery.includes('current') || lowerQuery.includes('now') || lowerQuery.includes('today') || lowerQuery.includes('present')) {
      temporalAspect = 'current';
    } else if (lowerQuery.includes('past') || lowerQuery.includes('history') || lowerQuery.includes('previous') || lowerQuery.includes('before')) {
      temporalAspect = 'historical';
    } else if (lowerQuery.includes('future') || lowerQuery.includes('will') || lowerQuery.includes('predict') || lowerQuery.includes('upcoming')) {
      temporalAspect = 'future';
    }

    // Detect domain specificity
    let domainSpecificity: QueryIntent['domain_specificity'] = 'general';
    const technicalTerms = ['algorithm', 'api', 'database', 'framework', 'protocol', 'architecture', 'system'];
    const domainTerms = ['medical', 'legal', 'financial', 'scientific', 'engineering', 'academic'];

    if (technicalTerms.some(term => lowerQuery.includes(term))) {
      domainSpecificity = 'technical';
      confidence += 0.05;
    } else if (domainTerms.some(term => lowerQuery.includes(term))) {
      domainSpecificity = 'domain_expert';
      confidence += 0.1;
    }

    // Detect modality preferences
    const modalityPreference: QueryIntent['modality_preference'] = ['text'];
    if (lowerQuery.includes('image') || lowerQuery.includes('picture') || lowerQuery.includes('photo') || lowerQuery.includes('visual')) {
      modalityPreference.push('image');
    }
    if (lowerQuery.includes('audio') || lowerQuery.includes('sound') || lowerQuery.includes('music') || lowerQuery.includes('podcast')) {
      modalityPreference.push('audio');
    }
    if (lowerQuery.includes('video') || lowerQuery.includes('movie') || lowerQuery.includes('clip') || lowerQuery.includes('recording')) {
      modalityPreference.push('video');
    }

    // Extract entities (simplified regex-based extraction)
    const entities: QueryIntent['entities'] = [];

    // Extract dates
    const datePattern = /\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}\b/g;
    const dateMatches = lowerQuery.match(datePattern);
    const dates: string[] = dateMatches || [];
    dates.forEach(date => {
      entities.push({
        name: date,
        type: 'date',
        confidence: 0.9
      });
    });

    // Extract capitalized words (potential entities)
    const capitalizedPattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g;
    const capitalizedWords = queryText.match(capitalizedPattern) || [];
    capitalizedWords.forEach(word => {
      if (word.length > 2 && !dates.includes(word)) {
        entities.push({
          name: word,
          type: word.includes(' ') ? 'organization' : 'person',
          confidence: 0.7
        });
      }
    });

    // Extract keywords and calculate importance
    const stopWords = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'];
    const words = lowerQuery.split(/\s+/).filter(word => word.length > 2 && !stopWords.includes(word));

    const keywords: QueryIntent['keywords'] = words.slice(0, 10).map((word, index) => ({
      term: word,
      importance: Math.max(0.1, 1 - (index * 0.1))
    }));

    return {
      primary_intent: primaryIntent,
      confidence: Math.min(1, confidence),
      entities: entities.slice(0, 5),
      keywords: keywords,
      complexity,
      modality_preference: modalityPreference,
      temporal_aspect: temporalAspect,
      domain_specificity: domainSpecificity,
      question_type: questionType
    };
  }, []);

  useEffect(() => {
    if (query && query.trim().length > 0) {
      setIsAnalyzing(true);
      const timer = setTimeout(async () => {
        try {
          const detectedIntent = await detectIntent(query);
          setIntent(detectedIntent);
          onIntentDetected?.(detectedIntent);
        } catch (error) {
          console.error('Intent detection failed:', error);
        } finally {
          setIsAnalyzing(false);
        }
      }, 300);

      return () => clearTimeout(timer);
    } else {
      setIntent(null);
      return undefined;
    }
  }, [query, detectIntent, onIntentDetected]);

  const getIntentIcon = () => {
    if (isAnalyzing) {
      return <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />;
    }

    switch (intent?.primary_intent) {
      case 'factual_lookup':
        return <DocumentTextIcon className="h-4 w-4 text-blue-600" />;
      case 'reasoning':
        return <LightBulbIcon className="h-4 w-4 text-purple-600" />;
      case 'summarization':
        return <ChartBarIcon className="h-4 w-4 text-green-600" />;
      case 'comparison':
        return <AcademicCapIcon className="h-4 w-4 text-orange-600" />;
      case 'exploration':
        return <SparklesIcon className="h-4 w-4 text-indigo-600" />;
      default:
        return <DocumentTextIcon className="h-4 w-4 text-gray-600" />;
    }
  };

  const getIntentColor = (intentType?: string) => {
    switch (intentType) {
      case 'factual_lookup':
        return 'text-blue-600';
      case 'reasoning':
        return 'text-purple-600';
      case 'summarization':
        return 'text-green-600';
      case 'comparison':
        return 'text-orange-600';
      case 'exploration':
        return 'text-indigo-600';
      default:
        return 'text-gray-600';
    }
  };

  if (!query) {
    return null;
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Intent Summary */}
      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {getIntentIcon()}
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-900">Intent:</span>
              <span className={cn("text-sm font-semibold", getIntentColor(intent?.primary_intent))}>
                {intent ? intent.primary_intent.replace('_', ' ') : (isAnalyzing ? 'Analyzing...' : 'Unknown')}
              </span>
              {intent && (
                <span className="text-xs text-gray-500">
                  ({Math.round(intent.confidence * 100)}% confidence)
                </span>
              )}
            </div>
            {intent && (
              <div className="flex items-center space-x-2 mt-1">
                <Badge variant="outline" className="text-xs">
                  {intent.complexity}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {intent.temporal_aspect}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {intent.domain_specificity.replace('_', ' ')}
                </Badge>
              </div>
            )}
          </div>
        </div>

        {showDetails && intent && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetailDialog(true)}
            className="h-8 w-8 p-0"
          >
            <InformationCircleIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Quick Insights */}
      {intent && !loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="flex items-center space-x-1 p-2 bg-blue-50 rounded">
            <DocumentTextIcon className="h-3 w-3 text-blue-600" />
            <span className="text-blue-800 font-medium">{intent.entities.length} entities</span>
          </div>
          <div className="flex items-center space-x-1 p-2 bg-green-50 rounded">
            <SparklesIcon className="h-3 w-3 text-green-600" />
            <span className="text-green-800 font-medium">{intent.keywords.length} keywords</span>
          </div>
          <div className="flex items-center space-x-1 p-2 bg-purple-50 rounded">
            <PhotoIcon className="h-3 w-3 text-purple-600" />
            <span className="text-purple-800 font-medium">{intent.modality_preference.length} modalities</span>
          </div>
          <div className="flex items-center space-x-1 p-2 bg-orange-50 rounded">
            <ClockIcon className="h-3 w-3 text-orange-600" />
            <span className="text-orange-800 font-medium">{intent.question_type || 'statement'}</span>
          </div>
        </div>
      )}

      {/* Detail Dialog */}
      {intent && (
        <IntentDetail
          intent={intent}
          isOpen={showDetailDialog}
          onClose={() => setShowDetailDialog(false)}
        />
      )}
    </div>
  );
};

export default QueryIntentDetector;