/**
 * Notification Center Component
 *
 * Comprehensive notification system with toast notifications, badges,
 * and real-time updates for document processing events.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import {
  BellIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { useRealtimeProcessing } from '@/hooks/useRealtimeProcessing';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { NotificationItem } from '@/types/realtime-processing';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/utils/formatUtils';

interface NotificationCenterProps {
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  maxVisible?: number;
  showBadge?: boolean;
  showHistory?: boolean;
  autoHideDuration?: number;
  enableSound?: boolean;
  enableDesktop?: boolean;
  className?: string;
}

interface ToastNotificationProps {
  notification: NotificationItem;
  onClose: () => void;
  onAction?: (action: NotificationItem['actions'][0]) => void;
  autoHide?: boolean;
  duration?: number;
}

interface NotificationHistoryProps {
  notifications: NotificationItem[];
  onClearAll: () => void;
  onDismiss: (id: string) => void;
  onAction: (id: string, action: NotificationItem['actions'][0]) => void;
  maxHeight?: number;
}

interface NotificationBadgeProps {
  count: number;
  showZero?: boolean;
  maxCount?: number;
  className?: string;
}

// Position configurations
const positionClasses = {
  'top-right': 'fixed top-4 right-4 z-50',
  'top-left': 'fixed top-4 left-4 z-50',
  'bottom-right': 'fixed bottom-4 right-4 z-50',
  'bottom-left': 'fixed bottom-4 left-4 z-50',
};

// Notification type configurations
const notificationConfigs = {
  success: {
    icon: CheckCircleIcon,
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    iconColor: 'text-green-500',
    titleColor: 'text-green-900',
    messageColor: 'text-green-800',
  },
  error: {
    icon: ExclamationTriangleIcon,
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    iconColor: 'text-red-500',
    titleColor: 'text-red-900',
    messageColor: 'text-red-800',
  },
  warning: {
    icon: ExclamationTriangleIcon,
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    iconColor: 'text-yellow-500',
    titleColor: 'text-yellow-900',
    messageColor: 'text-yellow-800',
  },
  info: {
    icon: InformationCircleIcon,
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    iconColor: 'text-blue-500',
    titleColor: 'text-blue-900',
    messageColor: 'text-blue-800',
  },
};

// Helper Components
const NotificationBadge: React.FC<NotificationBadgeProps> = ({
  count,
  showZero = false,
  maxCount = 99,
  className
}) => {
  if (count === 0 && !showZero) return null;

  const displayCount = count > maxCount ? `${maxCount}+` : count.toString();

  return (
    <span className={cn(
      'inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white bg-red-500 rounded-full min-w-[20px]',
      count > 0 && 'animate-pulse',
      className
    )}>
      {displayCount}
    </span>
  );
};

const ToastNotification: React.FC<ToastNotificationProps> = ({
  notification,
  onClose,
  onAction,
  autoHide = true,
  duration = 5000
}) => {
  const [isVisible, setIsVisible] = useState(true);
  const timerRef = useRef<NodeJS.Timeout>();

  const config = notificationConfigs[notification.type];
  const Icon = config.icon;

  // Auto-hide timer
  useEffect(() => {
    if (autoHide && notification.autoHide !== false) {
      timerRef.current = setTimeout(() => {
        setIsVisible(false);
      }, notification.autoHideDelay || duration);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [autoHide, notification.autoHide, notification.autoHideDelay, duration]);

  const handleClose = useCallback(() => {
    setIsVisible(false);
    onClose();
  }, [onClose]);

  const handleAction = useCallback((action: NotificationItem['actions'][0]) => {
    if (onAction) {
      onAction(action);
    }
    handleClose();
  }, [onAction, handleClose]);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: -50, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -50, scale: 0.95 }}
          className={cn(
            'flex items-start space-x-3 p-4 rounded-lg border shadow-lg max-w-sm w-full',
            config.bgColor,
            config.borderColor
          )}
        >
          <Icon className={cn('flex-shrink-0 w-5 h-5 mt-0.5', config.iconColor)} />

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className={cn('text-sm font-medium', config.titleColor)}>
                  {notification.title}
                </h4>
                <p className={cn('text-sm mt-1', config.messageColor)}>
                  {notification.message}
                </p>

                {/* Document reference */}
                {notification.documentId && (
                  <div className="flex items-center space-x-1 mt-2">
                    <DocumentTextIcon className="w-3 h-3 text-gray-400" />
                    <span className="text-xs text-gray-500">
                      Document ID: {notification.documentId.slice(0, 8)}...
                    </span>
                  </div>
                )}

                {/* Actions */}
                {notification.actions && notification.actions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {notification.actions.map((action, index) => (
                      <button
                        key={index}
                        onClick={() => handleAction(action)}
                        className="text-xs font-medium bg-white bg-opacity-70 hover:bg-opacity-100 px-2 py-1 rounded border border-gray-300 hover:border-gray-400 transition-colors"
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={handleClose}
                className="flex-shrink-0 ml-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

const NotificationHistory: React.FC<NotificationHistoryProps> = ({
  notifications,
  onClearAll,
  onDismiss,
  onAction,
  maxHeight = 400
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const visibleNotifications = isExpanded ? notifications : notifications.slice(0, 5);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="bg-white rounded-lg shadow-xl border border-gray-200 w-96 max-h-[80vh] overflow-hidden"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">
            Notifications ({notifications.length})
          </h3>
          <div className="flex items-center space-x-2">
            {notifications.length > 0 && (
              <button
                onClick={onClearAll}
                className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                Clear All
              </button>
            )}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              {isExpanded ? (
                <ChevronUpIcon className="w-4 h-4" />
              ) : (
                <ChevronDownIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div
        className="overflow-y-auto"
        style={{ maxHeight }}
      >
        {visibleNotifications.length === 0 ? (
          <div className="p-8 text-center">
            <BellIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500">No notifications</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {visibleNotifications.map((notification) => {
              const config = notificationConfigs[notification.type];
              const Icon = config.icon;

              return (
                <div
                  key={notification.id}
                  className={cn('p-4', config.bgColor)}
                >
                  <div className="flex items-start space-x-3">
                    <Icon className={cn('flex-shrink-0 w-5 h-5 mt-0.5', config.iconColor)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className={cn('text-sm font-medium', config.titleColor)}>
                            {notification.title}
                          </h4>
                          <p className={cn('text-sm mt-1', config.messageColor)}>
                            {notification.message}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {formatRelativeTime(notification.timestamp)}
                          </p>
                        </div>
                        <button
                          onClick={() => onDismiss(notification.id)}
                          className="flex-shrink-0 ml-2 text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          <XMarkIcon className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Actions */}
                      {notification.actions && notification.actions.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {notification.actions.map((action, index) => (
                            <button
                              key={index}
                              onClick={() => onAction(notification.id, action)}
                              className="text-xs font-medium bg-white bg-opacity-70 hover:bg-opacity-100 px-2 py-1 rounded border border-gray-300 hover:border-gray-400 transition-colors"
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Show more button */}
      {!isExpanded && notifications.length > 5 && (
        <div className="px-4 py-2 border-t border-gray-200">
          <button
            onClick={() => setIsExpanded(true)}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            Show {notifications.length - 5} more
          </button>
        </div>
      )}
    </motion.div>
  );
};

// Main NotificationCenter Component
export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  position = 'top-right',
  maxVisible = 5,
  showBadge = true,
  showHistory = true,
  autoHideDuration = 5000,
  enableSound = true,
  enableDesktop = true,
  className
}) => {
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [activeToasts, setActiveToasts] = useState<Map<string, NodeJS.Timeout>>(new Map());

  const {
    documents,
    notifications,
    clearNotifications
  } = useRealtimeProcessing();

  const unreadCount = notifications.filter(n => !n.autoHide).length;

  // Sound notification
  const playNotificationSound = useCallback(() => {
    if (!enableSound) return;

    try {
      // Create a simple beep sound
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800;
      oscillator.type = 'sine';
      gainNode.gain.value = 0.1;

      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
      console.warn('Could not play notification sound:', error);
    }
  }, [enableSound]);

  // Desktop notification
  const showDesktopNotification = useCallback((notification: NotificationItem) => {
    if (!enableDesktop || !('Notification' in window)) return;

    if (Notification.permission === 'granted') {
      new Notification(notification.title, {
        body: notification.message,
        icon: '/favicon.ico',
        tag: notification.id,
      });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          new Notification(notification.title, {
            body: notification.message,
            icon: '/favicon.ico',
            tag: notification.id,
          });
        }
      });
    }
  }, [enableDesktop]);

  // Handle new notifications
  useEffect(() => {
    const latestNotification = notifications[0];
    if (!latestNotification) return;

    // Play sound for important notifications
    if (latestNotification.type === 'error' || latestNotification.type === 'warning') {
      playNotificationSound();
    }

    // Show desktop notification
    showDesktopNotification(latestNotification);

    // Auto-hide toast notifications
    if (latestNotification.autoHide !== false) {
      const timer = setTimeout(() => {
        setActiveToasts(prev => {
          const newMap = new Map(prev);
          newMap.delete(latestNotification.id);
          return newMap;
        });
      }, latestNotification.autoHideDelay || autoHideDuration);

      setActiveToasts(prev => new Map(prev).set(latestNotification.id, timer));
    }
  }, [notifications, playNotificationSound, showDesktopNotification, autoHideDuration]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      activeToasts.forEach(timer => clearTimeout(timer));
    };
  }, [activeToasts]);

  // Request notification permissions on mount
  useEffect(() => {
    if (enableDesktop && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, [enableDesktop]);

  const handleClearNotifications = useCallback(() => {
    clearNotifications();
    activeToasts.forEach(timer => clearTimeout(timer));
    setActiveToasts(new Map());
  }, [clearNotifications, activeToasts]);

  const handleDismissNotification = useCallback((id: string) => {
    const timer = activeToasts.get(id);
    if (timer) {
      clearTimeout(timer);
      setActiveToasts(prev => {
        const newMap = new Map(prev);
        newMap.delete(id);
        return newMap;
      });
    }
  }, [activeToasts]);

  const handleNotificationAction = useCallback((
    notificationId: string,
    action: NotificationItem['actions'][0]
  ) => {
    action.action();
    handleDismissNotification(notificationId);
  }, [handleDismissNotification]);

  // Filter toast notifications (only recent ones)
  const toastNotifications = notifications.slice(0, maxVisible).filter(n =>
    !activeToasts.has(n.id)
  );

  return (
    <>
      {/* Toast notifications */}
      <div className={cn(positionClasses[position], 'space-y-2', className)}>
        <AnimatePresence>
          {toastNotifications.map((notification) => (
            <ToastNotification
              key={notification.id}
              notification={notification}
              onClose={() => handleDismissNotification(notification.id)}
              onAction={(action) => handleNotificationAction(notification.id, action)}
              autoHide={notification.autoHide !== false}
              duration={notification.autoHideDelay || autoHideDuration}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Notification bell button */}
      {showHistory && (
        <div className={cn(positionClasses[position], 'mt-16')}>
          <div className="relative">
            <button
              onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              className={cn(
                'relative p-2 rounded-lg bg-white border border-gray-200 shadow-md hover:shadow-lg transition-all duration-200',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
              )}
            >
              <BellIcon className="w-5 h-5 text-gray-600" />
              {showBadge && (
                <div className="absolute -top-1 -right-1">
                  <NotificationBadge count={unreadCount} />
                </div>
              )}
            </button>

            {/* Notification history dropdown */}
            {createPortal(
              <AnimatePresence>
                {isHistoryOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setIsHistoryOpen(false)}
                    />
                    <div className={cn('absolute mt-2', positionClasses[position])}>
                      <NotificationHistory
                        notifications={notifications}
                        onClearAll={handleClearNotifications}
                        onDismiss={handleDismissNotification}
                        onAction={handleNotificationAction}
                      />
                    </div>
                  </>
                )}
              </AnimatePresence>,
              document.body
            )}
          </div>
        </div>
      )}
    </>
  );
};

// Hook for notification management
export const useNotificationCenter = () => {
  const {
    notifications,
    clearNotifications,
  } = useRealtimeProcessing();

  const store = useRealtimeProcessingStore();

  const addNotification = useCallback((
    type: NotificationItem['type'],
    title: string,
    message: string,
    options: Partial<Omit<NotificationItem, 'id' | 'type' | 'title' | 'message'>> = {}
  ) => {
    store.addNotification({
      type,
      title,
      message,
      timestamp: new Date().toISOString(),
      ...options
    });
  }, [store]);

  const addSuccessNotification = useCallback((title: string, message: string, options?: any) => {
    addNotification('success', title, message, options);
  }, [addNotification]);

  const addErrorNotification = useCallback((title: string, message: string, options?: any) => {
    addNotification('error', title, message, options);
  }, [addNotification]);

  const addWarningNotification = useCallback((title: string, message: string, options?: any) => {
    addNotification('warning', title, message, options);
  }, [addNotification]);

  const addInfoNotification = useCallback((title: string, message: string, options?: any) => {
    addNotification('info', title, message, options);
  }, [addNotification]);

  return {
    notifications,
    unreadCount: notifications.filter(n => !n.autoHide).length,
    addNotification,
    addSuccessNotification,
    addErrorNotification,
    addWarningNotification,
    addInfoNotification,
    clearNotifications,
  };
};

export default NotificationCenter;