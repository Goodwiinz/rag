/**
 * Format Utilities
 *
 * Utility functions for formatting durations, file sizes, and relative times
 * throughout the application.
 */

/**
 * Format a duration in milliseconds to a human-readable string
 * @param ms - Duration in milliseconds
 * @returns Formatted duration string (e.g., "2h 30m", "45s", "1.2s")
 */
export function formatDuration(ms: number): string {
  if (ms < 0) return '0s';

  if (ms < 1000) {
    return `${ms}ms`;
  }

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    const remainingHours = hours % 24;
    return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
  }

  if (hours > 0) {
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }

  if (minutes > 0) {
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }

  if (seconds >= 10) {
    return `${seconds}s`;
  }

  // For durations under 10 seconds, show one decimal place
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format a file size in bytes to a human-readable string
 * @param bytes - Size in bytes
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted file size string (e.g., "1.5 MB", "256 KB")
 */
export function formatFileSize(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 B';
  if (bytes < 0) return '0 B';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const index = Math.min(i, sizes.length - 1);

  const value = bytes / Math.pow(k, index);

  // Avoid showing unnecessary decimals for whole numbers
  if (value === Math.floor(value)) {
    return `${value} ${sizes[index]}`;
  }

  return `${value.toFixed(dm)} ${sizes[index]}`;
}

/**
 * Format a timestamp to a relative time string
 * @param timestamp - Date, timestamp number (ms), or ISO string
 * @returns Relative time string (e.g., "2 minutes ago", "in 3 hours")
 */
export function formatRelativeTime(timestamp: Date | number | string): string {
  const now = Date.now();
  let time: number;

  if (timestamp instanceof Date) {
    time = timestamp.getTime();
  } else if (typeof timestamp === 'string') {
    time = new Date(timestamp).getTime();
  } else {
    time = timestamp;
  }

  const diff = now - time;
  const absDiff = Math.abs(diff);
  const isPast = diff > 0;

  const seconds = Math.floor(absDiff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  const format = (value: number, unit: string): string => {
    const plural = value !== 1 ? 's' : '';
    if (isPast) {
      return `${value} ${unit}${plural} ago`;
    }
    return `in ${value} ${unit}${plural}`;
  };

  if (seconds < 5) {
    return 'just now';
  }

  if (seconds < 60) {
    return format(seconds, 'second');
  }

  if (minutes < 60) {
    return format(minutes, 'minute');
  }

  if (hours < 24) {
    return format(hours, 'hour');
  }

  if (days < 7) {
    return format(days, 'day');
  }

  if (weeks < 4) {
    return format(weeks, 'week');
  }

  if (months < 12) {
    return format(months, 'month');
  }

  return format(years, 'year');
}

/**
 * Format a percentage value
 * @param value - Value between 0 and 1, or 0 and 100
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted percentage string (e.g., "75%", "99.5%")
 */
export function formatPercentage(value: number, decimals: number = 0): string {
  // Handle values that are already percentages (0-100)
  const percentage = value > 1 ? value : value * 100;
  return `${percentage.toFixed(decimals)}%`;
}

/**
 * Format a number with thousand separators
 * @param num - Number to format
 * @returns Formatted number string (e.g., "1,234,567")
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('en-US');
}

/**
 * Format a timestamp to a short time string
 * @param timestamp - Date, timestamp number (ms), or ISO string
 * @returns Short time string (e.g., "14:30", "09:15")
 */
export function formatTime(timestamp: Date | number | string): string {
  let date: Date;

  if (timestamp instanceof Date) {
    date = timestamp;
  } else if (typeof timestamp === 'string') {
    date = new Date(timestamp);
  } else {
    date = new Date(timestamp);
  }

  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}
