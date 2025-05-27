/**
 * Shared thumbnail caching module for all components
 */

// Cache for thumbnails
export interface ThumbnailCache {
  [key: string]: {
    url: string;
    timestamp: number;
    blob?: Blob;
    objectUrl?: string;
  };
}

// In-memory thumbnail cache (only lasts during the session)
export const thumbnailCache: ThumbnailCache = {};

// Cache expiration time in milliseconds (24 hours)
export const CACHE_EXPIRATION = 24 * 60 * 60 * 1000;

// Helper function to cleanup a specific cache entry
export const cleanupCacheEntry = (id: string): void => {
  if (thumbnailCache[id]?.objectUrl) {
    URL.revokeObjectURL(thumbnailCache[id].objectUrl!);
  }
  delete thumbnailCache[id];
};

// Helper function to clear entire cache
export const clearCache = (): void => {
  // Revoke all object URLs first
  Object.keys(thumbnailCache).forEach(id => {
    if (thumbnailCache[id].objectUrl) {
      URL.revokeObjectURL(thumbnailCache[id].objectUrl!);
    }
  });
  
  // Clear the cache object
  Object.keys(thumbnailCache).forEach(key => {
    delete thumbnailCache[key];
  });
};

// Clean up expired cache entries
export const cleanupExpiredCache = (): void => {
  const now = Date.now();
  Object.keys(thumbnailCache).forEach(id => {
    const cache = thumbnailCache[id];
    if (now - cache.timestamp > CACHE_EXPIRATION) {
      cleanupCacheEntry(id);
    }
  });
}; 