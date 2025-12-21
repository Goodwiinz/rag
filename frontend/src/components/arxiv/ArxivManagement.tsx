"use client";

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { apiClient } from '@/services/apiClient';
import { Brain, BookOpen, CheckCircle, Database, FileText, Hash, Link2, Loader2, RefreshCw, TrendingUp, Upload } from 'lucide-react';
import React, { useState } from 'react';

interface TrackResult {
  status: string;
  timestamp: string;
  result: {
    categories: string[];
    period_days: number;
    papers_found: number;
    changes_detected: number;
    changes_by_type: {
      new: Array<any>;
      updated: Array<any>;
      deleted: Array<any>;
    };
    applied: boolean;
    summary: {
      new: number;
      updated: number;
      deleted: number;
      errors: number;
    };
  };
}

interface StatsResult {
  status: string;
  timestamp: string;
  statistics: {
    total_papers_tracked: number;
    active_papers: number;
    deleted_papers: number;
    categories_tracked: number;
    top_categories: Array<[string, number]>;
    recent_changes_week: any;
    state_file_path: string;
  };
}

interface ExtractionResult {
  status: string;
  message: string;
  processed_count: number;
  results: Array<{
    paper_id: string;
    title: string;
    extraction_status: string;
    features: {
      entities?: any;
      topics?: string[] | { error: string };
      keyphrases?: string[] | { error: string };
      summary?: string | { error: string };
      citations?: any;
    };
    error?: string;
  }>;
}

export default function ArxivManagement() {
  const [isTracking, setIsTracking] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [trackingResult, setTrackingResult] = useState<TrackResult | null>(null);
  const [stats, setStats] = useState<StatsResult | null>(null);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');

  // Form states
  const [selectedCategories, setSelectedCategories] = useState<string[]>(['cs.AI', 'cs.LG', 'cs.CV', 'quant-ph']);
  const [daysBack, setDaysBack] = useState(1);
  const [maxResults, setMaxResults] = useState(50);
  const [updateDatabase, setUpdateDatabase] = useState(true);
  const [extractEntities, setExtractEntities] = useState(true);
  const [downloadPdfs, setDownloadPdfs] = useState(false);

  // Extraction form states
  const [extractPaperIds, setExtractPaperIds] = useState('');
  const [extractTopics, setExtractTopics] = useState(true);
  const [extractKeyphrases, setExtractKeyphrases] = useState(true);
  const [extractCitations, setExtractCitations] = useState(true);
  const [extractSummaries, setExtractSummaries] = useState(true);
  const [updateKG, setUpdateKG] = useState(true);

  const popularCategories = [
    'cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'cs.RO',
    'quant-ph', 'stat.ML', 'math.OC', 'physics.data-an', 'eess.IV'
  ];

  // Handle tracking changes
  const handleTrackChanges = async () => {
    setIsTracking(true);
    setMessage(`Tracking changes for ${selectedCategories.length} categories...`);
    setProgress(10);

    try {
      setProgress(30);
      const result = await apiClient.post<TrackResult>('/arxiv/tracking/track-categories', {
        categories: selectedCategories,
        days_back: daysBack,
        update_database: updateDatabase
      });

      setProgress(70);
      setTrackingResult(result);

      if (result.result.applied && updateDatabase) {
        setMessage(`✅ Tracking completed! Database updated with ${result.result.summary.new} new papers.`);
      } else if (!result.result.applied && updateDatabase) {
        setMessage(`⚠️ Found ${result.result.summary.new} new papers but database update is disabled.`);
      } else {
        setMessage(`✅ Tracking completed! Found ${result.result.summary.new} new, ${result.result.summary.updated} updated, ${result.result.summary.deleted} deleted papers.`);
      }
      setProgress(100);

      // Refresh stats
      await fetchStats();
    } catch (error: any) {
      console.error('Tracking failed:', error);
      setProgress(0);
      if (error.response?.status === 401) {
        setMessage('❌ Authentication failed. Please refresh the page and try again.');
      } else {
        setMessage(`❌ Tracking failed: ${error.response?.data?.detail || error.message}`);
      }
    } finally {
      setIsTracking(false);
    }
  };

  // Handle ingestion
  const handleIngestPapers = async () => {
    setIsIngesting(true);
    setMessage('Ingesting papers...');
    setProgress(0);

    try {
      // This would need to be implemented in the backend
      // For now, we'll show a placeholder
      setMessage('Ingestion feature coming soon to API');
      setProgress(50);

      setTimeout(() => {
        setProgress(100);
        setIsIngesting(false);
      }, 2000);
    } catch (error: any) {
      console.error('Ingestion failed:', error);
      setMessage(`Ingestion failed: ${error.message}`);
      setIsIngesting(false);
    }
  };

  // Fetch statistics
  const fetchStats = async () => {
    try {
      const result = await apiClient.get<StatsResult>('/arxiv/tracking/stats');
      setStats(result);
    } catch (error: any) {
      console.error('Failed to fetch stats:', error);
    }
  };

  // Clean up old state
  const handleCleanup = async () => {
    try {
      await apiClient.post('/arxiv/tracking/cleanup', null, {
        params: { days: 90 }
      });
      setMessage('Cleanup completed');
      await fetchStats();
    } catch (error: any) {
      console.error('Cleanup failed:', error);
      setMessage(`Cleanup failed: ${error.message}`);
    }
  };

  // Handle feature extraction
  const handleExtractFeatures = async () => {
    setIsExtracting(true);
    setMessage('Extracting features...');
    setProgress(0);

    try {
      // Parse paper IDs
      const paperIds = extractPaperIds
        .split('\n')
        .map(id => id.trim())
        .filter(id => id.length > 0);

      if (paperIds.length === 0) {
        setMessage('Please enter at least one paper ID');
        setIsExtracting(false);
        return;
      }

      const result = await apiClient.post<ExtractionResult>('/arxiv/extraction/extract-features', {
        paper_ids: paperIds,
        extract_entities: extractEntities,
        extract_topics: extractTopics,
        extract_citations: extractCitations,
        extract_keyphrases: extractKeyphrases,
        extract_summaries: extractSummaries,
        update_knowledge_graph: updateKG
      });

      setExtractionResult(result);
      setMessage(`Successfully extracted features from ${result.processed_count} papers`);
      setProgress(100);
    } catch (error: any) {
      console.error('Extraction failed:', error);
      setMessage(`Extraction failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  // Handle bulk extraction
  const handleBulkExtract = async () => {
    setIsExtracting(true);
    setMessage('Bulk extracting features...');
    setProgress(0);

    try {
      const result = await apiClient.post<any>('/arxiv/extraction/bulk-extract', {
        categories: selectedCategories,
        days_back: daysBack,
        max_papers: maxResults,
        extraction_options: {
          extract_entities: extractEntities,
          extract_topics: extractTopics,
          extract_citations: extractCitations,
          extract_keyphrases: extractKeyphrases,
          extract_summaries: extractSummaries,
          update_knowledge_graph: updateKG
        }
      });

      setExtractionResult({
        status: result.status,
        message: result.message,
        processed_count: result.papers_processed,
        results: result.results || []
      });

      setMessage(`Bulk extraction completed: ${result.papers_processed} papers processed`);
      setProgress(100);
    } catch (error: any) {
      console.error('Bulk extraction failed:', error);
      setMessage(`Bulk extraction failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  // Handle local PDF extraction
  const handleExtractLocalPdfs = async () => {
    setIsExtracting(true);
    setMessage('Extracting features from local PDF files...');
    setProgress(0);

    try {
      const response = await apiClient.postWithLongTimeout('/arxiv/local/extract-local-features', {
        paper_ids: null, // Process all files
        extract_entities: extractEntities,
        extract_topics: extractTopics,
        extract_citations: extractCitations,
        extract_keyphrases: extractKeyphrases,
        extract_summaries: extractSummaries,
        process_full_content: true,
        update_knowledge_graph: updateKG
      });

        // The response is direct, not wrapped in .data
      const data = response.data || response;

      setExtractionResult({
        status: data.status,
        message: data.message,
        processed_count: data.processed_count,
        results: data.results || []
      });

      setMessage(`Successfully extracted features from ${data.processed_count} local PDF files`);
      setProgress(100);
    } catch (error: any) {
      console.error('Local PDF extraction failed:', error);

      // Check if it's an authentication error
      if (error.status === 401 || error.response?.status === 401) {
        setMessage('Authentication expired. Please refresh the page and log in again.');
      } else if (error.status === 403 || error.response?.status === 403) {
        setMessage('Access denied. Please check your permissions and try again.');
      } else {
        setMessage(`Local PDF extraction failed: ${error.response?.data?.detail || error.message || error.toString()}`);
      }
    } finally {
      setIsExtracting(false);
    }
  };

  // Initial stats fetch
  React.useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">ArXiv Management</h1>
          <p className="text-muted-foreground">
            Track and ingest arXiv papers with knowledge graph integration
          </p>
        </div>
      </div>

      <Tabs defaultValue="tracking" className="space-y-4">
        <TabsList>
          <TabsTrigger value="tracking">Track Changes</TabsTrigger>
          <TabsTrigger value="ingest">Ingest Papers</TabsTrigger>
          <TabsTrigger value="extract">Extract Features</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
        </TabsList>

        <TabsContent value="tracking" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Track ArXiv Changes
              </CardTitle>
              <CardDescription>
                Detect new, updated, and deleted papers in selected categories
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Categories Selection */}
              <div>
                <Label>Categories to Track</Label>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-2">
                  {popularCategories.map((category) => (
                    <div key={category} className="flex items-center space-x-2">
                      <Switch
                        checked={selectedCategories.includes(category)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedCategories([...selectedCategories, category]);
                          } else {
                            setSelectedCategories(selectedCategories.filter(c => c !== category));
                          }
                        }}
                      />
                      <Label className="text-sm">{category}</Label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Days Back */}
              <div>
                <Label>Days to look back: {daysBack}</Label>
                <Slider
                  value={[daysBack]}
                  onValueChange={(value) => setDaysBack(value[0])}
                  max={30}
                  min={1}
                  step={1}
                  className="mt-2"
                />
              </div>

              {/* Update Database */}
              <div className="flex items-center space-x-2">
                <Switch
                  id="update-db"
                  checked={updateDatabase}
                  onCheckedChange={setUpdateDatabase}
                />
                <Label htmlFor="update-db">Update database with changes</Label>
              </div>

              {/* Action Button */}
              <div className="flex items-center gap-4">
                <Button
                  onClick={handleTrackChanges}
                  disabled={isTracking || selectedCategories.length === 0}
                  className="w-full sm:w-auto"
                >
                  {isTracking ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Tracking...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Track Changes
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleCleanup}
                  className="w-full sm:w-auto"
                >
                  Cleanup Old State
                </Button>
              </div>

              {/* Progress */}
              {(isTracking || message) && (
                <div className="space-y-2">
                  <Progress value={progress} />
                  <p className="text-sm text-muted-foreground">{message}</p>
                </div>
              )}

              {/* Results */}
              {trackingResult && (
                <div className="space-y-4">
                  <Alert>
                    <CheckCircle className="h-4 w-4" />
                    <AlertDescription>
                      {trackingResult.result.applied ? (
                        <span>
                          ✅ Successfully tracked and updated database!
                          Found {trackingResult.result.papers_found} papers with {trackingResult.result.changes_detected} changes.
                        </span>
                      ) : (
                        <span>
                          ℹ️ Tracking completed (read-only).
                          Found {trackingResult.result.papers_found} papers with {trackingResult.result.changes_detected} changes.
                          Enable "Update database" to apply changes.
                        </span>
                      )}
                    </AlertDescription>
                  </Alert>

                  <div className="grid grid-cols-3 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-600">
                          {trackingResult.result.summary.new}
                        </div>
                        <p className="text-sm text-muted-foreground">New Papers</p>
                        <p className="text-xs text-gray-500 mt-1">
                          Categories: {trackingResult.result.categories.join(', ')}
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-blue-600">
                          {trackingResult.result.summary.updated}
                        </div>
                        <p className="text-sm text-muted-foreground">Updated</p>
                        <p className="text-xs text-gray-500 mt-1">
                          Last {trackingResult.result.period_days} days
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-600">
                          {trackingResult.result.summary.deleted}
                        </div>
                        <p className="text-sm text-muted-foreground">Deleted</p>
                      </CardContent>
                    </Card>
                  </div>

                  {trackingResult.result.applied && (
                    <Alert className="bg-blue-50 border-blue-200">
                      <Database className="h-4 w-4 text-blue-600" />
                      <AlertDescription className="text-blue-800">
                        Papers have been added to PostgreSQL and entities/relationships have been extracted to Neo4j knowledge graph.
                        Visit <a href="http://localhost:7474/browser/" target="_blank" rel="noopener noreferrer" className="underline font-medium">Neo4j Browser</a> to explore the knowledge graph.
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ingest" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Ingest ArXiv Papers
              </CardTitle>
              <CardDescription>
                Search and ingest papers from arXiv with knowledge graph extraction
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Search Configuration */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="search-query">Search Query</Label>
                  <input
                    id="search-query"
                    type="text"
                    placeholder="e.g., quantum computing"
                    className="w-full mt-1 px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <Label htmlFor="max-results">Max Results: {maxResults}</Label>
                  <Slider
                    id="max-results"
                    value={[maxResults]}
                    onValueChange={(value) => setMaxResults(value[0])}
                    max={100}
                    min={1}
                    step={1}
                    className="mt-2"
                  />
                </div>
              </div>

              {/* Options */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="extract-entities"
                    checked={extractEntities}
                    onCheckedChange={setExtractEntities}
                  />
                  <Label htmlFor="extract-entities">Extract entities to knowledge graph</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="download-pdfs"
                    checked={downloadPdfs}
                    onCheckedChange={setDownloadPdfs}
                  />
                  <Label htmlFor="download-pdfs">Download PDF files</Label>
                </div>
              </div>

              {/* Action Button */}
              <Button
                onClick={handleIngestPapers}
                disabled={isIngesting}
                className="w-full"
              >
                {isIngesting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Ingesting...
                  </>
                ) : (
                  <>
                    <Database className="mr-2 h-4 w-4" />
                    Start Ingestion
                  </>
                )}
              </Button>

              {/* Progress */}
              {(isIngesting || message) && (
                <div className="space-y-2">
                  <Progress value={progress} />
                  <p className="text-sm text-muted-foreground">{message}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="extract" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Extract Features from Papers
              </CardTitle>
              <CardDescription>
                Extract entities, topics, key phrases, summaries, and citations from ArXiv papers
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Paper IDs Input */}
              <div>
                <Label htmlFor="paper-ids">Paper IDs (one per line)</Label>
                <textarea
                  id="paper-ids"
                  placeholder="e.g.,&#10;2301.07041&#10;2302.08869&#10;2303.12345"
                  value={extractPaperIds}
                  onChange={(e) => setExtractPaperIds(e.target.value)}
                  className="w-full mt-1 px-3 py-2 border rounded-md h-32 font-mono text-sm"
                />
              </div>

              {/* Extraction Options */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium">Features to Extract:</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="extract-entities-feat"
                      checked={extractEntities}
                      onCheckedChange={setExtractEntities}
                    />
                    <Label htmlFor="extract-entities-feat" className="flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Entities
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="extract-topics-feat"
                      checked={extractTopics}
                      onCheckedChange={setExtractTopics}
                    />
                    <Label htmlFor="extract-topics-feat" className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      Topics
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="extract-keyphrases-feat"
                      checked={extractKeyphrases}
                      onCheckedChange={setExtractKeyphrases}
                    />
                    <Label htmlFor="extract-keyphrases-feat" className="flex items-center gap-2">
                      <Hash className="h-4 w-4" />
                      Key Phrases
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="extract-citations-feat"
                      checked={extractCitations}
                      onCheckedChange={setExtractCitations}
                    />
                    <Label htmlFor="extract-citations-feat" className="flex items-center gap-2">
                      <Link2 className="h-4 w-4" />
                      Citations
                    </Label>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="extract-summaries-feat"
                    checked={extractSummaries}
                    onCheckedChange={setExtractSummaries}
                  />
                  <Label htmlFor="extract-summaries-feat">Generate Summaries</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="update-kg-feat"
                    checked={updateKG}
                    onCheckedChange={setUpdateKG}
                  />
                  <Label htmlFor="update-kg-feat">Update Knowledge Graph</Label>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-4">
                <Button
                  onClick={handleExtractFeatures}
                  disabled={isExtracting || extractPaperIds.trim().length === 0}
                  className="w-full sm:w-auto"
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Brain className="mr-2 h-4 w-4" />
                      Extract Features
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleBulkExtract}
                  disabled={isExtracting}
                  className="w-full sm:w-auto"
                >
                  Bulk Extract from Categories
                </Button>

                <Button
                  variant="secondary"
                  onClick={handleExtractLocalPdfs}
                  disabled={isExtracting}
                  className="w-full sm:w-auto"
                >
                  Extract from Local PDFs
                </Button>
              </div>

              {/* Progress */}
              {(isExtracting || message) && (
                <div className="space-y-2">
                  <Progress value={progress} />
                  <p className="text-sm text-muted-foreground">{message}</p>
                </div>
              )}

              {/* Extraction Results */}
              {extractionResult && (
                <div className="space-y-4">
                  <Alert>
                    <CheckCircle className="h-4 w-4" />
                    <AlertDescription>
                      {extractionResult.message}
                    </AlertDescription>
                  </Alert>

                  {/* Results Grid */}
                  <div className="grid grid-cols-1 gap-4">
                    {extractionResult.results.map((result, index) => (
                      <Card key={index}>
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-sm truncate flex-1 mr-2">
                              {result.title}
                            </CardTitle>
                            <Badge variant={result.extraction_status === 'completed' ? 'default' : 'destructive'}>
                              {result.extraction_status}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{result.paper_id}</p>
                        </CardHeader>
                        {result.error && (
                          <CardContent className="pt-0">
                            <Alert>
                              <AlertDescription className="text-xs">
                                Error: {result.error}
                              </AlertDescription>
                            </Alert>
                          </CardContent>
                        )}
                        {result.extraction_status === 'completed' && (
                          <CardContent className="pt-0">
                            <div className="space-y-2">
                              {result.features.topics && Array.isArray(result.features.topics) && (
                                <div>
                                  <p className="text-xs font-medium mb-1">Topics:</p>
                                  <div className="flex flex-wrap gap-1">
                                    {result.features.topics.map((topic, i) => (
                                      <Badge key={i} variant="secondary" className="text-xs">
                                        {topic}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {result.features.keyphrases && Array.isArray(result.features.keyphrases) && (
                                <div>
                                  <p className="text-xs font-medium mb-1">Key Phrases:</p>
                                  <p className="text-xs text-muted-foreground truncate">
                                    {result.features.keyphrases.join(', ')}
                                  </p>
                                </div>
                              )}
                              {result.features.summary && typeof result.features.summary === 'string' && (
                                <div>
                                  <p className="text-xs font-medium mb-1">Summary:</p>
                                  <p className="text-xs text-muted-foreground line-clamp-3">
                                    {result.features.summary}
                                  </p>
                                </div>
                              )}
                            </div>
                          </CardContent>
                        )}
                        {result.extraction_status === 'completed' && (
                          <CardContent className="pt-0">
                            <div className="space-y-2">
                              {result.features.topics && !Array.isArray(result.features.topics) && (
                                <div className="text-xs text-red-500">
                                  Topics: {(result.features.topics as { error: string }).error}
                                </div>
                              )}
                              {result.features.keyphrases && !Array.isArray(result.features.keyphrases) && (
                                <div className="text-xs text-red-500">
                                  Key Phrases: {(result.features.keyphrases as { error: string }).error}
                                </div>
                              )}
                              {result.features.summary && typeof result.features.summary !== 'string' && (
                                <div className="text-xs text-red-500">
                                  Summary: {(result.features.summary as { error: string }).error}
                                </div>
                              )}
                            </div>
                          </CardContent>
                        )}
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stats" className="space-y-4">
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold">
                    {stats.statistics.total_papers_tracked}
                  </div>
                  <p className="text-sm text-muted-foreground">Total Papers Tracked</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.statistics.active_papers}
                  </div>
                  <p className="text-sm text-muted-foreground">Active Papers</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-blue-600">
                    {stats.statistics.categories_tracked}
                  </div>
                  <p className="text-sm text-muted-foreground">Categories Tracked</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-orange-600">
                    {stats.statistics.recent_changes_week.new || 0}
                  </div>
                  <p className="text-sm text-muted-foreground">New This Week</p>
                </CardContent>
              </Card>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Top Categories</CardTitle>
            </CardHeader>
            <CardContent>
              {stats?.statistics.top_categories?.map(([category, count]) => (
                <div key={category} className="flex items-center justify-between py-2">
                  <Badge variant="secondary">{category}</Badge>
                  <span className="text-sm font-medium">{count} papers</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}