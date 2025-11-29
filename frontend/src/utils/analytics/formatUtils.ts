import { format, formatDistanceToNow, parseISO, isAfter, isBefore } from 'date-fns';

// Date and time formatting utilities

export const formatDate = (
  date: string | Date,
  formatString: string = 'MMM dd, yyyy'
): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return format(dateObj, formatString);
  } catch (error) {
    return String(date);
  }
};

export const formatDateTime = (
  date: string | Date,
  includeSeconds: boolean = false
): string => {
  const formatString = includeSeconds ? 'MMM dd, yyyy HH:mm:ss' : 'MMM dd, yyyy HH:mm';
  return formatDate(date, formatString);
};

export const formatRelativeTime = (date: string | Date): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return formatDistanceToNow(dateObj, { addSuffix: true });
  } catch (error) {
    return String(date);
  }
};

export const formatTimeRange = (
  start: string | Date,
  end: string | Date,
  formatString: string = 'MMM dd, yyyy HH:mm'
): string => {
  const formattedStart = formatDate(start, formatString);
  const formattedEnd = formatDate(end, formatString);
  return `${formattedStart} - ${formattedEnd}`;
};

export const isInTimeRange = (
  date: string | Date,
  start: string | Date,
  end: string | Date
): boolean => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    const startObj = typeof start === 'string' ? parseISO(start) : start;
    const endObj = typeof end === 'string' ? parseISO(end) : end;

    return isAfter(dateObj, startObj) && isBefore(dateObj, endObj);
  } catch (error) {
    return false;
  }
};

// Number formatting utilities

export const formatNumber = (
  value: number,
  options: {
    decimals?: number;
    style?: 'decimal' | 'currency' | 'percent';
    currency?: string;
    locale?: string;
    compact?: boolean;
  } = {}
): string => {
  const {
    decimals = 2,
    style = 'decimal',
    currency = 'USD',
    locale = 'en-US',
    compact = false,
  } = options;

  try {
    if (compact && style === 'decimal') {
      return new Intl.NumberFormat(locale, {
        notation: 'compact',
        maximumFractionDigits: decimals,
      }).format(value);
    }

    return new Intl.NumberFormat(locale, {
      style,
      currency: style === 'currency' ? currency : undefined,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
  } catch (error) {
    return value.toLocaleString();
  }
};

export const formatLargeNumber = (value: number, decimals: number = 1): string => {
  if (value === 0) return '0';

  const absValue = Math.abs(value);
  let formattedValue: string;
  let suffix: string = '';

  if (absValue >= 1000000000) {
    formattedValue = (value / 1000000000).toFixed(decimals);
    suffix = 'B';
  } else if (absValue >= 1000000) {
    formattedValue = (value / 1000000).toFixed(decimals);
    suffix = 'M';
  } else if (absValue >= 1000) {
    formattedValue = (value / 1000).toFixed(decimals);
    suffix = 'K';
  } else {
    formattedValue = value.toFixed(decimals);
  }

  return `${formattedValue}${suffix}`;
};

export const formatPercentage = (
  value: number,
  decimals: number = 1,
  multiply: boolean = true
): string => {
  const percentage = multiply ? value * 100 : value;
  return `${percentage.toFixed(decimals)}%`;
};

export const formatBytes = (bytes: number, decimals: number = 2): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
};

export const formatDuration = (
  milliseconds: number,
  showMilliseconds: boolean = false
): string => {
  if (milliseconds < 1000) {
    return showMilliseconds ? `${milliseconds}ms` : '< 1s';
  }

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

// String formatting utilities

export const truncateString = (
  str: string,
  maxLength: number,
  suffix: string = '...'
): string => {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength - suffix.length) + suffix;
};

export const capitalizeWords = (str: string): string => {
  return str.replace(/\b\w/g, char => char.toUpperCase());
};

export const camelCaseToTitle = (str: string): string => {
  return str
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, char => char.toUpperCase())
    .trim();
};

export const snakeCaseToTitle = (str: string): string => {
  return str
    .split('_')
    .map(word => capitalizeWords(word))
    .join(' ');
};

export const kebabCaseToTitle = (str: string): string => {
  return str
    .split('-')
    .map(word => capitalizeWords(word))
    .join(' ');
};

// Metric formatting utilities

export const formatMetricValue = (
  value: number | string,
  unit?: string,
  options: {
    decimals?: number;
    locale?: string;
    style?: 'decimal' | 'currency' | 'percent';
  } = {}
): string => {
  if (typeof value === 'string') {
    return value;
  }

  const { decimals = 2, locale = 'en-US', style = 'decimal' } = options;

  if (!unit) {
    return formatNumber(value, { decimals, style, locale });
  }

  const normalizedUnit = unit.toLowerCase();

  switch (normalizedUnit) {
    case 'bytes':
    case 'b':
      return formatBytes(value, decimals);

    case 'percentage':
    case 'percent':
    case '%':
      return formatPercentage(value, decimals);

    case 'duration':
    case 'ms':
    case 'seconds':
    case 's':
      return formatDuration(value);

    case 'currency':
    case 'usd':
    case '$':
      return formatNumber(value, {
        decimals,
        style: 'currency',
        currency: 'USD',
        locale,
      });

    case 'count':
    case 'number':
      return formatLargeNumber(value, decimals);

    default:
      return `${formatNumber(value, { decimals, style, locale })} ${unit}`;
  }
};

export const formatTrend = (
  value: number,
  decimals: number = 1
): string => {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
};

export const formatTrendIcon = (trend: 'up' | 'down' | 'stable'): string => {
  switch (trend) {
    case 'up':
      return '↑';
    case 'down':
      return '↓';
    case 'stable':
      return '→';
    default:
      return '→';
  }
};

export const formatStatus = (
  status: string,
  style: 'badge' | 'text' = 'badge'
): { text: string; color: string; bgColor: string } => {
  const normalizedStatus = status.toLowerCase();

  const statusConfig = {
    active: { text: 'Active', color: 'text-green-700', bgColor: 'bg-green-100' },
    inactive: { text: 'Inactive', color: 'text-gray-700', bgColor: 'bg-gray-100' },
    pending: { text: 'Pending', color: 'text-yellow-700', bgColor: 'bg-yellow-100' },
    error: { text: 'Error', color: 'text-red-700', bgColor: 'bg-red-100' },
    success: { text: 'Success', color: 'text-green-700', bgColor: 'bg-green-100' },
    warning: { text: 'Warning', color: 'text-yellow-700', bgColor: 'bg-yellow-100' },
    info: { text: 'Info', color: 'text-blue-700', bgColor: 'bg-blue-100' },
    critical: { text: 'Critical', color: 'text-red-700', bgColor: 'bg-red-100' },
    connected: { text: 'Connected', color: 'text-green-700', bgColor: 'bg-green-100' },
    disconnected: { text: 'Disconnected', color: 'text-gray-700', bgColor: 'bg-gray-100' },
    connecting: { text: 'Connecting', color: 'text-blue-700', bgColor: 'bg-blue-100' },
  };

  return statusConfig[normalizedStatus] || {
    text: capitalizeWords(status),
    color: 'text-gray-700',
    bgColor: 'bg-gray-100',
  };
};

// URL and path formatting utilities

export const formatUrl = (url: string, maxLength?: number): string => {
  try {
    const urlObj = new URL(url);
    const formatted = `${urlObj.protocol}//${urlObj.hostname}${urlObj.pathname}`;
    return maxLength ? truncateString(formatted, maxLength) : formatted;
  } catch (error) {
    return maxLength ? truncateString(url, maxLength) : url;
  }
};

export const formatFilePath = (path: string, maxLength?: number): string => {
  const parts = path.split('/');
  const filename = parts[parts.length - 1];
  const directory = parts.slice(0, -1).join('/');

  if (maxLength && path.length > maxLength) {
    const availableLength = maxLength - filename.length - 10; // Reserve space for ellipsis and filename
    if (availableLength > 0) {
      return `.../${truncateString(directory, availableLength)}/${filename}`;
    } else {
      return `.../${filename}`;
    }
  }

  return path;
};

// Validation formatting utilities

export const formatValidationErrors = (
  errors: Record<string, string[]> | string[]
): string => {
  if (Array.isArray(errors)) {
    return errors.join(', ');
  }

  return Object.values(errors).flat().join(', ');
};

export const formatSearchHighlight = (
  text: string,
  query: string,
  highlightClass: string = 'bg-yellow-200'
): string => {
  if (!query.trim()) return text;

  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(regex, `<span class="${highlightClass}">$1</span>`);
};

// Export utilities

export const formatCsvValue = (value: any): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    // Escape quotes and wrap in quotes if contains comma or quote
    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }
  if (typeof value === 'number') {
    return value.toString();
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return JSON.stringify(value);
};

export const formatJsonForExport = (data: any, indent: number = 2): string => {
  try {
    return JSON.stringify(data, null, indent);
  } catch (error) {
    return '{}';
  }
};