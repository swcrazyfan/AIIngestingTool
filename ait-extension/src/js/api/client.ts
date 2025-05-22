import axios, { AxiosInstance } from 'axios';
import { 
  IngestOptions, 
  SearchType, 
  VideoFile, 
  IngestProgress, 
  AuthStatus,
  SearchResults,
  ApiResponse 
} from '../types/api';

// API configuration
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
  async search(query: string, searchType: SearchType = 'hybrid', limit: number = 20) {
    // For similar search, this shouldn't be called directly
    if (searchType === 'similar') {
      throw new Error('Use findSimilar method for similar searches');
    }
    
    const response = await apiClient.post('/search', {
      query,
      search_type: searchType,
      limit
    });
    return response.data;
  },

  async findSimilar(clipId: string, limit: number = 5) {
    // The backend expects a different endpoint or handling for similar searches
    // Based on the Python code, it seems we need to call a separate method
    // Let's check if the API server has a similar endpoint
    const response = await apiClient.post('/search/similar', {
      clip_id: clipId,
      limit
    });
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
  async getDetails(clipId: string) {
    const response = await apiClient.get(`/clips/${clipId}`);
    return response.data;
  }
};

// Stats API
export const statsApi = {
  async getCatalogStats() {
    const response = await apiClient.get('/stats');
    return response.data;
  }
};

// Pipeline API
export const pipelineApi = {
  async getSteps() {
    const response = await apiClient.get('/pipeline/steps');
    return response.data;
  }
};

export default apiClient;
