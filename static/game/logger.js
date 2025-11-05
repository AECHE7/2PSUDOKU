/**
 * Production-safe logging utility
 * Automatically disables debug logs in production
 */

const Logger = {
  isDevelopment: window.location.hostname === 'localhost' || 
                 window.location.hostname === '127.0.0.1' ||
                 window.location.search.includes('debug=true'),
  
  debug: function(...args) {
    if (this.isDevelopment) {
      console.log(...args);
    }
  },
  
  info: function(...args) {
    console.info(...args);
  },
  
  warn: function(...args) {
    console.warn(...args);
  },
  
  error: function(...args) {
    console.error(...args);
  },
  
  // Keep critical logs always on
  critical: function(...args) {
    console.error('[CRITICAL]', ...args);
  }
};

// Export for use in other files
window.Logger = Logger;
