import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  PlayIcon,
  PauseIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface MultimodalViewerProps {
  document: {
    id: string;
    title: string;
    filename: string;
    file_type: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
    file_size: number;
    thumbnail_url?: string;
    extracted_text_preview?: string;
    metadata?: Record<string, any>;
    processing_status: string;
    processing_completed_at?: string;
  };
  className?: string;
  showControls?: boolean;
  allowDownload?: boolean;
  allowFullscreen?: boolean;
  maxHeight?: string;
}

interface DocumentPage {
  number: number;
  content: string;
  imageUrl?: string;
}

interface AudioMetadata {
  duration: number;
  waveform?: number[];
  transcript?: string;
}

interface VideoMetadata {
  duration: number;
  frames?: Array<{
    timestamp: number;
    imageUrl: string;
  }>;
  transcript?: string;
}

interface ImageViewerState {
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  dragStart: { x: number; y: number };
}

export const MultimodalViewer: React.FC<MultimodalViewerProps> = ({
  document,
  className,
  showControls = true,
  allowDownload = true,
  allowFullscreen = true,
  maxHeight = '600px',
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [audioMetadata, setAudioMetadata] = useState<AudioMetadata | null>(null);
  const [videoMetadata, setVideoMetadata] = useState<VideoMetadata | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  // Image viewer state
  const [imageState, setImageState] = useState<ImageViewerState>({
    scale: 1,
    position: { x: 0, y: 0 },
    isDragging: false,
    dragStart: { x: 0, y: 0 },
  });

  // Refs
  const audioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const imageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Format time
  const formatTime = (seconds: number): string => {
    if (isNaN(seconds)) return '0:00';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  // Load document content based on type
  useEffect(() => {
    const loadDocument = async () => {
      setIsLoading(true);
      setError(null);

      try {
        switch (document.file_type) {
          case 'pdf':
            await loadPDFDocument();
            break;
          case 'txt':
            await loadTextDocument();
            break;
          case 'jpg':
          case 'png':
            await loadImageDocument();
            break;
          case 'mp3':
            await loadAudioDocument();
            break;
          case 'mp4':
            await loadVideoDocument();
            break;
          default:
            throw new Error('Unsupported document type');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setIsLoading(false);
      }
    };

    loadDocument();
  }, [document.id, document.file_type]);

  // Load PDF document
  const loadPDFDocument = async () => {
    // Mock PDF loading - in real implementation, use PDF.js or similar
    const mockPages: DocumentPage[] = [
      {
        number: 1,
        content: document.extracted_text_preview || 'PDF content would be displayed here...',
      },
    ];
    setPages(mockPages);
    setTotalPages(mockPages.length);
  };

  // Load text document
  const loadTextDocument = async () => {
    // Mock text loading - in real implementation, fetch the actual content
    const mockPages: DocumentPage[] = [
      {
        number: 1,
        content: document.extracted_text_preview || 'Text content would be displayed here...',
      },
    ];
    setPages(mockPages);
    setTotalPages(mockPages.length);
  };

  // Load image document
  const loadImageDocument = async () => {
    // Image will be loaded via img tag
    setImageState({ scale: 1, position: { x: 0, y: 0 }, isDragging: false, dragStart: { x: 0, y: 0 } });
  };

  // Load audio document
  const loadAudioDocument = async () => {
    // Mock audio metadata - in real implementation, fetch from API
    const mockAudioMetadata: AudioMetadata = {
      duration: 180, // 3 minutes
      transcript: document.extracted_text_preview,
    };
    setAudioMetadata(mockAudioMetadata);
    setDuration(mockAudioMetadata.duration);
  };

  // Load video document
  const loadVideoDocument = async () => {
    // Mock video metadata - in real implementation, fetch from API
    const mockVideoMetadata: VideoMetadata = {
      duration: 300, // 5 minutes
      transcript: document.extracted_text_preview,
    };
    setVideoMetadata(mockVideoMetadata);
    setDuration(mockVideoMetadata.duration);
  };

  // Audio controls
  const togglePlayPause = useCallback(() => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  }, [isPlaying]);

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  }, []);

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  }, []);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  }, [isMuted]);

  // Image viewer controls
  const handleImageZoom = useCallback((delta: number) => {
    setImageState(prev => ({
      ...prev,
      scale: Math.max(0.1, Math.min(5, prev.scale + delta)),
    }));
  }, []);

  const handleImageReset = useCallback(() => {
    setImageState({
      scale: 1,
      position: { x: 0, y: 0 },
      isDragging: false,
      dragStart: { x: 0, y: 0 },
    });
  }, []);

  const handleImageMouseDown = useCallback((e: React.MouseEvent) => {
    if (imageState.scale > 1) {
      setImageState(prev => ({
        ...prev,
        isDragging: true,
        dragStart: { x: e.clientX - prev.position.x, y: e.clientY - prev.position.y },
      }));
    }
  }, [imageState.scale]);

  const handleImageMouseMove = useCallback((e: React.MouseEvent) => {
    if (imageState.isDragging) {
      setImageState(prev => ({
        ...prev,
        position: {
          x: e.clientX - prev.dragStart.x,
          y: e.clientY - prev.dragStart.y,
        },
      }));
    }
  }, [imageState.isDragging]);

  const handleImageMouseUp = useCallback(() => {
    setImageState(prev => ({ ...prev, isDragging: false }));
  }, []);

  // Page navigation
  const goToPage = useCallback((page: number) => {
    setCurrentPage(Math.max(1, Math.min(totalPages, page)));
  }, [totalPages]);

  const goToPreviousPage = useCallback(() => {
    goToPage(currentPage - 1);
  }, [currentPage, goToPage]);

  const goToNextPage = useCallback(() => {
    goToPage(currentPage + 1);
  }, [currentPage, goToPage]);

  // Download document
  const handleDownload = useCallback(() => {
    // Mock download - in real implementation, fetch the actual file
    const link = window.document.createElement('a');
    link.href = '#'; // Would be actual file URL
    link.download = document.filename;
    link.click();
  }, [document.filename]);

  // Share document
  const handleShare = useCallback(async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: document.title,
          text: `Check out this document: ${document.title}`,
          url: window.location.href,
        });
      } catch (err) {
        console.log('Share cancelled or failed');
      }
    } else {
      // Fallback - copy to clipboard
      navigator.clipboard.writeText(window.location.href);
    }
  }, [document.title]);

  // Get document type icon
  const getDocumentIcon = () => {
    switch (document.file_type) {
      case 'pdf':
      case 'txt':
        return <DocumentTextIcon className="h-6 w-6" />;
      case 'jpg':
      case 'png':
        return <PhotoIcon className="h-6 w-6" />;
      case 'mp3':
        return <MusicalNoteIcon className="h-6 w-6" />;
      case 'mp4':
        return <VideoCameraIcon className="h-6 w-6" />;
      default:
        return <DocumentTextIcon className="h-6 w-6" />;
    }
  };

  // Get document type name
  const getDocumentTypeName = () => {
    switch (document.file_type) {
      case 'pdf':
        return 'PDF Document';
      case 'txt':
        return 'Text Document';
      case 'jpg':
      case 'png':
        return 'Image';
      case 'mp3':
        return 'Audio File';
      case 'mp4':
        return 'Video File';
      default:
        return 'Document';
    }
  };

  if (error) {
    return (
      <div className={cn("flex flex-col items-center justify-center p-8 bg-card border rounded-lg", className)}>
        <div className="text-center">
          <p className="text-red-600 mb-4">Failed to load document</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
        <div className="flex items-center space-x-3">
          {getDocumentIcon()}
          <div>
            <h3 className="font-medium text-foreground">{document.title}</h3>
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <span>{getDocumentTypeName()}</span>
              <span>•</span>
              <span>{formatFileSize(document.file_size)}</span>
              {document.processing_completed_at && (
                <>
                  <span>•</span>
                  <span>Processed {new Date(document.processing_completed_at).toLocaleDateString()}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {showControls && (
          <div className="flex items-center space-x-2">
            {allowDownload && (
              <Button variant="outline" size="sm" onClick={handleDownload}>
                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                Download
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={handleShare}>
              Share
            </Button>
            {allowFullscreen && (
              <Button variant="outline" size="sm" onClick={() => setIsFullscreen(!isFullscreen)}>
                {isFullscreen ? (
                  <ArrowsPointingInIcon className="h-4 w-4" />
                ) : (
                  <ArrowsPointingOutIcon className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Document Content */}
      <div className="bg-card border rounded-lg overflow-hidden" style={{ maxHeight }}>
        {isLoading ? (
          <div className="flex items-center justify-center p-16">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading document...</p>
            </div>
          </div>
        ) : (
          <>
            {/* PDF/Text Viewer */}
            {(document.file_type === 'pdf' || document.file_type === 'txt') && (
              <div className="flex flex-col h-full">
                {/* Page Navigation */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between p-4 border-b">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goToPreviousPage}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeftIcon className="h-4 w-4 mr-2" />
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {currentPage} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={goToNextPage}
                      disabled={currentPage === totalPages}
                    >
                      Next
                      <ChevronRightIcon className="h-4 w-4 ml-2" />
                    </Button>
                  </div>
                )}

                {/* Content */}
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="prose max-w-none">
                    {pages[currentPage - 1]?.content || 'No content available'}
                  </div>
                </div>
              </div>
            )}

            {/* Image Viewer */}
            {(document.file_type === 'jpg' || document.file_type === 'png') && (
              <div className="relative flex items-center justify-center p-8 overflow-hidden">
                {/* Zoom Controls */}
                <div className="absolute top-4 right-4 flex flex-col space-y-2 z-10">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleImageZoom(0.1)}
                  >
                    <MagnifyingGlassPlusIcon className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleImageZoom(-0.1)}
                  >
                    <MagnifyingGlassMinusIcon className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleImageReset}
                  >
                    Reset
                  </Button>
                </div>

                {/* Image */}
                <div
                  ref={imageRef}
                  className="cursor-move"
                  onMouseDown={handleImageMouseDown}
                  onMouseMove={handleImageMouseMove}
                  onMouseUp={handleImageMouseUp}
                  onMouseLeave={handleImageMouseUp}
                  style={{
                    transform: `translate(${imageState.position.x}px, ${imageState.position.y}px) scale(${imageState.scale})`,
                    transition: imageState.isDragging ? 'none' : 'transform 0.2s',
                  }}
                >
                  <img
                    src={document.thumbnail_url || `https://via.placeholder.com/800x600?text=${document.filename}`}
                    alt={document.title}
                    className="max-w-full max-h-full object-contain"
                    draggable={false}
                  />
                </div>
              </div>
            )}

            {/* Audio Player */}
            {document.file_type === 'mp3' && (
              <div className="p-6">
                <div className="max-w-2xl mx-auto">
                  {/* Audio Visualizer */}
                  <div className="bg-gradient-to-r from-blue-500 to-purple-500 h-32 rounded-lg mb-6 flex items-center justify-center">
                    <MusicalNoteIcon className="h-12 w-12 text-white animate-pulse" />
                  </div>

                  {/* Audio Controls */}
                  <div className="space-y-4">
                    <div className="flex items-center space-x-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={togglePlayPause}
                      >
                        {isPlaying ? (
                          <PauseIcon className="h-4 w-4" />
                        ) : (
                          <PlayIcon className="h-4 w-4" />
                        )}
                      </Button>
                      <div className="flex-1">
                        <input
                          type="range"
                          min="0"
                          max={duration}
                          value={currentTime}
                          onChange={handleSeek}
                          className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground mt-1">
                          <span>{formatTime(currentTime)}</span>
                          <span>{formatTime(duration)}</span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={toggleMute}
                        >
                          {isMuted ? (
                            <SpeakerXMarkIcon className="h-4 w-4" />
                          ) : (
                            <SpeakerWaveIcon className="h-4 w-4" />
                          )}
                        </Button>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={volume}
                          onChange={handleVolumeChange}
                          className="w-20"
                        />
                      </div>
                    </div>

                    {/* Transcript Toggle */}
                    {audioMetadata?.transcript && (
                      <div className="mt-6">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowTranscript(!showTranscript)}
                        >
                          {showTranscript ? 'Hide' : 'Show'} Transcript
                        </Button>
                        {showTranscript && (
                          <div className="mt-4 p-4 bg-muted rounded-lg max-h-48 overflow-y-auto">
                            <p className="text-sm">{audioMetadata.transcript}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Hidden audio element */}
                  <audio
                    ref={audioRef}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={(e) => {
                      const audio = e.currentTarget;
                      setDuration(audio.duration);
                    }}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                  />
                </div>
              </div>
            )}

            {/* Video Player */}
            {document.file_type === 'mp4' && (
              <div className="p-6">
                <div className="max-w-4xl mx-auto">
                  {/* Video */}
                  <div className="bg-black rounded-lg overflow-hidden mb-4">
                    <video
                      ref={videoRef}
                      className="w-full"
                      controls
                      onLoadedMetadata={(e) => {
                        const video = e.currentTarget;
                        setDuration(video.duration);
                      }}
                      onTimeUpdate={(e) => {
                        setCurrentTime(e.currentTarget.currentTime);
                      }}
                    >
                      <source src="#" type="video/mp4" />
                      Your browser does not support the video tag.
                    </video>
                  </div>

                  {/* Transcript Toggle */}
                  {videoMetadata?.transcript && (
                    <div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowTranscript(!showTranscript)}
                      >
                        {showTranscript ? 'Hide' : 'Show'} Transcript
                      </Button>
                      {showTranscript && (
                        <div className="mt-4 p-4 bg-muted rounded-lg max-h-48 overflow-y-auto">
                          <p className="text-sm">{videoMetadata.transcript}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <Dialog open={isFullscreen} onOpenChange={setIsFullscreen}>
          <DialogContent className="max-w-7xl max-h-[90vh] p-0">
            <div className="h-full flex flex-col">
              <DialogHeader className="p-4 border-b">
                <DialogTitle>{document.title}</DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-hidden">
                {/* Render the appropriate viewer in fullscreen */}
                <MultimodalViewer
                  document={document}
                  showControls={false}
                  allowDownload={false}
                  allowFullscreen={false}
                  className="h-full"
                />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default MultimodalViewer;