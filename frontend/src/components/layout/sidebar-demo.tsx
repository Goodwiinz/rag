'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { EnhancedSidebarTrigger, MobileSidebarTrigger } from '@/components/ui/enhanced-sidebar-trigger';
import { useSidebarStore, useSidebarKeyboardShortcuts } from '@/store/sidebar-store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ChevronDown, ChevronRight, Keyboard, Settings, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

export function SidebarDemo() {
  const {
    state,
    toggleSidebar,
    expandSidebar,
    collapseSidebar,
    setMiniMode,
    isMobile,
    shouldShowTooltips,
  } = useSidebarStore();

  // Enable keyboard shortcuts
  useSidebarKeyboardShortcuts();

  const [isOpen, setIsOpen] = useState(true);

  const shortcuts = [
    { key: '⌘/Ctrl + B', description: 'Toggle sidebar state' },
    { key: '⌘/Ctrl + Shift + B', description: 'Expand sidebar' },
    { key: '⌘/Ctrl + Alt + B', description: 'Collapse sidebar' },
    { key: 'Escape', description: 'Close mobile sidebar' },
  ];

  const features = [
    {
      title: 'Persistent State',
      description: 'Sidebar state is saved to localStorage and restored on page refresh',
      status: '✅ Implemented',
    },
    {
      title: 'Three States',
      description: 'Expanded, Mini (icon-only), and Collapsed states',
      status: '✅ Implemented',
    },
    {
      title: 'Smooth Animations',
      description: 'Fluid transitions between states using Framer Motion',
      status: '✅ Implemented',
    },
    {
      title: 'Keyboard Shortcuts',
      description: 'Quick keyboard controls for power users',
      status: '✅ Implemented',
    },
    {
      title: 'Responsive Design',
      description: 'Adaptive behavior for mobile, tablet, and desktop',
      status: '✅ Implemented',
    },
    {
      title: 'Mobile Overlay',
      description: 'Full-screen overlay with backdrop on mobile devices',
      status: '✅ Implemented',
    },
    {
      title: 'Tooltips in Mini Mode',
      description: 'Helpful tooltips when sidebar is in mini mode',
      status: '✅ Implemented',
    },
    {
      title: 'Auto-collapse on Mobile',
      description: 'Sidebar automatically collapses on mobile devices',
      status: '✅ Implemented',
    },
    {
      title: 'Auto-mini on Tablet',
      description: 'Sidebar switches to mini mode on tablet devices',
      status: '✅ Implemented',
    },
    {
      title: 'Hover Effects',
      description: 'Subtle hover animations and visual feedback',
      status: '✅ Implemented',
    },
    {
      title: 'Resize Handle',
      description: 'Drag to resize sidebar on desktop',
      status: '✅ Implemented',
    },
    {
      title: 'Accessibility',
      description: 'Full keyboard navigation and screen reader support',
      status: '✅ Implemented',
    },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Enhanced Sidebar System</h1>
        <p className="text-muted-foreground">
          A premium sidebar implementation with smooth animations, persistent state, and responsive design.
        </p>
      </div>

      {/* Current State Display */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Current State
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <p className="text-sm font-medium">Sidebar State</p>
              <Badge variant={state === 'expanded' ? 'default' : 'secondary'} className="capitalize">
                {state}
              </Badge>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Device Type</p>
              <Badge variant="outline">
                {isMobile ? 'Mobile' : 'Desktop'}
              </Badge>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Tooltips</p>
              <Badge variant="outline">
                {shouldShowTooltips ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
          </div>

          {/* Toggle Buttons */}
          <div className="flex flex-wrap gap-2 pt-4">
            <Button onClick={toggleSidebar} variant="outline">
              <EnhancedSidebarTrigger showLabel />
            </Button>
            <Button onClick={expandSidebar} variant="outline">
              Expand
            </Button>
            <Button onClick={setMiniMode} variant="outline">
              Mini Mode
            </Button>
            <Button onClick={collapseSidebar} variant="outline">
              Collapse
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Keyboard Shortcuts */}
      <Card>
        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
          <CollapsibleTrigger className="w-full">
            <CardHeader className="cursor-pointer hover:bg-accent/50 transition-colors">
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Keyboard className="w-5 h-5" />
                  Keyboard Shortcuts
                </div>
                {isOpen ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </CardTitle>
              <CardDescription>
                Use these shortcuts for quick sidebar control
              </CardDescription>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="pt-0">
              <div className="grid gap-3">
                {shortcuts.map((shortcut, index) => (
                  <motion.div
                    key={shortcut.key}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: index * 0.05 }}
                    className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <kbd className="px-2 py-1 text-xs bg-background border rounded shadow-sm">
                        {shortcut.key}
                      </kbd>
                      <span className="text-sm">{shortcut.description}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {/* Features List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" />
            Features
          </CardTitle>
          <CardDescription>
            All the enhancements implemented in the sidebar system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                className={cn(
                  'p-3 rounded-lg border',
                  'hover:bg-accent/50 transition-colors'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <h3 className="font-medium text-sm">{feature.title}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      {feature.description}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {feature.status}
                  </Badge>
                </div>
              </motion.div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>How to Use</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>• Click the sidebar toggle button in the header or use keyboard shortcuts</p>
          <p>• On desktop, cycle through: Expanded → Mini → Collapsed</p>
          <p>• On mobile, sidebar appears as an overlay with a backdrop</p>
          <p>• State is automatically saved and restored on page refresh</p>
          <p>• Resize sidebar by dragging the right edge (desktop only)</p>
        </CardContent>
      </Card>
    </div>
  );
}