# New Chat Dialog Components

This document provides comprehensive documentation for the enhanced New Chat Dialog components built with shadcn/ui, featuring glass morphism effects, smooth animations, and modern design patterns.

## Overview

The New Chat Dialog components provide a beautiful, accessible, and feature-rich interface for users to select AI assistants for their conversations. Two versions are available:

1. **NewChatDialog** - Standard version with essential features
2. **EnhancedNewChatDialog** - Advanced version with additional features and animations

## Installation

Make sure you have the following dependencies installed:

```bash
npm install framer-motion class-variance-authority
```

Required components from shadcn/ui:
- Dialog
- Button
- Input
- Avatar
- Badge

## Basic Usage

### Standard NewChatDialog

```tsx
import { NewChatDialog } from '@/components/ui/new-chat-dialog'

function App() {
  const [isOpen, setIsOpen] = useState(false)

  const assistants = [
    {
      id: "default",
      name: "Default",
      description: "General purpose assistant",
      avatar: "",
      category: "general",
      capabilities: ["General knowledge", "Text processing"],
      color: "from-blue-500 to-cyan-500"
    }
  ]

  return (
    <NewChatDialog
      open={isOpen}
      onOpenChange={setIsOpen}
      assistants={assistants}
      onSelectAssistant={(assistant) => {
        console.log('Selected:', assistant)
      }}
    />
  )
}
```

### Enhanced NewChatDialog

```tsx
import { EnhancedNewChatDialog } from '@/components/ui/enhanced-new-chat-dialog'
import { useNewChatDialog, useChatKeyboardShortcuts } from '@/hooks/useNewChatDialog'

function App() {
  const {
    isOpen,
    selectedAssistantId,
    recentSelections,
    openDialog,
    closeDialog,
    selectAssistant,
    handleDialogChange
  } = useNewChatDialog({
    onAssistantSelect: (assistant) => {
      console.log('Starting chat with:', assistant)
    }
  })

  // Enable keyboard shortcuts
  useChatKeyboardShortcuts(openDialog)

  return (
    <EnhancedNewChatDialog
      open={isOpen}
      onOpenChange={handleDialogChange}
      assistants={assistants}
      onSelectAssistant={selectAssistant}
      categories={ASSISTANT_CATEGORIES}
      showCategories={true}
      showTrending={true}
      recentlyUsed={recentSelections}
    />
  )
}
```

## Features

### Core Features
- ✅ Glass morphism design with backdrop blur effects
- ✅ Smooth animations and transitions (Framer Motion)
- ✅ Search/filter functionality
- ✅ Category filtering
- ✅ Assistant selection with visual feedback
- ✅ Loading states
- ✅ Error handling
- ✅ Responsive design
- ✅ Dark mode support
- ✅ Keyboard navigation
- ✅ Accessibility (ARIA labels)

### Enhanced Features
- ✅ Advanced animations (scale, rotate, spring physics)
- ✅ Metrics display (usage count, ratings)
- ✅ Premium/PRO badges
- ✅ Recently used tracking
- ✅ Category icons and colors
- ✅ Trending indicators
- ✅ Assistant variants (compact, detailed)
- ✅ Persistent state management
- ✅ Keyboard shortcuts (Cmd/Ctrl + K)
- ✅ Custom scrollbars
- ✅ Hover effects and micro-interactions

## Props

### NewChatDialog

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `open` | `boolean` | Required | Controls dialog visibility |
| `onOpenChange` | `(open: boolean) => void` | Required | Called when dialog opens/closes |
| `assistants` | `Assistant[]` | `[]` | List of available assistants |
| `onSelectAssistant` | `(assistant: Assistant) => void` | Required | Called when assistant is selected |
| `isLoading` | `boolean` | `false` | Show loading state |

### EnhancedNewChatDialog

Includes all props from NewChatDialog plus:

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `error` | `string | null` | `null` | Error message to display |
| `categories` | `AssistantCategory[]` | `[]` | List of categories for filtering |
| `showCategories` | `boolean` | `true` | Show category filter buttons |
| `showTrending` | `boolean` | `true` | Show usage metrics |
| `recentlyUsed` | `Assistant[]` | `[]` | Recently used assistants |

### Assistant Interface

```tsx
interface Assistant {
  id: string                    // Unique identifier
  name: string                  // Display name
  description: string           // Short description
  avatar?: string              // Optional avatar URL
  category: string             // Category ID
  capabilities: string[]       // List of capabilities
  color: string                // Gradient CSS classes
  model?: string               // Optional model name
  version?: string             // Optional version
  tags?: string[]             // Optional tags
  isPremium?: boolean         // Premium status
  isActive?: boolean          // Active status
  usageCount?: number         // Usage statistics
  avgRating?: number          // Average rating
  lastUsed?: Date            // Last usage date
}
```

## Styling

### Glass Morphism

The components use glass morphism effects for a modern, translucent appearance:

```css
/* Applied automatically via Tailwind classes */
backdrop-blur-md
bg-white/10 dark:bg-black/10
border-border/50
```

### Custom Colors

The theme uses orange/amber accent colors for consistency:

```css
/* Primary gradient */
from-orange-500 to-amber-500

/* Hover states */
hover:from-orange-600 hover:to-amber-600

/* Glass effects */
shadow-orange-500/20
ring-orange-400/50
```

## Animations

### Framer Motion

Components use Framer Motion for smooth animations:

```tsx
// Card animations
whileHover={{ y: -4, scale: 1.02 }}
whileTap={{ scale: 0.98 }}

// Staggered list animations
initial={{ opacity: 0, y: 20 }}
animate={{ opacity: 1, y: 0 }}
transition={{ delay: index * 0.05 }}
```

## Customization

### Custom Assistant Colors

```tsx
const assistant = {
  color: "from-purple-500 via-pink-500 to-red-500"  // Custom gradient
}
```

### Custom Category Icons

```tsx
const categoryIcons = {
  yourCategory: YourCustomIcon,
  // Add your custom icons here
}
```

### Custom Animations

```tsx
// Override default animation variants
const customVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.8 }
}
```

## Hooks

### useNewChatDialog

Custom hook for managing dialog state:

```tsx
const {
  isOpen,              // Dialog open state
  selectedAssistantId, // Selected assistant ID
  recentSelections,    // Recently used assistants
  openDialog,          // Open dialog
  closeDialog,         // Close dialog
  selectAssistant,     // Select assistant
  handleDialogChange,  // Handle dialog change
  clearSelection,      // Clear selection
  setMostRecentAssistant // Set most recent
} = useNewChatDialog({
  onAssistantSelect: (assistant) => { ... },
  persistSelection: true,
  storageKey: 'my-chat-assistant'
})
```

### useChatKeyboardShortcuts

Hook for keyboard shortcuts:

```tsx
useChatKeyboardShortcuts(
  openDialog,  // Function to open dialog
  true         // Enable/disable shortcuts
)
```

## Accessibility

The components follow WCAG guidelines:

- ✅ Keyboard navigation
- ✅ ARIA labels and roles
- ✅ Focus management
- ✅ Screen reader support
- ✅ High contrast support
- ✅ Reduced motion support

## Performance Optimizations

- ✅ React.memo for component memoization
- ✅ useMemo for expensive computations
- ✅ useCallback for stable references
- ✅ Lazy loading with AnimatePresence
- ✅ Virtual scrolling support (ready for large lists)
- ✅ Debounced search input
- ✅ Optimized re-renders

## Browser Support

- ✅ Chrome/Edge (Modern)
- ✅ Firefox (Modern)
- ✅ Safari (Modern)
- ✅ Mobile browsers

Required features:
- CSS backdrop-filter
- CSS custom properties
- ES2020 JavaScript
- ResizeObserver API

## Examples

### Basic Example

```tsx
import { NewChatDialog } from '@/components/ui/new-chat-dialog'
import { Button } from '@/components/ui/button'
import { MessageSquarePlus } from 'lucide-react'

export function ChatButton() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <MessageSquarePlus className="h-4 w-4 mr-2" />
        New Chat
      </Button>

      <NewChatDialog
        open={open}
        onOpenChange={setOpen}
        assistants={assistants}
        onSelectAssistant={(a) => console.log(a)}
      />
    </>
  )
}
```

### Advanced Example with Custom Styling

```tsx
import { EnhancedNewChatDialog } from '@/components/ui/enhanced-new-chat-dialog'

export function CustomChatDialog() {
  const [open, setOpen] = useState(false)

  const customAssistants = [
    {
      id: 'custom',
      name: 'Custom Assistant',
      description: 'My custom assistant',
      category: 'custom',
      capabilities: ['Custom feature 1', 'Custom feature 2'],
      color: 'from-indigo-500 via-purple-500 to-pink-500',
      isPremium: true,
      usageCount: 1234,
      avgRating: 4.8
    }
  ]

  return (
    <EnhancedNewChatDialog
      open={open}
      onOpenChange={setOpen}
      assistants={customAssistants}
      onSelectAssistant={(a) => {
        // Handle selection
      }}
      showCategories={false}
      showTrending={true}
    />
  )
}
```

## Troubleshooting

### Common Issues

1. **Animations not working**: Ensure Framer Motion is installed
2. **Glass effect not visible**: Check backdrop-filter browser support
3. **Z-index issues**: Ensure dialog has proper z-index
4. **Scroll not working**: Check parent container overflow settings

### Performance Issues

1. **Slow animations**: Reduce number of simultaneous animations
2. **Large lists**: Implement virtualization
3. **Memory leaks**: Clean up event listeners and intervals

## Contributing

When contributing to these components:

1. Follow TypeScript best practices
2. Maintain accessibility standards
3. Test on multiple browsers
4. Document new features
5. Keep animations performant
6. Follow existing code style

## License

These components are part of the RAG System project and follow the same license terms.