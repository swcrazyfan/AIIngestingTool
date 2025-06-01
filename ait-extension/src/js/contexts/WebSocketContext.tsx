import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { connectionApi } from '../api/client';

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  progress: any;
  results: any[];
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

    // Progress and result handlers
    newSocket.on('progress_update', (data) => {
      console.log('Progress update received:', data);
      setProgress(data);
    });

    newSocket.on('ingest_results', (data) => {
      console.log('Ingest results received:', data);
      setResults(prev => [...prev, data]);
    });

    setSocket(newSocket);

    return () => {
      console.log('Cleaning up WebSocket connection');
      newSocket.disconnect();
    };
  }, []); // Remove auth dependency

  const value = {
    socket,
    isConnected,
    progress,
    results
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
