import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { IngestProgress, VideoFile, SearchResults } from '../types/api';

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
  
  // Map to track pending requests
  const pendingRequests = useRef<Map<RequestId, PendingRequest>>(new Map());
  
  // Generate a unique request ID
  const generateRequestId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
  };

  const setupSocket = () => {
    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.disconnect();
    }

    console.log('Setting up WebSocket connection to new API server...');
    
    // Create new socket connection
    const newSocket = io('http://localhost:8000', {
      transports: ['websocket', 'polling'],  // Try WebSocket first, fall back to polling
      reconnectionAttempts: 15,              // Increased for better reliability
      reconnectionDelay: 1000,
      timeout: 8000,                         // Increased timeout for better reliability
      forceNew: true,                        // Force a new connection
      autoConnect: true                      // Automatically connect
    });
    
    socketRef.current = newSocket;
    setSocket(newSocket);

    // Set up event listeners
    newSocket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
      
      // Reject all pending requests on disconnect
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

    // Listen for ingest progress updates
    newSocket.on('ingest_progress', (data) => {
      console.log('Received ingest progress update:', data);
      setIngestProgress(data);
    });
    
    // Handle ping response to confirm connection is healthy
    newSocket.on('pong', () => {
      console.debug('Received pong from server');
    });
    
    // Generic response handler
    newSocket.on('response', (data) => {
      const { requestId, result, error } = data;
      
      if (requestId && pendingRequests.current.has(requestId)) {
        const request = pendingRequests.current.get(requestId)!;
        clearTimeout(request.timeout);
        
        if (error) {
          request.reject(new Error(error));
        } else {
          request.resolve(result);
        }
        
        pendingRequests.current.delete(requestId);
      }
    });
    
    // Specific event handlers
    newSocket.on('search_results', (data) => {
      console.log('Received search results:', data);
      // This will be handled by the search method's promise
    });

    return newSocket;
  };

  // Initialize socket on component mount
  useEffect(() => {
    const socket = setupSocket();
    
    // Set up a heartbeat interval to detect stale connections
    const heartbeatInterval = setInterval(() => {
      if (socketRef.current && connected) {
        // Ping the server to keep the connection alive
        socketRef.current.emit('ping');
      }
    }, 30000); // Every 30 seconds
    
    // Cleanup on unmount
    return () => {
      console.log('Cleaning up WebSocket connection');
      clearInterval(heartbeatInterval);
      if (socket) {
        socket.disconnect();
      }
    };
  }, []);

  // Generic request sender with timeout
  const sendRequest = useCallback(<T,>(eventName: string, data: any, timeoutMs: number = 10000): Promise<T> => {
    return new Promise((resolve, reject) => {
      if (!socketRef.current || !connected) {
        console.warn(`WebSocket not connected, cannot send ${eventName} request`);
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
      
      socketRef.current.emit(eventName, { ...data, requestId });
    });
  }, [connected]);
  
  // Search API with fallback to HTTP
  const search = useCallback(async (params: SearchParams): Promise<SearchResults> => {
    try {
      // Try WebSocket first
      if (connected && socketRef.current) {
        return await sendRequest<SearchResults>('search_request', params);
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket search failed, falling back to HTTP API:', error);
      // Fall back to HTTP API
      const { searchApi } = await import('../api/client');
      return searchApi.search(params.query, params.search_type as any, params.limit);
    }
  }, [connected, sendRequest]);
  
  // Start ingest API with fallback to HTTP
  const startIngest = useCallback(async (params: IngestParams): Promise<any> => {
    try {
      // Try WebSocket first
      if (connected && socketRef.current) {
        return await sendRequest<any>('start_ingest', params);
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket startIngest failed, falling back to HTTP API:', error);
      // Fall back to HTTP API
      const { ingestApi } = await import('../api/client');
      return ingestApi.startIngest(params.directory, params.options || {});
    }
  }, [connected, sendRequest]);
  
  // Get ingest progress API with fallback to HTTP
  const getIngestProgress = useCallback(async (): Promise<IngestProgress> => {
    try {
      // Try WebSocket first
      if (connected && socketRef.current) {
        return await sendRequest<IngestProgress>('get_ingest_progress', {});
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getIngestProgress failed, falling back to HTTP API:', error);
      // Fall back to HTTP API
      const { ingestApi } = await import('../api/client');
      return ingestApi.getProgress();
    }
  }, [connected, sendRequest]);
  
  // Get video details API with fallback to HTTP
  const getVideoDetails = useCallback(async (id: string): Promise<VideoFile> => {
    try {
      // Try WebSocket first
      if (connected && socketRef.current) {
        return await sendRequest<VideoFile>('get_video_details', { clipId: id });
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getVideoDetails failed, falling back to HTTP API:', error);
      // Fall back to HTTP API
      const { clipsApi } = await import('../api/client');
      return clipsApi.getDetails(id);
    }
  }, [connected, sendRequest]);
  
  // Get similar videos API with fallback to HTTP
  const getSimilarVideos = useCallback(async (id: string, limit: number = 5): Promise<VideoFile[]> => {
    try {
      // Try WebSocket first
      if (connected && socketRef.current) {
        const result = await sendRequest<any>('get_similar_videos', { clipId: id, limit });
        return result.results || [];
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.warn('WebSocket getSimilarVideos failed, falling back to HTTP API:', error);
      // Fall back to HTTP API
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
