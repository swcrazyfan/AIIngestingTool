import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { connectionApi } from '../api/client';

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  progress: any;
  results: any[];
  subscribeToProgress: (taskRunId?: string) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: ReactNode;
}

// Sanitize progress data to prevent React crashes
function sanitizeProgressData(data: any): any {
  if (!data || typeof data !== 'object') {
    console.warn('Invalid progress data received:', data);
    return null;
  }

  try {
    console.log('Sanitizing progress data:', JSON.stringify(data, null, 2)); // Debug log
    
    // Ensure basic required fields exist
    const sanitized = {
      status: data.status || 'unknown',
      progress: typeof data.progress === 'number' ? data.progress : 0,
      message: data.message || '',
      current_file: data.current_file || '',
      error: data.error || null,
      processed_count: typeof data.processed_count === 'number' ? data.processed_count : 0,
      failed_count: typeof data.failed_count === 'number' ? data.failed_count : 0,
      total_count: typeof data.total_count === 'number' ? data.total_count : 0,
      processed_files: Array.isArray(data.processed_files) ? data.processed_files.map(sanitizeFileData) : []
    };

    console.log('Sanitized progress data:', JSON.stringify(sanitized, null, 2)); // Debug log
    return sanitized;
  } catch (error) {
    console.error('Error sanitizing progress data:', error);
    console.error('Raw data:', data);
    return null;
  }
}

// Sanitize individual file data
function sanitizeFileData(file: any): any {
  try {
    if (!file || typeof file !== 'object') {
      console.warn('Invalid file data received:', file);
      return {
        file_name: 'Unknown file',
        status: 'unknown',
        progress_percentage: 0,
        current_step: '',
        error: null
      };
    }

    const sanitized = {
      file_name: file.file_name || file.path || 'Unknown file',
      path: file.path || '',
      status: file.status || 'unknown',
      progress_percentage: typeof file.progress_percentage === 'number' ? file.progress_percentage : 0,
      current_step: file.current_step || '',
      error: file.error || null,
      // Compression details with safe defaults
      compression_total_frames: typeof file.compression_total_frames === 'number' ? file.compression_total_frames : null,
      compression_processed_frames: typeof file.compression_processed_frames === 'number' ? file.compression_processed_frames : null,
      compression_current_rate: typeof file.compression_current_rate === 'number' ? file.compression_current_rate : null,
      compression_etr_seconds: typeof file.compression_etr_seconds === 'number' ? file.compression_etr_seconds : null,
      compression_speed: file.compression_speed || null,
      compression_error_detail: file.compression_error_detail || null
    };
    
    return sanitized;
  } catch (error) {
    console.error('Error sanitizing file data:', error);
    console.error('Raw file data:', file);
    return {
      file_name: 'Error processing file data',
      status: 'error',
      progress_percentage: 0,
      current_step: '',
      error: 'Data processing error'
    };
  }
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState(null);
  const [results, setResults] = useState<any[]>([]);

  useEffect(() => {
    // Get the current API configuration to determine the correct port
    const config = connectionApi.getCurrentConfig();
    const port = config.port || 8001; // Fallback to 8001 to match current server
    
    console.log(`Initializing WebSocket connection to localhost:${port}`);
    
    const newSocket = io(`http://localhost:${port}`, {
      transports: ['websocket', 'polling'],
      upgrade: true,
      rememberUpgrade: true,
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      timeout: 10000,
    });

    // Connection event handlers
    newSocket.on('connect', () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    });

    newSocket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setIsConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
    });

    // Progress handlers - FIXED: Listen for correct event names from server
    newSocket.on('ingest_progress_update', (data) => {
      console.log('Ingest progress update received:', data);
      try {
        // Sanitize the progress data to prevent crashes
        const sanitizedProgress = sanitizeProgressData(data);
        
        // Only set progress if sanitization was successful
        if (sanitizedProgress !== null) {
          setProgress(sanitizedProgress);
        } else {
          console.warn('Failed to sanitize progress data, ignoring update');
        }
      } catch (error) {
        console.error('Error processing ingest progress update:', error);
        console.error('Raw data that caused error:', data);
        // Set a safe fallback instead of crashing
        setProgress({
          status: 'error',
          progress: 0,
          message: 'Error processing progress update',
          current_file: '',
          error: 'Data processing error',
          processed_count: 0,
          failed_count: 0,
          total_count: 0,
          processed_files: []
        } as any);
      }
    });
    
    // Also listen for generic progress updates
    newSocket.on('progress_update', (data) => {
      console.log('Progress update received:', data);
      try {
        // Sanitize the progress data to prevent crashes
        const sanitizedProgress = sanitizeProgressData(data);
        
        // Only set progress if sanitization was successful
        if (sanitizedProgress !== null) {
          setProgress(sanitizedProgress);
        } else {
          console.warn('Failed to sanitize progress data, ignoring update');
        }
      } catch (error) {
        console.error('Error processing progress update:', error);
        console.error('Raw data that caused error:', data);
        // Set a safe fallback instead of crashing
        setProgress({
          status: 'error',
          progress: 0,
          message: 'Error processing progress update',
          current_file: '',
          error: 'Data processing error',
          processed_count: 0,
          failed_count: 0,
          total_count: 0,
          processed_files: []
        } as any);
      }
    });

    // Result handlers
    newSocket.on('ingest_results', (data) => {
      console.log('Ingest results received:', data);
      setResults(prev => [...prev, data]);
    });

    // Subscription confirmations
    newSocket.on('progress_subscribed', (data) => {
      console.log('Progress subscription confirmed:', data);
    });

    newSocket.on('progress_error', (data) => {
      console.error('Progress subscription error:', data);
    });

    setSocket(newSocket);

    return () => {
      console.log('Cleaning up WebSocket connection');
      newSocket.disconnect();
    };
  }, []); // Remove auth dependency

  const subscribeToProgress = (taskRunId?: string) => {
    if (socket && isConnected) {
      console.log('Subscribing to progress updates', { taskRunId });
      socket.emit('subscribe_progress', { 
        task_run_id: taskRunId,
        requestId: `subscribe_${Date.now()}`
      });
    } else {
      console.warn('Cannot subscribe to progress: socket not connected');
    }
  };

  const value = {
    socket,
    isConnected,
    progress,
    results,
    subscribeToProgress
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
