/**
 * Frontend Security Module
 * Implements comprehensive client-side security measures including:
 * XSS prevention
 * CSRF protection
 * Content Security Policy management
 * Secure storage utilities
 * Input sanitization
 * Security event logging
 */

// Security constants
export const SECURITY_CONFIG = {
  // CSRF configuration
  CSRF: {
    tokenHeader: 'X-CSRF-Token',
    cookieName: 'csrf_token',
    tokenExpiry: 60 * 60 * 1000, // 1 hour
  },

  // CSP configuration
  CSP: {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", 'data:', 'https:'],
    'font-src': ["'self'"],
    'connect-src': ["'self'"],
    'frame-ancestors': ["'none'"],
    'form-action': ["'self'"],
    'base-uri': ["'self'"],
  },

  // XSS patterns to detect
  XSS_PATTERNS: [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
    /<iframe\b[^>]*>/gi,
    /<object\b[^>]*>/gi,
    /<embed\b[^>]*>/gi,
    /<link\b[^>]*>/gi,
    /<meta\b[^>]*>/gi,
    /vbscript:/gi,
    /data:text\/html/gi,
    /expression\s*\(/gi,
  ],

  // SQL injection patterns
  SQL_INJECTION_PATTERNS: [
    /(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)/gi,
    /(\'(OR|AND)\s+\w+\s*=\s*\w+)/gi,
    /((\%27)|(\'))\s*((\%6F)|o|(\%4F))((\%72)|r|(\%52))/gi,
    /((\%27)|(\'))\s*((\%61)|a|(\%41))((\%6E)|n|(\%4E))((\%64)|d|(\%44))/gi,
    /(--[^#]*)/gi,
    /(\/\*.*\*\/)/gi,
  ],

  // Suspicious patterns
  SUSPICIOUS_PATTERNS: [
    /\.\./gi, // Path traversal
    /<[^>]*>/gi, // HTML tags
    /document\.cookie/gi,
    /window\.location/gi,
    /innerHTML\s*=/gi,
    /outerHTML\s*=/gi,
  ],
};

// CSRF Token Manager
export class CSRFManager {
  private static instance: CSRFManager;
  private token: string | null = null;
  private tokenExpiry: number = 0;

  static getInstance(): CSRFManager {
    if (!CSRFManager.instance) {
      CSRFManager.instance = new CSRFManager();
    }
    return CSRFManager.instance;
  }

  async getToken(): Promise<string> {
    const now = Date.now();

    // Check if token is expired or missing
    if (!this.token || now > this.tokenExpiry) {
      await this.refreshToken();
    }

    return this.token!;
  }

  private async refreshToken(): Promise<void> {
    try {
      const response = await fetch('/api/auth/csrf-token', {
        method: 'GET',
        credentials: 'same-origin',
      });

      if (!response.ok) {
        throw new Error('Failed to fetch CSRF token');
      }

      const data = await response.json();
      this.token = data.token;
      this.tokenExpiry = Date.now() + SECURITY_CONFIG.CSRF.tokenExpiry;

      // Store token in cookie
      document.cookie = `${SECURITY_CONFIG.CSRF.cookieName}=${this.token}; path=/; secure; samesite=strict`;
    } catch (error) {
      console.error('CSRF token refresh failed:', error);
      this.token = null;
      this.tokenExpiry = 0;
    }
  }

  attachToRequest(headers: Record<string, string>): void {
    if (this.token) {
      headers[SECURITY_CONFIG.CSRF.tokenHeader] = this.token;
    }
  }
}

// Input Sanitizer
export class InputSanitizer {
  /**
   * Sanitize string input to prevent XSS
   */
  static sanitize(input: string): string {
    if (typeof input !== 'string') {
      return '';
    }

    return input
      .replace(/[&<>"']/g, (match) => {
        const escapeMap: Record<string, string> = {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#x27;',
        };
        return escapeMap[match] || match;
      })
      .replace(/\0/g, ''); // Remove null bytes
  }

  /**
   * Validate and sanitize numeric input
   */
  static sanitizeNumber(input: any, min?: number, max?: number): number | null {
    const num = Number(input);

    if (isNaN(num) || !isFinite(num)) {
      return null;
    }

    if (min !== undefined && num < min) {
      return null;
    }

    if (max !== undefined && num > max) {
      return null;
    }

    return num;
  }

  /**
   * Validate email format
   */
  static isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Validate URL format
   */
  static isValidURL(url: string): boolean {
    try {
      const urlObj = new URL(url);
      return ['http:', 'https:'].includes(urlObj.protocol);
    } catch {
      return false;
    }
  }

  /**
   * Check for XSS patterns
   */
  static containsXSS(input: string): boolean {
    return SECURITY_CONFIG.XSS_PATTERNS.some(pattern => pattern.test(input));
  }

  /**
   * Check for SQL injection patterns
   */
  static containsSQLInjection(input: string): boolean {
    return SECURITY_CONFIG.SQL_INJECTION_PATTERNS.some(pattern => pattern.test(input));
  }

  /**
   * Check for suspicious patterns
   */
  static isSuspicious(input: string): boolean {
    return SECURITY_CONFIG.SUSPICIOUS_PATTERNS.some(pattern => pattern.test(input));
  }

  /**
   * Comprehensive validation
   */
  static validateInput(
    input: string,
    type: 'text' | 'email' | 'url' | 'html' = 'text',
    maxLength: number = 10000
  ): { valid: boolean; sanitized?: string; error?: string } {
    // Check length
    if (input.length > maxLength) {
      return { valid: false, error: 'Input too long' };
    }

    // Check for dangerous patterns
    if (this.containsXSS(input)) {
      this.logSecurityEvent('XSS_ATTEMPT', { input: input.substring(0, 100) });
      return { valid: false, error: 'Invalid input detected' };
    }

    if (this.containsSQLInjection(input)) {
      this.logSecurityEvent('SQL_INJECTION_ATTEMPT', { input: input.substring(0, 100) });
      return { valid: false, error: 'Invalid input detected' };
    }

    // Type-specific validation
    switch (type) {
      case 'email':
        if (!this.isValidEmail(input)) {
          return { valid: false, error: 'Invalid email format' };
        }
        break;

      case 'url':
        if (!this.isValidURL(input)) {
          return { valid: false, error: 'Invalid URL format' };
        }
        break;

      case 'html':
        // For HTML content, we might want to allow certain tags
        // This would require more sophisticated sanitization
        return { valid: false, error: 'HTML content not allowed' };
    }

    // Return sanitized input
    return { valid: true, sanitized: this.sanitize(input) };
  }

  /**
   * Log security events
   */
  private static logSecurityEvent(event: string, data: any): void {
    const eventData = {
      type: event,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      data,
    };

    // Send to security endpoint
    fetch('/api/security/log-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(eventData),
    }).catch(() => {
      // Silently fail to avoid exposing security monitoring
      console.warn('Failed to log security event');
    });
  }
}

// Secure Storage Manager
export class SecureStorage {
  private static prefix = 'secure_';
  private static encryptionKey: string | null = null;

  /**
   * Store data securely with encryption
   */
  static async setSecureItem(key: string, value: any, encrypt: boolean = true): Promise<void> {
    const prefixedKey = this.prefix + key;

    try {
      let dataToStore = JSON.stringify({
        value,
        timestamp: Date.now(),
        version: '1.0',
      });

      if (encrypt) {
        dataToStore = await this.encrypt(dataToStore);
      }

      sessionStorage.setItem(prefixedKey, dataToStore);
    } catch (error) {
      console.error('Failed to store secure item:', error);
      throw new Error('Storage operation failed');
    }
  }

  /**
   * Retrieve and decrypt stored data
   */
  static async getSecureItem(key: string, encrypt: boolean = true): Promise<any> {
    const prefixedKey = this.prefix + key;
    const stored = sessionStorage.getItem(prefixedKey);

    if (!stored) {
      return null;
    }

    try {
      let decrypted = stored;

      if (encrypt) {
        decrypted = await this.decrypt(stored);
      }

      const data = JSON.parse(decrypted);

      // Check for expired data (24 hours)
      if (Date.now() - data.timestamp > 24 * 60 * 60 * 1000) {
        this.removeSecureItem(key);
        return null;
      }

      return data.value;
    } catch (error) {
      console.error('Failed to retrieve secure item:', error);
      this.removeSecureItem(key);
      return null;
    }
  }

  /**
   * Remove stored item
   */
  static removeSecureItem(key: string): void {
    const prefixedKey = this.prefix + key;
    sessionStorage.removeItem(prefixedKey);
  }

  /**
   * Simple encryption using Web Crypto API
   */
  private static async encrypt(data: string): Promise<string> {
    if (!this.encryptionKey) {
      this.encryptionKey = await this.generateKey();
    }

    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(data);

    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await crypto.subtle.importKey(
      'raw',
      encoder.encode(this.encryptionKey),
      { name: 'AES-GCM' },
      false,
      ['encrypt']
    );

    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      dataBuffer
    );

    // Combine IV and encrypted data
    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv);
    combined.set(new Uint8Array(encrypted), iv.length);

    return btoa(String.fromCharCode(...combined));
  }

  /**
   * Simple decryption using Web Crypto API
   */
  private static async decrypt(encryptedData: string): Promise<string> {
    if (!this.encryptionKey) {
      throw new Error('No encryption key available');
    }

    const encoder = new TextEncoder();
    const decoder = new TextDecoder();

    // Extract IV and encrypted data
    const combined = new Uint8Array(
      atob(encryptedData)
        .split('')
        .map(char => char.charCodeAt(0))
    );

    const iv = combined.slice(0, 12);
    const encrypted = combined.slice(12);

    const key = await crypto.subtle.importKey(
      'raw',
      encoder.encode(this.encryptionKey),
      { name: 'AES-GCM' },
      false,
      ['decrypt']
    );

    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      encrypted
    );

    return decoder.decode(decrypted);
  }

  /**
   * Generate encryption key
   */
  private static async generateKey(): Promise<string> {
    const key = crypto.getRandomValues(new Uint8Array(32));
    return Array.from(key)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
}

// Content Security Policy Manager
export class CSPManager {
  private static nonce: string;

  static initialize(): void {
    // Generate nonce for inline scripts
    this.nonce = this.generateNonce();

    // Set up CSP headers (handled by backend)
    this.monitorCSPViolations();
  }

  private static generateNonce(): string {
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    return Array.from(array)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  getNonce(): string {
    return CSPManager.nonce;
  }

  private static monitorCSPViolations(): void {
    // Listen for CSP violation reports
    document.addEventListener('securitypolicyviolation', (event) => {
      const violation = {
        blockedURI: event.blockedURI,
        documentURI: event.documentURI,
        effectiveDirective: event.effectiveDirective,
        originalPolicy: event.originalPolicy,
        referrer: event.referrer,
        sample: event.sample,
        sourceFile: event.sourceFile,
        lineNumber: event.lineNumber,
        columnNumber: event.columnNumber,
        violatedDirective: event.violatedDirective,
        timestamp: new Date().toISOString(),
      };

      // Log violation
      console.error('CSP Violation:', violation);

      // Send to security endpoint
      fetch('/api/security/csp-violation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(violation),
      }).catch(() => {
        // Silently fail
      });
    });
  }
}

// Security Event Logger
export class SecurityLogger {
  private static events: any[] = [];
  private static maxEvents = 100;

  static logEvent(
    type: string,
    data: any,
    severity: 'low' | 'medium' | 'high' | 'critical' = 'medium'
  ): void {
    const event = {
      id: crypto.randomUUID(),
      type,
      data,
      severity,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    };

    // Store in memory
    this.events.push(event);
    if (this.events.length > this.maxEvents) {
      this.events.shift();
    }

    // Log to console
    const logMethod = severity === 'critical' || severity === 'high' ? 'error' : 'warn';
    console[logMethod](`[Security Event] ${type}:`, event);

    // Send to server
    this.sendEventToServer(event);
  }

  private static sendEventToServer(event: any): void {
    // Batch send events
    setTimeout(() => {
      const eventsToSend = [...this.events];
      this.events = [];

      fetch('/api/security/log-events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ events: eventsToSend }),
      }).catch(() => {
        // Add events back if send failed
        this.events.unshift(...eventsToSend.slice(0, this.maxEvents - this.events.length));
      });
    }, 5000);
  }

  static getEvents(): any[] {
    return [...this.events];
  }

  static clearEvents(): void {
    this.events = [];
  }
}

// Initialize security on page load
document.addEventListener('DOMContentLoaded', () => {
  CSPManager.initialize();

  // Log page load for security monitoring
  SecurityLogger.logEvent('PAGE_LOAD', {
    path: window.location.pathname,
    referrer: document.referrer,
  }, 'low');
});

// Export default security utilities
export default {
  CSRFManager,
  InputSanitizer,
  SecureStorage,
  CSPManager,
  SecurityLogger,
};