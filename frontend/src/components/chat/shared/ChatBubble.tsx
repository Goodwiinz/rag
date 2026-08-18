'use client';

import { cn } from '@/lib/utils';
import { completeStreamingMarkdown } from '@/lib/markdown-utils';
import { getReferencedCitations, type Citation } from '@/utils/citationParser';
import {
  Check,
  Clock,
  Copy,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import React, { useMemo, useState } from 'react';
import { CitationRenderer } from '../CitationRenderer';
import { ChatInlinePlan } from './ChatInlinePlan';
import { ToolStrip } from './ToolStrip';
import { CitationChips } from './CitationChips';
import { ThinkingMatrix } from './ThinkingMatrix';
import { AuiToolParts } from '@/components/chat/aui/AuiToolParts';
import { useChatStore } from '@/store/chat-store';
import type { ActivityStep } from './cloudMessageView';
import type { PlanStep } from '@/types/agent-chat';

export interface ChatBubbleMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
  /** Tool executions recorded during the turn that produced this message. */
  toolExecutions?: ActivityStep[];
  /** Structured execution plan emitted by the agent planner for this turn. */
  plan?: PlanStep[];
  /** Planner's top-level rationale for `plan`. */
  planReasoning?: string;
  metadata?: {
    toolsUsed?: string[];
    responseTimeMs?: number;
    /** Time to first token, same origin as `responseTimeMs`. */
    ttftMs?: number;
    sourcesCount?: number;
    stopped?: boolean;
    tokenUsage?: { input: number; output: number };
  };
}

const EMPTY_STEPS: ActivityStep[] = [];
const EMPTY_PLAN: PlanStep[] = [];

export interface ChatBubbleProps {
  message: ChatBubbleMessage;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  isStreaming?: boolean;
  streamingContent?: string;
  onRetry?: () => void;
  onCitationClick?: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  /** Label for the pre-token "thinking" pill (phase-aware). */
  thinkingLabel?: string;
}

export const ChatBubble = React.memo(function ChatBubble({
  message,
  index: _index,
  modelName,
  isTyping,
  isStreaming,
  streamingContent,
  onRetry,
  onCitationClick,
  thinkingLabel = 'Thinking',
}: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  // Read live streaming steps from the store — only meaningful for the
  // currently-streaming message (isStreaming=true). For committed messages
  // we return a stable empty array so the store subscription doesn't
  // trigger re-renders on every tool start/end during streaming.
  const storeStreamingSteps = useChatStore((s) =>
    isStreaming ? s.streamingSteps : EMPTY_STEPS
  );
  const storeStreamingPlan = useChatStore((s) =>
    isStreaming ? s.streamingPlan : EMPTY_PLAN
  );

  const timestamp = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '--:--';

  const handleCopy = async () => {
    try {
      const textToCopy = streamingContent || message.content;
      if (!textToCopy) return;
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard access denied or page unfocused
    }
  };

  const allCitations = message.citations ?? [];

  const inlineCitations = useMemo(
    () => getReferencedCitations(message.content, allCitations),
    [message.content, allCitations]
  );

  // Show inline-referenced citations when available, otherwise fall back
  // to all attached citations so footer chips + tool strip always render
  // when the backend attached sources — even if the AI didn't use [Doc N].
  const visibleCitations =
    inlineCitations.length > 0 ? inlineCitations : allCitations;

  const stripSourcesCount =
    message.metadata?.sourcesCount ?? visibleCitations.length;
  // Prefer committed metadata; fall back to toolExecutions labels so the strip
  // never shows "0 tools" when executions are present but metadata wasn't set.
  const stripToolsUsed =
    message.metadata?.toolsUsed ??
    (message.toolExecutions && message.toolExecutions.length > 0
      ? message.toolExecutions.map((s) => s.label)
      : undefined);
  // The execution plan's header shows its own "took …" duration — when a
  // plan is present, the clock moved there (see ToolStrip.getToolStripProps).
  const hasPlan = !!message.plan && message.plan.length > 0;
  const stripResponseMs = hasPlan ? undefined : message.metadata?.responseTimeMs;

  // Steps to show in the activity strip:
  // — while streaming: live store steps (scoped to this turn)
  // — after commit: persisted toolExecutions on the message
  const activitySteps: ActivityStep[] = isStreaming
    ? storeStreamingSteps
    : (message.toolExecutions ?? []);

  // Execution plan: live streaming plan while in flight, committed plan
  // after — same streaming/committed split as activitySteps above.
  const activePlan: PlanStep[] = isStreaming
    ? storeStreamingPlan
    : (message.plan ?? []);

  return (
    <div className="group relative mb-7 sm:mb-8">
      {/* Content column */}
      <div className={cn('min-w-0', isUser ? 'text-right' : 'text-left')}>
        {/* Meta row — role + model pill + time */}
        <div
          className={cn(
            'mb-2 flex items-center gap-2.5',
            isUser ? 'justify-end' : ''
          )}
        >
          {!isUser && (
            <>
              <span
                className="text-[12px] font-medium text-(--nous-fg-3)"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Assistant
              </span>
              {modelName && (
                <span
                  className="inline-flex items-center gap-1 px-2 py-[2px] rounded text-[10px] font-semibold bg-(--nous-aurum) text-(--nous-sol-safe) dark:bg-(--nous-ember) dark:text-(--nous-helios)"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <Sparkles className="w-2.5 h-2.5" strokeWidth={2} />
                  {modelName}
                </span>
              )}
            </>
          )}
          {isUser && (
            <span
              className="text-[12px] font-medium text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              You
            </span>
          )}
          <span
            className="inline-flex items-center gap-1 text-[11px] text-(--nous-fg-3)"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <Clock className="w-2.5 h-2.5" strokeWidth={2} />
            {timestamp}
          </span>
        </div>

        {/* Execution plan — live while streaming, committed provenance after */}
        {!isUser && activePlan.length > 0 && (
          <ChatInlinePlan
            plan={activePlan}
            reasoning={message.planReasoning}
            toolExecutions={activitySteps}
            streaming={isStreaming}
            elapsedMs={message.metadata?.responseTimeMs}
            ttftMs={message.metadata?.ttftMs}
          />
        )}

        {/* Tool strip — only when we have something to show */}
        {!isUser && !isStreaming && !isTyping && (
          <ToolStrip
            toolsUsed={stripToolsUsed}
            sourcesCount={stripSourcesCount}
            responseTimeMs={stripResponseMs}
            ttftMs={hasPlan ? undefined : message.metadata?.ttftMs}
            stopped={message.metadata?.stopped}
            tokenUsage={message.metadata?.tokenUsage}
          />
        )}

        {/* Body
            — user: scholarly pill (nous-bubble-user)
            — assistant: NO wrapper — serif body sits directly on parchment,
              matching the hybrid-chat reference where the assistant column
              reads as a manuscript margin, not a chat card. */}
        {isUser ? (
          <div
            className={cn(
              'nous-bubble-user relative inline-block px-4 py-2.5 text-left',
              'max-w-[92%] sm:max-w-[540px] transition-shadow hover:shadow-md'
            )}
          >
            <div className="nous-chat-body">
              <p className="whitespace-pre-wrap text-[14px] leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        ) : (
          <div className="relative">
            {/* Inline agent activity strip — above body, quiet */}
            {activitySteps.length > 0 && (
              <AuiToolParts
                messageId={message.id ?? `idx-${_index}`}
                steps={activitySteps}
                isStreaming={Boolean(isStreaming)}
              />
            )}

            {isStreaming && !streamingContent ? (
              <ThinkingPill label={thinkingLabel} />
            ) : isStreaming && streamingContent ? (
              <div className="nous-chat-body">
                {/* Render streaming content through CitationRenderer so
                    markdown (bold, lists, headings) renders live, not as raw
                    whitespace-pre-wrap text. Pass empty citations — they aren't
                    available until the stream commits. */}
                <CitationRenderer
                  content={completeStreamingMarkdown(streamingContent)}
                  freshTail
                  citations={[]}
                  onCitationClick={() => {}}
                />
                <span
                  className="ml-0.5 inline-block h-4 w-[3px] rounded-sm align-text-bottom animate-pulse bg-(--nous-sol) dark:bg-(--nous-helios)"
                  data-testid="streaming-cursor"
                />
              </div>
            ) : isTyping && !message.content ? (
              <ThinkingPill label={thinkingLabel} />
            ) : (
              <div className="nous-chat-body">
                <CitationRenderer
                  content={message.content}
                  citations={message.citations as Citation[]}
                  onCitationClick={(citation) => {
                    if (onCitationClick) {
                      onCitationClick(
                        visibleCitations,
                        citation,
                        message.diagnosticsTraceId
                      );
                    }
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* Citations footer chips */}
        {!isUser &&
          visibleCitations.length > 0 &&
          !isStreaming &&
          !isTyping && (
            <CitationChips
              citations={visibleCitations}
              diagnosticsTraceId={message.diagnosticsTraceId}
              onCitationClick={onCitationClick}
            />
          )}

        {/* Scholarly action row — visible on hover */}
        {!isUser && !isStreaming && !isTyping && message.content && (
          <div className="nous-msg-actions">
            <button
              onClick={handleCopy}
              className="nous-msg-action"
              aria-label={copied ? 'Copied!' : 'Copy message'}
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-(--nous-terra)" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
            {onRetry && (
              <button
                onClick={onRetry}
                className="nous-msg-action"
                aria-label="Regenerate response"
                title="Regenerate response"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        {/* User message: copy on hover */}
        {isUser && message.content && (
          <div className="nous-msg-actions justify-end">
            <button
              onClick={handleCopy}
              className="nous-msg-action"
              aria-label={copied ? 'Copied!' : 'Copy message'}
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-(--nous-terra)" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

function ThinkingPill({ label }: { label: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="nous-streaming-pill"
      role="status"
      aria-live="polite"
      initial={reduce ? false : { opacity: 0, y: 2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
    >
      <ThinkingMatrix />
      <span>{label}</span>
    </motion.div>
  );
}

export default ChatBubble;
