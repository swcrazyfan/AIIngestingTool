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

// API configuration - connects to the new API server (api_server_new.py)
const API_BASE_URL = 'http://localhost:8000/api';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true
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
    // If we get a 401 on a protected endpoint, notify listeners
    else if (error.response?.status === 401) {
      // Don't trigger for auth endpoints
      const url = error.config?.url || '';
      if (!url.includes('/auth/')) {
        notifyConnectionListeners(true); // We're connected but need to re-authenticate
      }
    }
    return Promise.reject(error);
  }
);

// Function to notify all connection listeners
function notifyConnectionListeners(connected: boolean) {
  connectionListeners.forEach(listener => listener(connected));
}

// Auth API
export const authApi = {
  async login(email: string, password: string) {
    const response = await apiClient.post('/auth/login', { email, password });
    return response.data;
  },

  async signup(email: string, password: string) {
    const response = await apiClient.post('/auth/signup', { email, password });
    return response.data;
  },

  async logout() {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  },

  async getStatus() {
    const response = await apiClient.get('/auth/status');
    return response.data;
  }
};

// Ingest API
export const ingestApi = {
  async startIngest(directory: string, options: IngestOptions) {
    const response = await apiClient.post('/ingest', {
      directory,
      ...options
    });
    return response.data;
  },

  async getProgress() {
    const response = await apiClient.get('/ingest/progress');
    return response.data;
  },

  async getResults() {
    const response = await apiClient.get('/ingest/results');
    return response.data;
  }
};

// Search API
export const searchApi = {
  async search(query: string, searchType: SearchType = 'hybrid', limit: number = 20): Promise<SearchResults> {
    // For similar search, this shouldn't be called directly from generic search UI
    if (searchType === 'similar') {
      // UI should ideally use findSimilar directly
      console.warn('Attempted to use general search for similar items. Use findSimilar instead.');
      return { results: [], total: 0, query, search_type: searchType }; 
    }
    
    if (!query.trim()) {
      // Keyword search requires a query. Return empty if query is blank.
      // UI should guide user to use video listing for browsing all videos.
      console.warn('Search query is empty. Returning empty results for keyword search.');
      return { results: [], total: 0, query, search_type: searchType };
    }
    
    // Backend /api/search is now GET
    const response = await apiClient.get<SearchResults>('/search', {
      params: {
        query,
        type: searchType,
        limit
      }
    });
    return response.data;
  },

  async findSimilar(clipId: string, limit: number = 5): Promise<SearchResults> {
    // Backend /api/similar is now GET
    const response = await apiClient.get<SearchResults>('/similar', {
      params: {
        clip_id: clipId,
        limit
      }
    });
    return response.data;
  }
};

// Videos API (New)
export const videosApi = {
  async list(options?: ListVideoOptions): Promise<SearchResults> { // Assuming SearchResults can represent a list of videos
    const params: Record<string, any> = {};
    if (options?.sortBy) params.sort_by = options.sortBy;
    if (options?.sortOrder) params.sort_order = options.sortOrder;
    if (options?.limit) params.limit = options.limit;
    if (options?.offset) params.offset = options.offset;
    if (options?.dateStart) params.date_start = options.dateStart;
    if (options?.dateEnd) params.date_end = options.dateEnd;

    const response = await apiClient.get<SearchResults>('/videos', { params });
    return response.data;
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
    const response = await apiClient.get<VideoDetails>(`/clips/${clipId}`);
    return response.data;
  }
};

// Stats API
export const statsApi = {
  async getCatalogStats(): Promise<CatalogStats> {
    const response = await apiClient.get<CatalogStats>('/stats');
    return response.data;
  }
};

// Pipeline API
export const pipelineApi = {
  async getSteps(): Promise<PipelineStep[]> {
    const response = await apiClient.get<PipelineStep[]>('/pipeline/steps');
    return response.data;
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
