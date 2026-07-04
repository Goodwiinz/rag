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
            <div className="flex flex-col items-center shrink-0">
              <button
                onClick={() => isClickable && onStepClick(index)}
                disabled={!isClickable}
                className={`
                  relative flex items-center justify-center w-12 h-12 rounded-full
                  transition-all duration-300 text-sm
                  ${
                    status === 'completed'
                      ? 'bg-primary/10 border-2 border-primary text-primary cursor-pointer hover:bg-primary/20 hover:scale-105'
                      : status === 'active'
                        ? 'bg-primary border-2 border-primary text-primary-foreground shadow-lg shadow-primary/20'
                        : status === 'skipped'
                          ? 'bg-muted/50 border-2 border-dashed border-border text-muted-foreground cursor-pointer hover:border-muted-foreground/50 hover:scale-105'
                          : status === 'invalidated'
                            ? 'bg-(--nous-helios)/10 border-2 border-(--nous-helios) text-(--nous-helios) cursor-pointer hover:bg-(--nous-helios)/20 hover:scale-105'
                            : 'bg-muted/30 border-2 border-border text-muted-foreground'
                  }
                `}
                aria-label={`Step ${index + 1}: ${step.label} (${status})`}
              >
                {status === 'completed' ? (
                  <Check className="h-5 w-5" />
                ) : status === 'skipped' ? (
                  <SkipForward className="h-4 w-4" />
                ) : status === 'invalidated' ? (
                  <AlertTriangle className="h-4 w-4" />
                ) : (
                  <Icon className="h-5 w-5" />
                )}
              </button>
              <span
                className={`mt-2 text-xs font-medium ${
                  status === 'completed'
                    ? 'text-primary'
                    : status === 'active'
                      ? 'text-foreground font-semibold'
                      : status === 'skipped'
                        ? 'text-muted-foreground'
                        : status === 'invalidated'
                          ? 'text-(--nous-helios)'
                          : 'text-foreground'
                }`}
              >
                {step.label}
              </span>
              {status === 'skipped' && (
                <span className="text-[10px] text-muted-foreground">
                  skipped
                </span>
              )}
            </div>

            {/* Connector line */}
            {index < PIPELINE_STEPS.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 mt-[-24px] ${
                  status === 'completed'
                    ? 'bg-primary/40'
                    : status === 'skipped'
                      ? 'border-t-2 border-dashed border-border bg-transparent'
                      : status === 'invalidated'
                        ? 'bg-(--nous-helios)/30'
                        : 'bg-muted'
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
