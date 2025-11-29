'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useDocuments } from '@/hooks/useDocuments';
import { useAuth } from '@/hooks/useAuth';
import { DocumentCard } from '@/components/documents/DocumentCard';
import { EnhancedDocumentUploadZone } from '@/components/documents/EnhancedDocumentUploadZone';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Upload, 
  Search, 
  MessageSquare, 
  FileText, 
  Database, 
  Network, 
  Zap,
  ArrowRight,
  X,
  CheckCircle2,
  FolderOpen,
  Bot,
  Sparkles,
} from 'lucide-react';

export default function HomePage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [showUploadZone, setShowUploadZone] = useState(false);
  const [uploadResults, setUploadResults] = useState<Array<{ id: string, result: any }>>([]);

  const { documents, loading, error } = useDocuments({
    initialPageSize: 5,
    autoFetch: isAuthenticated && !authLoading,
  });

  const handleUploadComplete = (documentId: string, result: any) => {
    setUploadResults(prev => [...prev, { id: documentId, result }]);
    setShowUploadZone(false);
  };

  const handleUploadError = (error: string, file: any) => {
    console.error('Upload error:', error, file);
  };

  const features = [
    {
      icon: Search,
      title: 'Semantic Search',
      description: 'AI-powered search across all your documents',
      href: '/search',
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      icon: Bot,
      title: 'AI Chat',
      description: 'Chat with AI models running in your browser',
      href: '/llm-chat',
      color: 'text-amber-500',
      bgColor: 'bg-amber-500/10',
    },
    {
      icon: FileText,
      title: 'Documents',
      description: 'Manage your document library',
      href: '/documents/upload',
      color: 'text-green-500',
      bgColor: 'bg-green-500/10',
    },
  ];

  const stats = [
    { label: 'Backend API', status: 'online', icon: Zap },
    { label: 'Database', status: 'online', icon: Database },
    { label: 'Vector Store', status: 'online', icon: Sparkles },
    { label: 'Knowledge Graph', status: 'online', icon: Network },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-border">
        {/* Background Effects */}
        <div className="absolute inset-0 bg-gradient-to-b from-amber-500/5 via-background to-background" />
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-amber-500/20 rounded-full blur-[120px] opacity-60" />
        <div className="absolute top-20 right-1/4 w-[400px] h-[400px] bg-orange-500/15 rounded-full blur-[100px] opacity-50" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,var(--background)_70%)]" />
        
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--border))_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--border))_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black_20%,transparent_80%)] opacity-30" />
        
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20">
          <div className="text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-600 text-sm font-medium mb-6">
              <Sparkles className="w-4 h-4" />
              Enterprise RAG System
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            </div>
            
            {/* Heading */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground tracking-tight leading-[1.1] mb-6">
              Transform Documents into
              <br />
              <span className="bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 bg-clip-text text-transparent">
                Actionable Knowledge
              </span>
            </h1>
            
            {/* Description */}
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-8 leading-relaxed">
              Upload any document format, extract entities with AI, build knowledge graphs, 
              and search with semantic understanding.
            </p>
            
            {/* CTAs */}
            <div className="flex flex-wrap justify-center gap-4 mb-12">
              <Button 
                size="lg" 
                onClick={() => setShowUploadZone(true)}
                className="bg-amber-500 hover:bg-amber-600 text-white h-12 px-6 text-base shadow-lg shadow-amber-500/25 hover:shadow-amber-500/40 transition-all"
              >
                <Upload className="w-5 h-5 mr-2" />
                Upload Documents
              </Button>
              <Link href="/search">
                <Button size="lg" variant="outline" className="h-12 px-6 text-base border-border hover:bg-muted">
                  <Search className="w-5 h-5 mr-2" />
                  Search Knowledge Base
                </Button>
              </Link>
            </div>
            
            {/* Hero Stats */}
            <div className="flex flex-wrap justify-center gap-8 md:gap-12">
              <div className="text-center">
                <div className="text-2xl md:text-3xl font-bold text-foreground">PDF, DOCX</div>
                <div className="text-sm text-muted-foreground mt-1">Document Formats</div>
              </div>
              <div className="hidden sm:block w-px h-12 bg-border" />
              <div className="text-center">
                <div className="text-2xl md:text-3xl font-bold text-foreground">Images</div>
                <div className="text-sm text-muted-foreground mt-1">OCR Extraction</div>
              </div>
              <div className="hidden sm:block w-px h-12 bg-border" />
              <div className="text-center">
                <div className="text-2xl md:text-3xl font-bold text-foreground">Audio/Video</div>
                <div className="text-sm text-muted-foreground mt-1">Transcription</div>
              </div>
              <div className="hidden sm:block w-px h-12 bg-border" />
              <div className="text-center">
                <div className="text-2xl md:text-3xl font-bold text-amber-500">AI-Powered</div>
                <div className="text-sm text-muted-foreground mt-1">Semantic Search</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {features.map((feature) => (
            <Link key={feature.title} href={feature.href}>
              <Card className="h-full border-border hover:border-amber-500/50 hover:shadow-md transition-all cursor-pointer group">
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-lg ${feature.bgColor} flex items-center justify-center shrink-0`}>
                      <feature.icon className={`w-5 h-5 ${feature.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-foreground group-hover:text-amber-600 transition-colors">
                        {feature.title}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {feature.description}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-amber-500 group-hover:translate-x-1 transition-all shrink-0 mt-1" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Upload Section */}
          <div className="lg:col-span-2">
            <Card className="h-full border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Upload className="w-5 h-5 text-amber-500" />
                  Quick Upload
                </CardTitle>
                <CardDescription>
                  Drag and drop files to get started
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div 
                  className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:border-amber-500/50 hover:bg-amber-500/5 transition-all cursor-pointer group"
                  onClick={() => setShowUploadZone(true)}
                >
                  <div className="w-12 h-12 mx-auto rounded-xl bg-muted flex items-center justify-center mb-4 group-hover:bg-amber-500/10 group-hover:scale-110 transition-all">
                    <Upload className="w-6 h-6 text-muted-foreground group-hover:text-amber-500" />
                  </div>
                  <p className="text-sm font-medium text-foreground mb-1">
                    Drop files here
                  </p>
                  <p className="text-xs text-muted-foreground mb-4">
                    PDF, TXT, Images, Audio, Video
                  </p>
                  <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
                    Browse Files
                  </Button>
                </div>
                <div className="mt-4 pt-4 border-t border-border">
                  <Link href="/documents/upload" className="text-sm text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1">
                    Advanced upload options
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Documents */}
          <div className="lg:col-span-3">
            <Card className="h-full border-border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <FolderOpen className="w-5 h-5 text-amber-500" />
                    Recent Documents
                  </CardTitle>
                  <CardDescription>
                    Your latest uploaded files
                  </CardDescription>
                </div>
                {documents.length > 0 && (
                  <Link href="/documents/upload">
                    <Button variant="ghost" size="sm" className="text-amber-600 hover:text-amber-700 hover:bg-amber-500/10">
                      View all
                      <ArrowRight className="w-3 h-3 ml-1" />
                    </Button>
                  </Link>
                )}
              </CardHeader>
              <CardContent>
                {authLoading || loading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="text-center">
                      <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
                      <p className="text-sm text-muted-foreground mt-3">
                        {authLoading ? 'Checking authentication...' : 'Loading documents...'}
                      </p>
                    </div>
                  </div>
                ) : !isAuthenticated ? (
                  <div className="rounded-xl bg-muted/30 p-8 text-center">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-muted flex items-center justify-center mb-4">
                      <FileText className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-foreground mb-1">Sign in to view documents</p>
                    <p className="text-sm text-muted-foreground mb-4">
                      Access your document library and search history
                    </p>
                    <div className="flex gap-2 justify-center">
                      <Link href="/login">
                        <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
                          Sign In
                        </Button>
                      </Link>
                      <Link href="/register">
                        <Button size="sm" variant="outline">
                          Create Account
                        </Button>
                      </Link>
                    </div>
                  </div>
                ) : error ? (
                  <div className="rounded-xl bg-destructive/10 p-6 text-center border border-destructive/20">
                    <p className="text-sm font-medium text-destructive mb-1">Error loading documents</p>
                    <p className="text-xs text-destructive/80">{error}</p>
                  </div>
                ) : documents.length === 0 ? (
                  <div className="rounded-xl border-2 border-dashed border-border p-8 text-center">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-muted flex items-center justify-center mb-4">
                      <FileText className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-foreground mb-1">No documents yet</p>
                    <p className="text-sm text-muted-foreground">
                      Upload your first document to get started
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {documents.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        document={doc}
                        onSelect={() => {}}
                        selected={false}
                      />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* System Status */}
        <Card className="mt-6 border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              System Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {stats.map((stat) => (
                <div 
                  key={stat.label}
                  className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border"
                >
                  <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
                    <stat.icon className="w-4 h-4 text-green-500" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                    <p className="text-sm font-medium text-green-600 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                      Online
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Upload Zone Modal */}
      {showUploadZone && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-2xl border border-border max-w-4xl w-full max-h-[90vh] overflow-y-auto animate-in zoom-in-95 fade-in duration-200">
            <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Upload className="w-5 h-5 text-amber-500" />
                Upload Documents
              </h2>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowUploadZone(false)}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="p-6">
              <EnhancedDocumentUploadZone
                onUploadComplete={handleUploadComplete}
                onUploadError={handleUploadError}
                maxFiles={10}
              />
            </div>
          </div>
        </div>
      )}

      {/* Upload Success Toast */}
      {uploadResults.length > 0 && (
        <div className="fixed bottom-6 right-6 max-w-sm z-50 animate-in slide-in-from-bottom-4 duration-300">
          <Card className="border-green-500/20 bg-green-500/10 shadow-lg">
            <CardContent className="p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-700 dark:text-green-400">
                  Upload Complete
                </p>
                <p className="text-sm text-green-600 dark:text-green-500 mt-0.5">
                  {uploadResults.length} document{uploadResults.length > 1 ? 's' : ''} uploaded
                </p>
                <button
                  onClick={() => setUploadResults([])}
                  className="text-xs font-medium text-green-700 dark:text-green-400 hover:underline mt-2"
                >
                  Dismiss
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
