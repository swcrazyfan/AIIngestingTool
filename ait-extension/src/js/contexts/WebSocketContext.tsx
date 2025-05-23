import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { IngestProgress, VideoFile, SearchResults } from '../types/api';
import { useAuth } from './AuthContext';

// Define request types
type RequestId = string;

interface SearchParams {
  query: string;
  search_type?: string;
  limit?: number;
  offset?: number;
}

interface IngestParams {
  directory: string;
  options?: {
    recursive?: boolean;
    ai_analysis?: boolean;
    generate_embeddings?: boolean;
    store_database?: boolean;
    force_reprocess?: boolean;
  };
}

interface PendingRequest {
  resolve: (value: any) => void;
  reject: (reason: any) => void;
  timeout: NodeJS.Timeout;
}

interface WebSocketContextType {
  socket: Socket | null;
  connected: boolean;
  ingestProgress: IngestProgress | null;
  reconnect: () => void;
  search: (params: SearchParams) => Promise<SearchResults>;
  startIngest: (params: IngestParams) => Promise<any>;
  getIngestProgress: () => Promise<IngestProgress>;
  getVideoDetails: (id: string) => Promise<VideoFile>;
  getSimilarVideos: (id: string, limit?: number) => Promise<VideoFile[]>;
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  connected: false,
  ingestProgress: null,
  reconnect: () => {},
  search: () => Promise.reject('WebSocketContext not initialized'),
  startIngest: () => Promise.reject('WebSocketContext not initialized'),
  getIngestProgress: () => Promise.reject('WebSocketContext not initialized'),
  getVideoDetails: () => Promise.reject('WebSocketContext not initialized'),
  getSimilarVideos: () => Promise.reject('WebSocketContext not initialized')
});

export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<IngestProgress | null>(null);
  const socketRef = useRef<Socket | null>(null);
  
  const { handleAuthError } = useAuth();

  // Map to track pending requests
  const pendingRequests = useRef<Map<RequestId, PendingRequest>>(new Map());
  
  // Generate a unique request ID
  const generateRequestId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
  };

  const setupSocket = useCallback(() => {
    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.disconnect();
    }

    console.log('Setting up WebSocket connection to new API server...');
    
    const newSocket = io('http://localhost:8000', {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 15,
      reconnectionDelay: 1000,
      timeout: 8000,
      forceNew: true,
      autoConnect: true
    });
    
    socketRef.current = newSocket;
    setSocket(newSocket);

    newSocket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
      
      pendingRequests.current.forEach((request, id) => {
        clearTimeout(request.timeout);
        request.reject(new Error('WebSocket disconnected'));
      });
      pendingRequests.current.clear();
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setConnected(false);
    });

    newSocket.on('ingest_progress', (data) => {
      console.log('Received ingest progress update:', data);
      setIngestProgress(data);
    });
    
    // Generic response handler
    newSocket.on('response', (data) => {
      const { requestId, payload } = data;
      const request = pendingRequests.current.get(requestId);
      if (request) {
        clearTimeout(request.timeout);
        request.resolve(payload);
        pendingRequests.current.delete(requestId);
      }
    });

    // Generic error handler for responses
    newSocket.on('response_error', (data) => {
      const { requestId, error: errorMsg } = data;
      if (typeof errorMsg === 'string' && (errorMsg.startsWith('Authentication required') || errorMsg.startsWith('Authentication error:'))) {
        console.warn('WebSocket authentication error:', errorMsg);
        handleAuthError();
      }

      const request = pendingRequests.current.get(requestId);
      if (request) {
        clearTimeout(request.timeout);
        request.reject(new Error(errorMsg || 'Unknown WebSocket error'));
        pendingRequests.current.delete(requestId);
      }
    });

    // Handle any other errors (e.g. server-side exceptions not caught by specific handlers)
    newSocket.on('error', (error) => {
      console.error('Generic WebSocket error:', error);
      if (typeof error.message === 'string' && (error.message.startsWith('Authentication required') || error.message.startsWith('Authentication error:'))) {
        console.warn('Generic WebSocket authentication error:', error.message);
        handleAuthError();
      }
    });

  }, [handleAuthError]);

  // Effect to setup and cleanup socket connection
  useEffect(() => {
    setupSocket();

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      pendingRequests.current.forEach(request => clearTimeout(request.timeout));
      pendingRequests.current.clear();
    };
  }, [setupSocket]);

  // Generic request sender with timeout
  const sendRequest = useCallback(async <T extends unknown>(event: string, payload: any, timeoutMs: number = 15000): Promise<T> => {
    return new Promise((resolve, reject) => {
      if (!socketRef.current || !connected) {
        console.warn(`WebSocket not connected, cannot send ${event} request`);
        reject(new Error('WebSocket not connected'));
        return;
      }
      
      const requestId = generateRequestId();
      const timeoutId = setTimeout(() => {
        if (pendingRequests.current.has(requestId)) {
          pendingRequests.current.delete(requestId);
          reject(new Error(`Request timeout after ${timeoutMs}ms`));
        }
      }, timeoutMs);
      
      pendingRequests.current.set(requestId, {
        resolve,
        reject,
        timeout: timeoutId
      });
      
      socketRef.current.emit(event, { ...payload, requestId });
    });
  }, [connected]);

  // Search API with fallback to HTTP
  const search = useCallback(async (params: SearchParams): Promise<SearchResults> => {
    try {
      if (connected && socketRef.current) {
        return await sendRequest<SearchResults>('search_request', params);
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket search failed, falling back to HTTP API:', error);
      const { searchApi } = await import('../api/client');
      return searchApi.search(params.query, params.search_type as any, params.limit);
    }
  }, [connected, sendRequest]);
  
  // Start ingest API with fallback to HTTP
  const startIngest = useCallback(async (params: IngestParams): Promise<any> => {
    try {
      if (connected && socketRef.current) {
        return await sendRequest<any>('start_ingest', params);
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket startIngest failed, falling back to HTTP API:', error);
      const { ingestApi } = await import('../api/client');
      return ingestApi.startIngest(params.directory, params.options || {});
    }
  }, [connected, sendRequest]);
  
  // Get ingest progress API with fallback to HTTP
  const getIngestProgress = useCallback(async (): Promise<IngestProgress> => {
    try {
      if (connected && socketRef.current) {
        return await sendRequest<IngestProgress>('get_ingest_progress', {});
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getIngestProgress failed, falling back to HTTP API:', error);
      const { ingestApi } = await import('../api/client');
      return ingestApi.getProgress();
    }
  }, [connected, sendRequest]);
  
  // Get video details API with fallback to HTTP
  const getVideoDetails = useCallback(async (id: string): Promise<VideoFile> => {
    try {
      if (connected && socketRef.current) {
        return await sendRequest<VideoFile>('get_video_details', { clipId: id });
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getVideoDetails failed, falling back to HTTP API:', error);
      const { clipsApi } = await import('../api/client');
      const videoDetails = await clipsApi.getDetails(id);
      if (!videoDetails || !videoDetails.clip) {
        throw new Error(`Failed to retrieve video details for ID: ${id} or clip data is missing.`);
      }
      return videoDetails.clip;
    }
  }, [connected, sendRequest]);
  
  // Get similar videos API with fallback to HTTP
  const getSimilarVideos = useCallback(async (id: string, limit: number = 5): Promise<VideoFile[]> => {
    try {
      if (connected && socketRef.current) {
        const result = await sendRequest<any>('get_similar_videos', { clipId: id, limit });
        return result.results || [];
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getSimilarVideos failed, falling back to HTTP API:', error);
      const { searchApi } = await import('../api/client');
      const result = await searchApi.findSimilar(id, limit);
      return result.results || [];
    }
  }, [connected, sendRequest]);
  
  // Function to manually reconnect
  const reconnect = useCallback(() => {
    console.log('Manually reconnecting WebSocket...');
    setupSocket();
  }, []);

  const value = {
    socket,
    connected,
    ingestProgress,
    reconnect,
    search,
    startIngest,
    getIngestProgress,
    getVideoDetails,
    getSimilarVideos
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
