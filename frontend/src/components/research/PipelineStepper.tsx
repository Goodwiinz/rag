'use client';

/**
 * PipelineStepper Component
 * Horizontal stepper UI for the Research Pipeline wizard.
 * Shows step states: completed, active, skipped, upcoming, invalidated.
 */

import React from 'react';
import {
  Check,
  SkipForward,
  AlertTriangle,
  FileText,
  Grid3X3,
  BookOpen,
  Sparkles,
  Download,
} from 'lucide-react';
import type { PipelineStepStatus } from '@/types/scispace';
import { PIPELINE_STEPS } from '@/types/scispace';

interface PipelineStepperProps {
  currentStep: number;
  completedSteps: number[];
  skippedSteps: number[];
  invalidatedSteps: number[];
  onStepClick: (step: number) => void;
}

const STEP_ICONS = [FileText, Grid3X3, BookOpen, Sparkles, Download];

function getStepStatus(
  index: number,
  currentStep: number,
  completedSteps: number[],
  skippedSteps: number[],
  invalidatedSteps: number[]
): PipelineStepStatus {
  if (invalidatedSteps.includes(index)) return 'invalidated';
  if (index === currentStep) return 'active';
  if (skippedSteps.includes(index)) return 'skipped';
  if (completedSteps.includes(index)) return 'completed';
  return 'upcoming';
}

export const PipelineStepper: React.FC<PipelineStepperProps> = ({
  currentStep,
  completedSteps,
  skippedSteps,
  invalidatedSteps,
  onStepClick,
}) => {
  return (
    <div className="flex items-center w-full mb-8">
      {PIPELINE_STEPS.map((step, index) => {
        const status = getStepStatus(
          index,
          currentStep,
          completedSteps,
          skippedSteps,
          invalidatedSteps
        );
        const Icon = STEP_ICONS[index];
        const isClickable =
          status === 'completed' ||
          status === 'skipped' ||
          status === 'invalidated';

        return (
          <React.Fragment key={step.index}>
            {/* Step circle + label */}
            <div className="flex flex-col items-center flex-shrink-0">
              <button
                onClick={() => isClickable && onStepClick(index)}
                disabled={!isClickable}
                className={`
                  relative flex items-center justify-center w-10 h-10 rounded-full
                  transition-all duration-300 font-mono text-xs
                  ${
                    status === 'completed'
                      ? 'bg-sol/20 border-2 border-sol text-sol cursor-pointer hover:bg-sol/30'
                      : status === 'active'
                        ? 'bg-secondary/10 border-2 border-secondary text-white animate-pulse'
                        : status === 'skipped'
                          ? 'bg-gray-800/50 border-2 border-border border-dashed text-muted-foreground cursor-pointer hover:border-border'
                          : status === 'invalidated'
                            ? 'bg-helios/10 border-2 border-helios text-helios cursor-pointer hover:bg-helios/20'
                            : 'bg-gray-800/30 border-2 border-border text-foreground'
                  }
                `}
                aria-label={`Step ${index + 1}: ${step.label} (${status})`}
              >
                {status === 'completed' ? (
                  <Check className="h-4 w-4" />
                ) : status === 'skipped' ? (
                  <SkipForward className="h-3.5 w-3.5" />
                ) : status === 'invalidated' ? (
                  <AlertTriangle className="h-3.5 w-3.5" />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
              </button>
              <span
                className={`mt-2 text-[11px] font-mono tracking-wide ${
                  status === 'completed'
                    ? 'text-sol'
                    : status === 'active'
                      ? 'text-white'
                      : status === 'skipped'
                        ? 'text-muted-foreground'
                        : status === 'invalidated'
                          ? 'text-helios'
                          : 'text-foreground'
                }`}
              >
                {step.label}
              </span>
              {status === 'skipped' && (
                <span className="text-[9px] text-foreground font-mono">
                  skipped
                </span>
              )}
            </div>

            {/* Connector line */}
            {index < PIPELINE_STEPS.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 mt-[-20px] ${
                  status === 'completed'
                    ? 'bg-sol/40'
                    : status === 'skipped'
                      ? 'border-t-2 border-dashed border-border bg-transparent'
                      : status === 'invalidated'
                        ? 'bg-helios/30'
                        : 'bg-gray-800'
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
