/**
 * KeyboardShortcutsDialog Component
 * Displays all available keyboard shortcuts
 */

import React from 'react';
import { Keyboard, X } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';

interface ShortcutItem {
  keys: string[];
  description: string;
  category: string;
}

interface KeyboardShortcutsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const KeyboardShortcutsDialog: React.FC<KeyboardShortcutsDialogProps> = ({
  open,
  onOpenChange,
}) => {
  const shortcuts: ShortcutItem[] = [
    // Navigation
    { keys: ['G'], description: 'Toggle graph view', category: 'Navigation' },
    { keys: ['A'], description: 'Toggle analytics', category: 'Navigation' },
    { keys: ['P'], description: 'Open path finder', category: 'Navigation' },
    { keys: ['B'], description: 'Open bulk operations', category: 'Navigation' },
    { keys: ['H'], description: 'Open health monitor', category: 'Navigation' },
    { keys: ['M'], description: 'Open merge tool', category: 'Navigation' },
    { keys: ['D'], description: 'Open document extractor', category: 'Navigation' },
    
    // Actions
    { keys: ['Ctrl', 'N'], description: 'Create new entity', category: 'Actions' },
    { keys: ['Ctrl', 'K'], description: 'Focus search', category: 'Actions' },
    { keys: ['Ctrl', 'R'], description: 'Refresh data', category: 'Actions' },
    { keys: ['Ctrl', 'Shift', 'E'], description: 'Export data', category: 'Actions' },
    
    // Help
    { keys: ['?'], description: 'Show keyboard shortcuts', category: 'Help' },
    { keys: ['Esc'], description: 'Close dialogs', category: 'Help' },
  ];

  const categories = Array.from(new Set(shortcuts.map(s => s.category)));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono">
        <DialogHeader className="border-b border-[var(--terminal-border)] pb-4">
          <DialogTitle className="text-lg font-bold tracking-tight flex items-center gap-2">
            <Keyboard className="w-5 h-5" />
            KEYBOARD_SHORTCUTS
          </DialogTitle>
        </DialogHeader>
        <div className="py-4 space-y-6 max-h-[60vh] overflow-y-auto">
          {categories.map((category) => (
            <div key={category}>
              <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--phosphor-green)] mb-3">
                {category}
              </h3>
              <div className="space-y-2">
                {shortcuts
                  .filter((s) => s.category === category)
                  .map((shortcut, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-2 rounded-md bg-[var(--terminal-bg)] border border-[var(--terminal-border)]"
                    >
                      <span className="text-sm text-[var(--terminal-text)]">
                        {shortcut.description}
                      </span>
                      <div className="flex items-center gap-1">
                        {shortcut.keys.map((key, keyIndex) => (
                          <React.Fragment key={keyIndex}>
                            {keyIndex > 0 && (
                              <span className="text-xs text-[var(--terminal-text-dim)]">+</span>
                            )}
                            <Badge
                              variant="outline"
                              className="font-mono text-xs px-2 py-0.5 bg-[var(--terminal-elevated)] border-[var(--terminal-border)]"
                            >
                              {key}
                            </Badge>
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-[var(--terminal-border)] pt-4">
          <p className="text-xs font-mono text-[var(--terminal-text-dim)]">
            💡 Tip: Press <Badge variant="outline" className="font-mono text-[10px] mx-1">?</Badge> anytime to see these shortcuts
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
