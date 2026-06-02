"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Command, Search } from "lucide-react";

interface KeyboardShortcutsProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  description: string;
  icon: React.ReactNode;
}

// Only the shortcuts actually wired up on the dashboard. (Avoid advertising
// ⌘D/⌘F — those collide with the browser's bookmark/find and aren't handled.)
const shortcuts: Shortcut[] = [
  {
    keys: ["⌘", "K"],
    description: "Quick search",
    icon: <Search aria-hidden="true" className="h-4 w-4" />,
  },
  {
    keys: ["?"],
    description: "Show this shortcuts panel",
    icon: <Command aria-hidden="true" className="h-4 w-4" />,
  },
];

export const KeyboardShortcuts: React.FC<KeyboardShortcutsProps> = ({
  isOpen,
  onClose,
}) => {
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) {
        e.preventDefault();
        onClose();
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ duration: 0.2, type: "spring" }}
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md"
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="kbd-shortcuts-title"
              className="relative overflow-hidden rounded-2xl bg-white/95 backdrop-blur-xl border border-amber-200/20 shadow-2xl"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-amber-50/50 to-orange-50/30" />
              <div className="relative p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <Command
                      aria-hidden="true"
                      className="h-5 w-5 text-amber-600"
                    />
                    <h2
                      id="kbd-shortcuts-title"
                      className="text-lg font-semibold text-gray-800"
                    >
                      Keyboard Shortcuts
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close keyboard shortcuts"
                    className="p-1 hover:bg-gray-100/80 rounded-lg transition-colors"
                  >
                    <X aria-hidden="true" className="h-4 w-4 text-gray-500" />
                  </button>
                </div>

                <div className="space-y-3">
                  {shortcuts.map((shortcut, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="flex items-center justify-between p-3 rounded-xl bg-white/50 hover:bg-white/80 transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-100/50 text-amber-600 group-hover:bg-amber-100 transition-colors">
                          {shortcut.icon}
                        </div>
                        <span className="text-sm font-medium text-gray-700">
                          {shortcut.description}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        {shortcut.keys.map((key, keyIndex) => (
                          <React.Fragment key={keyIndex}>
                            {keyIndex > 0 && (
                              <span className="text-gray-400 mx-1">+</span>
                            )}
                            <kbd className="px-2 py-1 text-xs font-mono rounded-md bg-gray-100 border border-gray-200 shadow-sm">
                              {key}
                            </kbd>
                          </React.Fragment>
                        ))}
                      </div>
                    </motion.div>
                  ))}
                </div>

                <div className="mt-6 pt-4 border-t border-gray-200">
                  <p className="text-xs text-center text-gray-500">
                    Press <kbd className="px-1 py-0.5 text-xs font-mono rounded bg-gray-100">ESC</kbd> to close
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};