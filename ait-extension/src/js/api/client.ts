import axios, { AxiosInstance, AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { 
  IngestOptions, 
  SearchType, 
  VideoFile, 
  IngestProgress, 
  AuthStatus,
  SearchResults,
  ApiResponse,
  VideoDetails,
  CatalogStats,
  PipelineStep,
  SortField,
  SortOrder,
  ListVideoOptions
} from '../types/api';

// Connection status event handling
type ConnectionListener = (isConnected: boolean) => void;
const connectionListeners: ConnectionListener[] = [];
let isConnected = true;
let authErrorCallback: (() => void) | null = null;

// API configuration - Updated to match the current server setup
const API_BASE_URL = 'http://localhost:8001/api';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false // No authentication required
});

// Add interceptors to track connection status
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // If we get a successful response, we're connected
    if (!isConnected) {
      isConnected = true;
      notifyConnectionListeners(true);
    }
    return response;
  },
  (error: AxiosError) => {
    // Network errors indicate disconnection
    if (error.code === 'ECONNABORTED' || !error.response) {
      if (isConnected) {
        isConnected = false;
        notifyConnectionListeners(false);
      }
    }
    // Note: No auth error handling needed since authentication is disabled
    return Promise.reject(error);
  }
);

// Function to notify all connection listeners
function notifyConnectionListeners(connected: boolean) {
  connectionListeners.forEach(listener => listener(connected));
}

// Auth API - DEPRECATED: Authentication has been removed but keeping for compatibility
export const authApi = {
  async login(email: string, password: string) {
    // Return fake success since auth is disabled
    return { success: true, message: "Authentication disabled - using local mode" };
  },

  async signup(email: string, password: string) {
    // Return fake success since auth is disabled
    return { success: true, message: "Authentication disabled - using local mode" };
  },

  async logout() {
    // Return fake success since auth is disabled
    return { success: true, message: "Authentication disabled - using local mode" };
  },

  async getStatus() {
    // Return fake authenticated status since auth is disabled
    return { 
      success: true, 
      data: { 
        authenticated: true, 
        user: { 
          id: "local-user", 
          email: "local@localhost", 
          profile_type: "local" 
        } 
      } 
    };
  }
};

// Ingest API
export const ingestApi = {
  async startIngest(directory: string, options: IngestOptions) {
    try {
      // Map parameters to match server expectations
      const requestData = {
        directory,
        recursive: options.recursive ?? true,
        // Map client options to server parameter names
        ai_analysis: options.ai_analysis ?? false,  // Server expects ai_analysis, maps to ai_analysis_enabled
        store_database: options.store_database ?? false,  // Server expects store_database, maps to database_storage
        generate_embeddings: options.generate_embeddings ?? false,
        force_reprocess: options.force_reprocess ?? false
      };
      
      const response = await apiClient.post('/ingest', requestData);
      return response.data;
    } catch (error: any) {
      console.error('AIServer: Error starting ingest:', error);
      if (error.response && error.response.data) {
        console.error('AIServer: Server error details:', error.response.data);
        const message = error.response.data.error || 'Failed to start ingest (server error)';
        throw new Error(message);
      }
      throw new Error(error.message || 'Failed to start ingest process (network or unknown error)');
    }
  },

  async getProgress() {
    const response = await apiClient.get('/progress');
    return response.data;
  },

  async getResults() {
    // This endpoint doesn't exist in current server, return placeholder
    return { success: true, data: { results: [] } };
  }
};

// Search API
export const searchApi = {
  async search(query: string, searchType: SearchType = 'hybrid', limit: number = 20): Promise<SearchResults> {
    // For similar search, this shouldn't be called directly from generic search UI
    if (searchType === 'similar') {
      console.warn('Attempted to use general search for similar items. Use findSimilar instead.');
      return { results: [], total: 0, query, search_type: searchType }; 
    }
    
    if (!query.trim()) {
      console.warn('Search query is empty. Returning empty results for keyword search.');
      return { results: [], total: 0, query, search_type: searchType };
    }
    
    // Backend /api/search endpoint
    const response = await apiClient.get('/search', {
      params: {
        q: query,  // Server expects 'q' parameter
        type: searchType,
        limit
      }
    });
    
    // Extract data from success response structure
    const data = response.data.success ? response.data.data : response.data;
    return {
      results: data.data || [],
      total: data.pagination?.total || 0,
      query,
      search_type: searchType
    };
  },

  async findSimilar(clipId: string, limit: number = 5): Promise<SearchResults> {
    // Backend /api/search/similar endpoint
    const response = await apiClient.get('/search/similar', {
      params: {
        clip_id: clipId,
        limit
      }
    });
    
    // Extract data from success response structure
    const data = response.data.success ? response.data.data : response.data;
    return {
      results: data.data || [],
      total: data.pagination?.total || 0,
      search_type: 'similar'
    };
  }
};

// Videos API (New)
export const videosApi = {
  async list(options?: ListVideoOptions): Promise<SearchResults> {
    const params: Record<string, any> = {};
    if (options?.sortBy) params.sort_by = options.sortBy;
    if (options?.sortOrder) params.sort_order = options.sortOrder;
    if (options?.limit) params.limit = options.limit;
    if (options?.offset) params.offset = options.offset;

    // Use /clips endpoint for listing all videos
    const response = await apiClient.get('/clips', { params });
    
    // Extract data from success response structure
    const data = response.data.success ? response.data.data : response.data;
    return {
      results: data.data || [],
      total: data.pagination?.total || 0
    };
  }
};

// Health check
export const healthApi = {
  async check() {
    try {
      const response = await apiClient.get('/health');
      return { connected: true, data: response.data };
    } catch (error) {
      return { connected: false, error };
    }
  }
};

// Clips API
export const clipsApi = {
  async getDetails(clipId: string): Promise<VideoDetails> {
    const response = await apiClient.get(`/clips/${clipId}`, {
      params: {
        include: 'transcript,analysis'  // Get full details
      }
    });
    
    // Extract data from success response structure
    const data = response.data.success ? response.data.data : response.data;
    return {
      clip: data,
      transcript: data.transcript || null,
      analysis: data.analysis || null
    };
  }
};

// Stats API - Not available in current server, provide placeholder
export const statsApi = {
  async getCatalogStats(): Promise<CatalogStats> {
    // This endpoint doesn't exist in current server, return placeholder
    return {
      total_videos: 0,
      total_duration_seconds: 0,
      total_file_size_bytes: 0
    };
  }
};

// Pipeline API
export const pipelineApi = {
  async getSteps(): Promise<PipelineStep[]> {
    const response = await apiClient.get('/pipeline/steps');
    
    // Extract data from success response structure
    const data = response.data.success ? response.data.data : response.data;
    return data.steps || [];
  }
};

// Connection status management
export const connectionManager = {
  /**
   * Add a listener for connection status changes
   * @param listener Function to call when connection status changes
   */
  addConnectionListener(listener: ConnectionListener) {
    connectionListeners.push(listener);
    // Immediately notify with current status
    listener(isConnected);
  },

  /**
   * Remove a connection listener
   * @param listener The listener to remove
   */
  removeConnectionListener(listener: ConnectionListener) {
    const index = connectionListeners.indexOf(listener);
    if (index !== -1) {
      connectionListeners.splice(index, 1);
    }
  },

  /**
   * Get current connection status
   * @returns Whether the API is currently connected
   */
  isConnected() {
    return isConnected;
  },

  /**
   * Sets the callback function to be invoked when a 401 auth error occurs.
   * @param callback The function to call on auth error, or null to clear.
   * @deprecated Authentication has been disabled
   */
  setAuthErrorCallback(callback: (() => void) | null) {
    authErrorCallback = callback;
  },

  /**
   * Triggers the registered auth error callback.
   * @deprecated Authentication has been disabled
   */
  triggerAuthError() {
    if (authErrorCallback) {
      authErrorCallback();
    }
  },

  /**
   * Check connection to the API server
   * @returns Promise resolving to connection status
   */
  async checkConnection() {
    try {
      await healthApi.check();
      if (!isConnected) {
        isConnected = true;
        notifyConnectionListeners(true);
      }
      return true;
    } catch (error) {
      if (isConnected) {
        isConnected = false;
        notifyConnectionListeners(false);
      }
      return false;
    }
  }
};

export default apiClient;
