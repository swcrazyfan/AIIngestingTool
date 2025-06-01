import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios';
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

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

// Connection status event handling
type ConnectionListener = (isConnected: boolean) => void;
const connectionListeners: ConnectionListener[] = [];
let isConnected = true;

// Global variables for dynamic configuration
let currentApiPort: number = 8001; // Default fallback - updated to match current server
let currentBaseUrl: string = 'http://localhost:8001/api'; // Default fallback - updated to match current server
let portConfigLoaded: boolean = false;

// Function to get API port from configuration
function getApiPort(): number {
  try {
    // Use the CLI to get current port configuration
    const { execSync } = require('child_process');
    
    // Try to execute the CLI ports command using conda run
    const projectRoot = '/Users/developer/Development/GitHub/AIIngestingTool';
    const cliCommand = `cd "${projectRoot}" && conda run -n video-ingest python -m video_ingest_tool.cli ports --format json`;
    
    console.log('Executing CLI command to get ports...');
    const output = execSync(cliCommand, { 
      encoding: 'utf8',
      timeout: 15000, // 15 second timeout
      stdio: ['ignore', 'pipe', 'ignore'] // Ignore stderr to avoid conda warnings
    });
    
    // The CLI should output JSON with port configuration
    const config = JSON.parse(output.trim());
    console.log('Found port configuration from CLI:', config);
    
    // Look for API port in the configuration
    if (config.api_port) {
      console.log(`Using API port from CLI: ${config.api_port}`);
      return config.api_port;
    }
    
  } catch (error: any) {
    console.warn('Could not get port configuration from CLI:', error.message);
    
    // Fallback: try to read the config file directly
    try {
      const fs = require('fs');
      const configPath = '/Users/developer/Development/GitHub/AIIngestingTool/config/ports.json';
      
      if (fs.existsSync(configPath)) {
        console.log('Falling back to config file...');
        const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        console.log('Port configuration from file:', config);
        return config.api_port;
      }
    } catch (fileError: any) {
      console.warn('Could not read port configuration file:', fileError);
    }
  }
  
  // Final fallback to environment variable or default
  const envPort = process.env.API_PORT;
  if (envPort) {
    console.log(`Using API_PORT environment variable: ${envPort}`);
    return parseInt(envPort, 10);
  }
  
  // Ultimate fallback
  console.log('Using fallback port: 8001');
  return 8001;
}

// Function to refresh port configuration (call on page load)
function refreshPortConfiguration(): void {
  try {
    console.log('🔄 Refreshing port configuration...');
    const detectedPort = getApiPort();
    
    // Only update if we got a different port
    if (detectedPort !== currentApiPort) {
      console.log(`📡 Port changed from ${currentApiPort} to ${detectedPort}`);
      currentApiPort = detectedPort;
      currentBaseUrl = `http://localhost:${currentApiPort}/api`;
      
      // Update the axios instance
      apiClient.defaults.baseURL = currentBaseUrl;
      console.log(`🔧 Updated API client base URL to: ${currentBaseUrl}`);
    } else {
      console.log(`✅ Port configuration unchanged: ${currentApiPort}`);
    }
    
    portConfigLoaded = true;
  } catch (error: any) {
    console.error('❌ Failed to refresh port configuration:', error.message);
    // Keep using the current configuration
  }
}

// Function to ensure port configuration is loaded
function ensurePortConfiguration(): void {
  if (!portConfigLoaded) {
    refreshPortConfiguration();
  }
}

// Get the initial API port but make it dynamic
function getBaseUrl(): string {
  ensurePortConfiguration();
  return currentBaseUrl;
}

// Create axios instance with dynamic config
const apiClient: AxiosInstance = axios.create({
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false // No authentication required
});

// Interceptor to ensure we always use the current base URL
apiClient.interceptors.request.use((config) => {
  // Update base URL before each request
  config.baseURL = getBaseUrl();
  return config;
});

console.log(`🚀 API client initialized with dynamic port detection`);

// Initialize port configuration immediately
refreshPortConfiguration();

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
    return Promise.reject(error);
  }
);

// Function to notify all connection listeners
function notifyConnectionListeners(connected: boolean) {
  connectionListeners.forEach(listener => listener(connected));
}

// Auth API - REMOVED: Authentication has been completely disabled
export const authApi = {
  async login(email: string, password: string) {
    // Return success since auth is disabled - using local DuckDB
    return { 
      success: true, 
      data: { 
        authenticated: true, 
        user: { 
          id: "user", 
          email: "user", 
          profile_type: "local" 
        } 
      },
      message: "Authentication disabled" 
    };
  },

  async signup(email: string, password: string) {
    // Return success since auth is disabled
    return { 
      success: true, 
      data: { 
        authenticated: true, 
        user: { 
          id: "user", 
          email: "user", 
          profile_type: "local" 
        } 
      },
      message: "Authentication disabled" 
    };
  },

  async logout() {
    // Return success since auth is disabled
    return { 
      success: true, 
      message: "Authentication disabled" 
    };
  },

  async getStatus() {
    // Return authenticated status since auth is disabled
    return { 
      success: true, 
      data: { 
        authenticated: true, 
        user: { 
          id: "user", 
          email: "user", 
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
        ai_analysis: options.ai_analysis ?? false,
        store_database: options.store_database ?? false,
        generate_embeddings: options.generate_embeddings ?? false,
        force_reprocess: options.force_reprocess ?? false,
        // Optional compression settings if provided
        compression_fps: 30,
        compression_bitrate: '1000k'
      };
      
      console.log('Starting ingest with params:', requestData);
      const response = await apiClient.post('/ingest', requestData);
      
      // Server returns standardized response format
      if (response.data.success) {
        return response.data;
      } else {
        throw new Error(response.data.error || 'Failed to start ingest');
      }
    } catch (error: any) {
      console.error('Error starting ingest:', error);
      if (error.response && error.response.data) {
        console.error('Server error details:', error.response.data);
        const message = error.response.data.error || 'Failed to start ingest (server error)';
        throw new Error(message);
      }
      throw new Error(error.message || 'Failed to start ingest process (network error)');
    }
  },

  async getProgress(taskRunId?: string) {
    try {
      if (taskRunId) {
        // Get specific task progress
        const response = await apiClient.get(`/progress/${taskRunId}`);
        return response.data;
      } else {
        // Get overall progress
        const response = await apiClient.get('/progress');
        return response.data;
      }
    } catch (error: any) {
      console.error('Error getting progress:', error);
      throw error;
    }
  }
};

// Search API
export const searchApi = {
  async search(query: string, searchType: SearchType = 'hybrid', limit: number = 20): Promise<SearchResults> {
    // For similar search, this shouldn't be called directly
    if (searchType === 'similar') {
      console.warn('Use findSimilar() instead for similar search');
      return { results: [], total: 0, query, search_type: searchType }; 
    }
    
    if (!query.trim()) {
      console.warn('Search query is empty');
      return { results: [], total: 0, query, search_type: searchType };
    }
    
    try {
      // Backend /api/search endpoint
      const response = await apiClient.get('/search', {
        params: {
          q: query,  // Server expects 'q' parameter
          type: searchType,
          limit
        }
      });
      
      // Extract data from standardized success response
      if (response.data.success) {
        const data = response.data.data;
        return {
          results: data.data || [],
          total: data.pagination?.total || data.match_count || 0,
          query: data.query || query,
          search_type: data.search_type || searchType
        };
      } else {
        throw new Error(response.data.error || 'Search failed');
      }
    } catch (error: any) {
      console.error('Search error:', error);
      throw error;
    }
  },

  async findSimilar(clipId: string, limit: number = 5): Promise<SearchResults> {
    try {
      // Backend /api/search/similar endpoint
      const response = await apiClient.get('/search/similar', {
        params: {
          clip_id: clipId,
          limit
        }
      });
      
      // Extract data from standardized success response
      if (response.data.success) {
        const data = response.data.data;
        return {
          results: data.data || [],
          total: data.pagination?.total || data.match_count || 0,
          search_type: 'similar'
        };
      } else {
        throw new Error(response.data.error || 'Similar search failed');
      }
    } catch (error: any) {
      console.error('Similar search error:', error);
      throw error;
    }
  }
};

// Videos API
export const videosApi = {
  async list(options?: ListVideoOptions): Promise<SearchResults> {
    try {
      const params: Record<string, any> = {};
      
      // Map sort parameters
      if (options?.sortBy) {
        // Map frontend field names to backend field names
        const sortByMap: Record<string, string> = {
          'processed_at': 'processed_at',
          'file_name': 'file_name',
          'duration_seconds': 'duration_seconds',
          'created_at': 'created_at'
        };
        params.sort_by = sortByMap[options.sortBy] || options.sortBy;
      }
      
      if (options?.sortOrder) {
        // Map frontend order to backend order
        const orderMap: Record<string, string> = {
          'ascending': 'asc',
          'descending': 'desc'
        };
        params.sort_order = orderMap[options.sortOrder] || options.sortOrder;
      }
      
      if (options?.limit) params.limit = options.limit;
      if (options?.offset) params.offset = options.offset;

      // Use /clips endpoint for listing all videos
      const response = await apiClient.get('/clips', { params });
      
      // Extract data from standardized success response
      if (response.data.success) {
        const data = response.data.data;
        return {
          results: data.data || [],
          total: data.pagination?.total || 0
        };
      } else {
        throw new Error(response.data.error || 'Failed to list videos');
      }
    } catch (error: any) {
      console.error('List videos error:', error);
      throw error;
    }
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
    try {
      const response = await apiClient.get(`/clips/${clipId}`, {
        params: {
          include: 'transcript,analysis'  // Get full details
        }
      });
      
      // Extract data from standardized success response
      if (response.data.success) {
        const data = response.data.data;
        return {
          clip: data,
          transcript: data.transcript || null,
          analysis: data.analysis || null
        };
      } else {
        throw new Error(response.data.error || 'Failed to get clip details');
      }
    } catch (error: any) {
      console.error('Get clip details error:', error);
      throw error;
    }
  }
};

// Stats API - Not available in current server
export const statsApi = {
  async getCatalogStats(): Promise<CatalogStats> {
    // This endpoint doesn't exist in current server, return placeholder
    console.warn('Stats endpoint not available in current server');
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
    try {
      const response = await apiClient.get('/pipeline/steps');
      
      // Extract data from standardized success response
      if (response.data.success) {
        const data = response.data.data;
        return data.steps || [];
      } else {
        throw new Error(response.data.error || 'Failed to get pipeline steps');
      }
    } catch (error: any) {
      console.error('Get pipeline steps error:', error);
      return []; // Return empty array on error
    }
  }
};

// Export connection management functions
export const connectionApi = {
  addConnectionListener(listener: ConnectionListener) {
    connectionListeners.push(listener);
  },

  removeConnectionListener(listener: ConnectionListener) {
    const index = connectionListeners.indexOf(listener);
    if (index > -1) {
      connectionListeners.splice(index, 1);
    }
  },

  isConnected() {
    return isConnected;
  },

  async checkConnection() {
    try {
      await apiClient.get('/health');
      return true;
    } catch {
      return false;
    }
  },

  // New function to refresh port configuration
  refreshPortConfiguration() {
    return refreshPortConfiguration();
  },

  // Get current configuration info  
  getCurrentConfig() {
    return {
      port: currentApiPort,
      baseUrl: currentBaseUrl,
      loaded: portConfigLoaded
    };
  }
};

export default apiClient;
