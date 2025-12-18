"use client"

import { useState, useCallback, useEffect } from 'react'
import { Assistant } from '@/components/ui/new-chat-dialog'

interface UseNewChatDialogOptions {
  onAssistantSelect?: (assistant: Assistant) => void
  persistSelection?: boolean
  storageKey?: string
}

export function useNewChatDialog(options: UseNewChatDialogOptions = {}) {
  const {
    onAssistantSelect,
    persistSelection = true,
    storageKey = 'selected-chat-assistant'
  } = options

  const [isOpen, setIsOpen] = useState(false)
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null)
  const [recentSelections, setRecentSelections] = useState<Assistant[]>([])

  // Load persisted selections on mount
  useEffect(() => {
    if (persistSelection && typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem(storageKey)
        if (stored) {
          const data = JSON.parse(stored)
          setSelectedAssistantId(data.selectedId)
          setRecentSelections(data.recent || [])
        }
      } catch (error) {
        console.warn('Failed to load chat assistant preferences:', error)
      }
    }
  }, [persistSelection, storageKey])

  // Persist selections when they change
  const persistData = useCallback((id: string | null, recent: Assistant[]) => {
    if (persistSelection && typeof window !== 'undefined') {
      try {
        localStorage.setItem(storageKey, JSON.stringify({
          selectedId: id,
          recent: recent.slice(0, 5) // Keep only last 5 selections
        }))
      } catch (error) {
        console.warn('Failed to persist chat assistant preferences:', error)
      }
    }
  }, [persistSelection, storageKey])

  const openDialog = useCallback(() => {
    setIsOpen(true)
  }, [])

  const closeDialog = useCallback(() => {
    setIsOpen(false)
  }, [])

  const selectAssistant = useCallback((assistant: Assistant) => {
    setSelectedAssistantId(assistant.id)

    // Update recent selections
    setRecentSelections(prev => {
      const filtered = prev.filter(a => a.id !== assistant.id)
      const updated = [assistant, ...filtered].slice(0, 5)
      persistData(assistant.id, updated)
      return updated
    })

    // Call custom handler
    onAssistantSelect?.(assistant)

    // Close dialog
    closeDialog()
  }, [onAssistantSelect, closeDialog, persistData])

  const handleDialogChange = useCallback((open: boolean) => {
    if (!open) {
      setIsOpen(false)
    }
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedAssistantId(null)
    persistData(null, [])
    setRecentSelections([])
  }, [persistData])

  const setMostRecentAssistant = useCallback((assistant: Assistant) => {
    setSelectedAssistantId(assistant.id)
    setRecentSelections(prev => {
      const filtered = prev.filter(a => a.id !== assistant.id)
      const updated = [assistant, ...filtered].slice(0, 5)
      persistData(assistant.id, updated)
      return updated
    })
  }, [persistData])

  return {
    isOpen,
    selectedAssistantId,
    recentSelections,
    openDialog,
    closeDialog,
    selectAssistant,
    handleDialogChange,
    clearSelection,
    setMostRecentAssistant
  }
}

// Hook for keyboard shortcuts
export function useChatKeyboardShortcuts(
  openDialog: () => void,
  isEnabled: boolean = true
) {
  useEffect(() => {
    if (!isEnabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd/Ctrl + K to open new chat
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        openDialog()
      }

      // Escape to close (handled by dialog component)
      // The dialog component already handles escape, so we don't need to add it here
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [openDialog, isEnabled])
}