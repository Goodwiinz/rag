/**
 * ThreadCard Component - Display linked conversation thread
 *
 * Features:
 * - Clickable title navigates to chat thread
 * - Link type badge (AUTO/MANUAL/FROM_CHAT) with color coding
 * - Message count and last message time
 * - Context note display (amber text)
 * - Conversation ID (small, gray)
 * - Actions: Open Thread, Save to Note, Unlink (with confirm)
 * - Terminal Observatory theme (dark with phosphor green accents)
 */

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, Clock, FileText, Link2, Trash2, ExternalLink } from 'lucide-react';
import { ProjectThread, ProjectThreadLinkType } from '@/types/project-chat';
import { formatDistanceToNow } from 'date-fns';

// ============================================================================
// Theme Constants
// ============================================================================

const COLORS = {
  phosphorGreen: '#00ff9f',
  amber: '#ffb700',
  cyan: '#00d4ff',
  terminalBg: '#0a0a0a',
  terminalSurface: '#0d0d12',
  terminalBorder: '#1a1a1a',
  textMuted: '#6b7280',
  textSecondary: '#9ca3af',
  dangerRed: '#ef4444',
};

// Link type badge colors
const LINK_TYPE_COLORS: Record<ProjectThreadLinkType, { bg: string; text: string; border: string }> = {
  [ProjectThreadLinkType.AUTO]: {
    bg: 'rgba(0, 255, 159, 0.1)',
    text: COLORS.phosphorGreen,
    border: 'rgba(0, 255, 159, 0.3)',
  },
  [ProjectThreadLinkType.MANUAL]: {
    bg: 'rgba(0, 212, 255, 0.1)',
    text: COLORS.cyan,
    border: 'rgba(0, 212, 255, 0.3)',
  },
  [ProjectThreadLinkType.FROM_CHAT]: {
    bg: 'rgba(255, 183, 0, 0.1)',
    text: COLORS.amber,
    border: 'rgba(255, 183, 0, 0.3)',
  },
};

// ============================================================================
// Props Interface
// ============================================================================

interface ThreadCardProps {
  thread: ProjectThread;
  onSaveToNote: (threadId: string) => void;
  onUnlink: (threadId: string) => void;
}

// ============================================================================
// Component
// ============================================================================

export const ThreadCard: React.FC<ThreadCardProps> = ({
  thread,
  onSaveToNote,
  onUnlink,
}) => {
  const router = useRouter();
  const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false);

  // Format last message time
  const formatLastMessageTime = (timestamp?: string) => {
    if (!timestamp) return 'No messages yet';
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
    } catch {
      return 'Recently';
    }
  };

  // Handle title click - navigate to chat
  const handleTitleClick = () => {
    router.push(`/chat?conversationId=${thread.conversation_id}`);
  };

  // Handle open thread action
  const handleOpenThread = () => {
    router.push(`/chat?conversationId=${thread.conversation_id}`);
  };

  // Handle save to note
  const handleSaveToNote = () => {
    onSaveToNote(thread.thread_id);
  };

  // Handle unlink with confirmation
  const handleUnlinkClick = () => {
    setShowUnlinkConfirm(true);
  };

  const handleConfirmUnlink = () => {
    onUnlink(thread.thread_id);
    setShowUnlinkConfirm(false);
  };

  const handleCancelUnlink = () => {
    setShowUnlinkConfirm(false);
  };

  // Handle case-insensitive link type lookup (backend returns lowercase)
  const normalizedLinkType = thread.link_type?.toUpperCase() as ProjectThreadLinkType;
  const linkTypeColors = LINK_TYPE_COLORS[normalizedLinkType] || LINK_TYPE_COLORS[ProjectThreadLinkType.AUTO];

  return (
    <div
      style={{
        backgroundColor: COLORS.terminalSurface,
        border: `1px solid ${COLORS.terminalBorder}`,
        borderRadius: '8px',
        padding: '16px',
        transition: 'all 0.2s ease',
      }}
      className="hover:shadow-lg"
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = COLORS.phosphorGreen;
        e.currentTarget.style.boxShadow = `0 0 20px rgba(0, 255, 159, 0.15)`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = COLORS.terminalBorder;
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {/* Header Row - Title + Link Type Badge */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '12px' }}>
        <h3
          onClick={handleTitleClick}
          style={{
            flex: 1,
            fontSize: '16px',
            fontWeight: 600,
            color: COLORS.phosphorGreen,
            cursor: 'pointer',
            margin: 0,
            fontFamily: 'monospace',
            transition: 'color 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = COLORS.cyan;
            e.currentTarget.style.textDecoration = 'underline';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = COLORS.phosphorGreen;
            e.currentTarget.style.textDecoration = 'none';
          }}
        >
          {thread.thread_title}
        </h3>

        {/* Link Type Badge */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '4px 8px',
            fontSize: '11px',
            fontWeight: 600,
            fontFamily: 'monospace',
            backgroundColor: linkTypeColors.bg,
            color: linkTypeColors.text,
            border: `1px solid ${linkTypeColors.border}`,
            borderRadius: '4px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {thread.link_type}
        </span>
      </div>

      {/* Metadata Row - Message Count + Last Message Time */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '12px',
          fontSize: '13px',
          color: COLORS.textSecondary,
          fontFamily: 'monospace',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <MessageSquare size={14} style={{ color: COLORS.cyan }} />
          <span>{thread.message_count} messages</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Clock size={14} style={{ color: COLORS.amber }} />
          <span>{formatLastMessageTime(thread.last_message_at)}</span>
        </div>
      </div>

      {/* Context Note (if present) */}
      {thread.context_note && (
        <div
          style={{
            marginBottom: '12px',
            padding: '8px 12px',
            backgroundColor: 'rgba(255, 183, 0, 0.05)',
            border: `1px solid rgba(255, 183, 0, 0.2)`,
            borderRadius: '4px',
            fontSize: '13px',
            color: COLORS.amber,
            fontFamily: 'monospace',
            fontStyle: 'italic',
          }}
        >
          {thread.context_note}
        </div>
      )}

      {/* Conversation ID */}
      <div
        style={{
          marginBottom: '12px',
          fontSize: '11px',
          color: COLORS.textMuted,
          fontFamily: 'monospace',
        }}
      >
        Conversation ID: {thread.conversation_id}
      </div>

      {/* Actions Row */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          paddingTop: '12px',
          borderTop: `1px solid ${COLORS.terminalBorder}`,
        }}
      >
        {/* Open Thread Button */}
        <button
          onClick={handleOpenThread}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            padding: '8px 12px',
            fontSize: '13px',
            fontWeight: 600,
            fontFamily: 'monospace',
            color: COLORS.phosphorGreen,
            backgroundColor: 'rgba(0, 255, 159, 0.1)',
            border: `1px solid ${COLORS.phosphorGreen}`,
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 255, 159, 0.2)';
            e.currentTarget.style.boxShadow = `0 0 10px rgba(0, 255, 159, 0.3)`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 255, 159, 0.1)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <ExternalLink size={14} />
          Open Thread
        </button>

        {/* Save to Note Button */}
        <button
          onClick={handleSaveToNote}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            padding: '8px 12px',
            fontSize: '13px',
            fontWeight: 600,
            fontFamily: 'monospace',
            color: COLORS.cyan,
            backgroundColor: 'rgba(0, 212, 255, 0.1)',
            border: `1px solid ${COLORS.cyan}`,
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 212, 255, 0.2)';
            e.currentTarget.style.boxShadow = `0 0 10px rgba(0, 212, 255, 0.3)`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0, 212, 255, 0.1)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <FileText size={14} />
          Save to Note
        </button>

        {/* Unlink Button */}
        {!showUnlinkConfirm ? (
          <button
            onClick={handleUnlinkClick}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 12px',
              fontSize: '13px',
              fontWeight: 600,
              fontFamily: 'monospace',
              color: COLORS.dangerRed,
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${COLORS.dangerRed}`,
              borderRadius: '4px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
              e.currentTarget.style.boxShadow = `0 0 10px rgba(239, 68, 68, 0.3)`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <Trash2 size={14} />
          </button>
        ) : (
          // Confirmation buttons
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              onClick={handleConfirmUnlink}
              style={{
                padding: '8px 12px',
                fontSize: '11px',
                fontWeight: 600,
                fontFamily: 'monospace',
                color: '#fff',
                backgroundColor: COLORS.dangerRed,
                border: `1px solid ${COLORS.dangerRed}`,
                borderRadius: '4px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#dc2626';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = COLORS.dangerRed;
              }}
            >
              Confirm
            </button>
            <button
              onClick={handleCancelUnlink}
              style={{
                padding: '8px 12px',
                fontSize: '11px',
                fontWeight: 600,
                fontFamily: 'monospace',
                color: COLORS.textSecondary,
                backgroundColor: 'transparent',
                border: `1px solid ${COLORS.terminalBorder}`,
                borderRadius: '4px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ThreadCard;
