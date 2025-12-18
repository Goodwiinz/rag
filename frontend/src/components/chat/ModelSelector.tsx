'use client';

import React, { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cpu,
  Zap,
  MemoryStick,
  Clock,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Star,
  ChevronDown,
  Info,
  Loader2,
  Sparkles,
  BarChart3,
  Brain,
} from 'lucide-react';

export interface Model {
  id: string;
  name: string;
  description: string;
  size: string;
  parameters: string;
  ram: string;
  speed: 'Very Fast' | 'Fast' | 'Medium' | 'Slow';
  accuracy: number;
  features: string[];
  tags: string[];
  isRecommended?: boolean;
  isFeatured?: boolean;
  benchmarks?: {
    reasoning: number;
    coding: number;
    math: number;
    language: number;
  };
}

const DEFAULT_MODELS: Model[] = [
  {
    id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 1B',
    description: 'Ultra-lightweight model for quick responses and simple tasks',
    size: '1B',
    parameters: '1.2B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 78,
    features: ['Text Generation', 'Q&A', 'Summarization'],
    tags: ['lightweight', 'fast', 'efficient'],
    isRecommended: true,
    benchmarks: { reasoning: 72, coding: 65, math: 70, language: 82 }
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 3B',
    description: 'Balanced model offering quality responses with good speed',
    size: '3B',
    parameters: '3.2B',
    ram: '~4GB',
    speed: 'Fast',
    accuracy: 84,
    features: ['Text Generation', 'Complex Q&A', 'Reasoning', 'Coding'],
    tags: ['balanced', 'versatile', 'popular'],
    isRecommended: true,
    isFeatured: true,
    benchmarks: { reasoning: 81, coding: 78, math: 79, language: 88 }
  },
  {
    id: 'gemma-2-2b-it-q4f16_1-MLC',
    name: 'Gemma 2 2B',
    description: "Google's efficient model with strong multilingual capabilities",
    size: '2B',
    parameters: '2.6B',
    ram: '~3GB',
    speed: 'Fast',
    accuracy: 82,
    features: ['Text Generation', 'Multilingual', 'Coding'],
    tags: ['multilingual', 'google', 'efficient'],
    benchmarks: { reasoning: 79, coding: 80, math: 76, language: 91 }
  },
  {
    id: 'Phi-3.5-mini-instruct-q4f16_1-MLC',
    name: 'Phi 3.5 Mini',
    description: "Microsoft's compact model optimized for instruction following",
    size: '3.8B',
    parameters: '3.8B',
    ram: '~4GB',
    speed: 'Medium',
    accuracy: 86,
    features: ['Instruction Following', 'Reasoning', 'Code Generation'],
    tags: ['microsoft', 'instruction-tuned', 'reliable'],
    benchmarks: { reasoning: 85, coding: 83, math: 82, language: 87 }
  },
  {
    id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
    name: 'Qwen2 1.5B',
    description: 'Alibaba\'s lightweight model with strong performance',
    size: '1.5B',
    parameters: '1.5B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 80,
    features: ['Text Generation', 'Chinese & English', 'Q&A'],
    tags: ['lightweight', 'bilingual', 'alibaba'],
    isRecommended: true,
    benchmarks: { reasoning: 76, coding: 71, math: 74, language: 86 }
  },
];

interface ModelSelectorProps {
  models?: Model[];
  selectedModelId?: string;
  onModelChange: (modelId: string) => void;
  isLoading?: boolean;
  showComparison?: boolean;
  showBenchmarks?: boolean;
  className?: string;
}

export function ModelSelector({
  models = DEFAULT_MODELS,
  selectedModelId,
  onModelChange,
  isLoading = false,
  showComparison = true,
  showBenchmarks = true,
  className,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);

  const selectedModel = useMemo(
    () => models.find(m => m.id === selectedModelId),
    [models, selectedModelId]
  );

  const featuredModels = useMemo(
    () => models.filter(m => m.isFeatured),
    [models]
  );

  const recommendedModels = useMemo(
    () => models.filter(m => m.isRecommended),
    [models]
  );

  const getSpeedColor = (speed: string) => {
    switch (speed) {
      case 'Very Fast': return 'text-green-600';
      case 'Fast': return 'text-blue-600';
      case 'Medium': return 'text-yellow-600';
      case 'Slow': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getSpeedIcon = (speed: string) => {
    switch (speed) {
      case 'Very Fast': return <Zap className="w-4 h-4" />;
      case 'Fast': return <Zap className="w-4 h-4" />;
      case 'Medium': return <Clock className="w-4 h-4" />;
      case 'Slow': return <Clock className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const ModelCard = ({ model, compact = false }: { model: Model; compact?: boolean }) => (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={cn(
        "relative p-4 rounded-lg border cursor-pointer transition-all",
        "hover:shadow-md hover:border-orange-200",
        selectedModelId === model.id && "border-orange-500 bg-orange-50/50",
        compact ? "p-3" : "p-4"
      )}
      onClick={() => {
        onModelChange(model.id);
        setIsOpen(false);
      }}
    >
      {model.isFeatured && (
        <div className="absolute -top-2 -right-2">
          <Badge className="bg-gradient-to-r from-orange-500 to-orange-600">
            <Star className="w-3 h-3 mr-1" />
            Featured
          </Badge>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className={cn(
            "font-semibold text-sm",
            selectedModelId === model.id && "text-orange-600"
          )}>
            {model.name}
          </h3>
          {selectedModelId === model.id && (
            <CheckCircle2 className="w-4 h-4 text-orange-600" />
          )}
        </div>

        {!compact && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {model.description}
          </p>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-xs">
            {model.parameters}
          </Badge>
          <span className={cn("text-xs flex items-center gap-1", getSpeedColor(model.speed))}>
            {getSpeedIcon(model.speed)}
            {model.speed}
          </span>
          <span className="text-xs text-muted-foreground">
            {model.ram}
          </span>
        </div>

        {showBenchmarks && !compact && model.benchmarks && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Overall Accuracy</span>
              <span className="font-medium">{model.accuracy}%</span>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {Object.entries(model.benchmarks).map(([key, value]) => (
                <div key={key} className="text-center">
                  <div className="text-xs font-medium">{value}%</div>
                  <div className="text-[10px] text-muted-foreground capitalize">{key.slice(0, 1)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );

  const ModelComparison = () => {
    const comparisonModels = selectedModels.length > 0
      ? models.filter(m => selectedModels.includes(m.id))
      : [selectedModel, ...models.slice(0, 2)].filter(Boolean);

    return (
      <div className="space-y-4">
        {selectedModels.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Select models to compare
          </p>
        )}

        <div className="grid gap-4">
          {comparisonModels.map(model => (
            <Card key={model.id} className={cn(
              "transition-all",
              selectedModelId === model.id && "ring-2 ring-orange-500"
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">{model.name}</CardTitle>
                  <Button
                    size="sm"
                    variant={selectedModelId === model.id ? "default" : "outline"}
                    onClick={() => onModelChange(model.id)}
                  >
                    {selectedModelId === model.id ? 'Selected' : 'Select'}
                  </Button>
                </div>
                <CardDescription className="text-xs">
                  {model.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <Label className="text-muted-foreground">Parameters</Label>
                    <p className="font-medium">{model.parameters}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">RAM Usage</Label>
                    <p className="font-medium">{model.ram}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Speed</Label>
                    <p className={cn("font-medium flex items-center gap-1", getSpeedColor(model.speed))}>
                      {getSpeedIcon(model.speed)}
                      {model.speed}
                    </p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Accuracy</Label>
                    <p className="font-medium">{model.accuracy}%</p>
                  </div>
                </div>

                {model.benchmarks && (
                  <div className="mt-4">
                    <Label className="text-xs text-muted-foreground">Benchmarks</Label>
                    <div className="mt-2 space-y-2">
                      {Object.entries(model.benchmarks).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between">
                          <span className="text-xs capitalize">{key}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className={cn(
                                  "h-full transition-all",
                                  value >= 80 ? "bg-green-500" :
                                  value >= 60 ? "bg-yellow-500" : "bg-red-500"
                                )}
                                style={{ width: `${value}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium w-8 text-right">{value}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className={cn("space-y-2", className)}>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between"
            disabled={isLoading}
          >
            <div className="flex items-center gap-2">
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Cpu className="w-4 h-4" />
              )}
              <span>
                {selectedModel ? selectedModel.name : 'Select Model'}
              </span>
            </div>
            <ChevronDown className="w-4 h-4" />
          </Button>
        </DialogTrigger>

        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain className="w-5 h-5" />
              Choose AI Model
            </DialogTitle>
            <DialogDescription>
              Select the model that best fits your needs. Consider speed, accuracy, and resource requirements.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Quick Stats */}
            {selectedModel && (
              <Card className="bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200">
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center">
                        <Cpu className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-orange-900">{selectedModel.name}</h3>
                        <p className="text-sm text-orange-700">{selectedModel.description}</p>
                      </div>
                    </div>
                    <Badge className="bg-orange-500 text-white">
                      Currently Active
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Tabs */}
            <div className="flex gap-2 border-b">
              <Button
                variant={showComparison ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonOpen(false)}
                className="rounded-b-none"
              >
                <Sparkles className="w-4 h-4 mr-1" />
                All Models
              </Button>
              <Button
                variant={comparisonOpen ? "default" : "ghost"}
                size="sm"
                onClick={() => setComparisonOpen(true)}
                className="rounded-b-none"
              >
                <BarChart3 className="w-4 h-4 mr-1" />
                Compare
              </Button>
            </div>

            {/* Content */}
            <AnimatePresence mode="wait">
              {!comparisonOpen ? (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-4"
                >
                  {/* Featured Models */}
                  {featuredModels.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                        <Star className="w-4 h-4 text-orange-500" />
                        Featured Models
                      </h3>
                      <div className="grid md:grid-cols-2 gap-3">
                        {featuredModels.map(model => (
                          <ModelCard key={model.id} model={model} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommended Models */}
                  {recommendedModels.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-blue-500" />
                        Recommended
                      </h3>
                      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {recommendedModels
                          .filter(m => !m.isFeatured)
                          .map(model => (
                            <ModelCard key={model.id} model={model} compact />
                          ))}
                      </div>
                    </div>
                  )}

                  {/* All Models */}
                  <div>
                    <h3 className="text-sm font-semibold mb-3">All Models</h3>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {models.map(model => (
                        <ModelCard
                          key={model.id}
                          model={model}
                          compact={!featuredModels.includes(model) && !recommendedModels.includes(model)}
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <ModelComparison />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </DialogContent>
      </Dialog>

      {/* Model Info */}
      {selectedModel && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <MemoryStick className="w-3 h-3" />
              {selectedModel.ram}
            </span>
            <span className={cn("flex items-center gap-1", getSpeedColor(selectedModel.speed))}>
              {getSpeedIcon(selectedModel.speed)}
              {selectedModel.speed}
            </span>
            {selectedModel.accuracy && (
              <span className="flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                {selectedModel.accuracy}% accuracy
              </span>
            )}
          </div>
          <Badge variant="secondary" className="text-xs">
            {selectedModel.parameters}
          </Badge>
        </div>
      )}
    </div>
  );
}

export default ModelSelector;