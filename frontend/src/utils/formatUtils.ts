/**
 * Format Utility Functions
 *
 * Common formatting functions for dates, file sizes, duration, etc.
 */

/**
 * Format file size in human readable format
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

/**
 * Format duration in human readable format
 */
export const formatDuration = (milliseconds: number): string => {
  if (!milliseconds || milliseconds === 0) return '0s';

  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}d ${hours % 24}h ${minutes % 60}m`;
  } else if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
};

/**
 * Format duration in milliseconds to human readable format
 */
export const formatDurationMs = (milliseconds: number): string => {
  if (!milliseconds || milliseconds === 0) return '0ms';

  if (milliseconds < 1000) {
    return `${Math.round(milliseconds)}ms`;
  }

  return formatDuration(milliseconds);
};

/**
 * Format number with locale-specific formatting
 */
export const formatNumber = (num: number, locale: string = 'en-US'): string => {
  return new Intl.NumberFormat(locale).format(num);
};

/**
 * Format percentage
 */
export const formatPercentage = (value: number, decimals: number = 1): string => {
  return `${value.toFixed(decimals)}%`;
};

/**
 * Format date relative to now
 */
export const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  if (diffMs < 1000) {
    return 'Just now';
  }

  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return `${diffSecs}s ago`;
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return date.toLocaleDateString();
  }
};

/**
 * Format date to locale-specific format
 */
export const formatDate = (dateString: string, locale: string = 'en-US'): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

/**
 * Format time to locale-specific format
 */
export const formatTime = (dateString: string, locale: string = 'en-US'): string => {
  const date = new Date(dateString);
  return date.toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

/**
 * Format bytes to human readable format (alias for formatFileSize)
 */
export const formatBytes = formatFileSize;

/**
 * Truncate text with ellipsis
 */
export const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
};

/**
 * Format a rate (per second, per minute, etc.)
 */
export const formatRate = (
  value: number,
  perUnit: 'second' | 'minute' | 'hour' = 'second',
  decimals: number = 1
): string => {
  const unit = perUnit === 'second' ? '/s' : perUnit === 'minute' ? '/min' : '/h';
  return `${value.toFixed(decimals)}${unit}`;
};

/**
 * Format throughput (documents per time unit)
 */
export const formatThroughput = (
  docs: number,
  timeMs: number,
  timeUnit: 'second' | 'minute' = 'minute'
): string => {
  const timeInUnit = timeUnit === 'second' ? timeMs / 1000 : timeMs / 60000;
  const rate = timeInUnit > 0 ? docs / timeInUnit : 0;
  return formatRate(rate, timeUnit);
};

/**
 * Format currency value
 */
export const formatCurrency = (
  amount: number,
  currency: string = 'USD',
  locale: string = 'en-US'
): string => {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency
  }).format(amount);
};

/**
 * Format a large number with abbreviations (K, M, B, T)
 */
export const formatLargeNumber = (num: number): string => {
  if (num < 1000) return num.toString();

  const abbreviations = ['', 'K', 'M', 'B', 'T'];
  const exponent = Math.floor(Math.log10(num) / 3);
  const value = num / Math.pow(1000, exponent);

  return `${value.toFixed(1)}${abbreviations[exponent]}`;
};

/**
 * Format a memory size (bytes) in human readable format
 */
export const formatMemorySize = (bytes: number): string => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

/**
 * Format a timestamp to ISO string
 */
export const formatTimestamp = (date: Date = new Date()): string => {
  return date.toISOString();
};

/**
 * Format a timestamp to human readable format
 */
export const formatTimestampHuman = (date: Date = new Date()): string => {
  return date.toLocaleString();
};

/**
 * Format a URL for display (remove protocol, www)
 */
export const formatUrl = (url: string): string => {
  try {
    const urlObj = new URL(url);
    let display = urlObj.hostname;

    if (display.startsWith('www.')) {
      display = display.slice(4);
    }

    return display;
  } catch {
    return url;
  }
};

/**
 * Format a file name with extension highlighting
 */
export const formatFileName = (filename: string): { name: string; extension: string } => {
  const lastDotIndex = filename.lastIndexOf('.');

  if (lastDotIndex === -1 || lastDotIndex === 0) {
    return { name: filename, extension: '' };
  }

  return {
    name: filename.slice(0, lastDotIndex),
    extension: filename.slice(lastDotIndex + 1)
  };
};

/**
 * Format a version number
 */
export const formatVersion = (version: string): string => {
  // Ensure version follows semver format
  const semverRegex = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;
  const match = version.match(semverRegex);

  if (!match) {
    return version; // Return as-is if not a valid semver
  }

  const [, major, minor, patch, prerelease, build] = match;
  let formatted = `${major}.${minor}.${patch}`;

  if (prerelease) {
    formatted += `-${prerelease}`;
  }

  if (build) {
    formatted += `+${build}`;
  }

  return formatted;
};

/**
 * Format a score or rating
 */
export const formatScore = (
  score: number,
  maxScore: number = 100,
  decimals: number = 1
): string => {
  const percentage = (score / maxScore) * 100;
  return `${percentage.toFixed(decimals)}%`;
};

/**
 * Format a range of values
 */
export const formatRange = (min: number, max: number): string => {
  if (min === max) {
    return min.toString();
  }
  return `${min} - ${max}`;
};

/**
 * Format a list of items
 */
export const formatList = (
  items: string[],
  maxItems: number = 3,
  separator: string = ', '
): string => {
  if (items.length <= maxItems) {
    return items.join(separator);
  }

  const visibleItems = items.slice(0, maxItems);
  const remainingCount = items.length - maxItems;

  return `${visibleItems.join(separator)} and ${remainingCount} more`;
};