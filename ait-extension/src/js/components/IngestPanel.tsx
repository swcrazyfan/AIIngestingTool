import React, { useState, useEffect } from 'react';
import { ingestApi } from '../api/client';
import { IngestProgress } from '../types/api';
import { evalTS } from '../lib/utils/bolt';
import { FiFolder, FiPlay, FiCheckSquare, FiSquare, FiRefreshCw } from 'react-icons/fi';
import { useWebSocket } from '../contexts/WebSocketContext';
import '../styles/IngestPanel.scss';

const IngestPanel: React.FC = () => {
  const [selectedDirectory, setSelectedDirectory] = useState('');
  const [ingestOptions, setIngestOptions] = useState({
    recursive: true,
    ai_analysis: true,
    generate_embeddings: true,
    store_database: true, // Always true by default, no UI control
    force_reprocess: false
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState<boolean>(false);
  
  // Use the global WebSocket connection
  const { ingestProgress, connected } = useWebSocket();

  const selectDirectory = async () => {
    try {
      const directory = await evalTS("selectDirectory");
      if (directory) {
        setSelectedDirectory(directory);
      }
    } catch (error) {
      console.error('Failed to select directory:', error);
    }
  };

  const startIngest = async () => {
    if (!selectedDirectory) return;
    
    setIsLoading(true);
    try {
      await ingestApi.startIngest(selectedDirectory, ingestOptions);
      
      // Show progress section
      setShowProgress(true);
      setError(null);
    } catch (error) {
      console.error('Ingest failed:', error);
      setError('Failed to start ingest process');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleOption = (option: keyof typeof ingestOptions) => {
    setIngestOptions(prev => ({
      ...prev,
      [option]: !prev[option]
    }));
  };

  // Check for ongoing ingest process on load
  useEffect(() => {
    const checkIngestProgress = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // Only make an API call if WebSocket is not connected yet
        if (!connected) {
          const progressData = await ingestApi.getProgress();
          
          // If there's an active ingest process
          if (progressData && (progressData.status === 'running' || 
                              progressData.status === 'scanning' || 
                              progressData.status === 'processing')) {
            setShowProgress(true);
          }
        }
      } catch (error) {
        console.error('Failed to check ingest status:', error);
        setError('Failed to check ingest status');
      } finally {
        setIsLoading(false);
      }
    };
    
    checkIngestProgress();
  }, [connected]);
  
  // Update UI based on ingest progress from WebSocket
  useEffect(() => {
    if (ingestProgress) {
      // Show progress section if there's an active process
      if (ingestProgress.status === 'running' || 
          ingestProgress.status === 'scanning' || 
          ingestProgress.status === 'processing') {
        setShowProgress(true);
      }
      
      // Hide progress after a delay when process is idle
      if (ingestProgress.status === 'idle') {
        setTimeout(() => {
          setShowProgress(false);
        }, 3000);
      }
    }
  }, [ingestProgress]);

  return (
    <div className="ingest-panel">
      <h2>Video Ingest</h2>
      
      {isLoading ? (
        <div className="loading-state">
          <FiRefreshCw className="loading-icon" />
          <p>Checking ingest status...</p>
        </div>
      ) : error ? (
        <div className="error-state">
          <p className="error-message">{error}</p>
          <button onClick={() => {
            setIsLoading(true);
            setError(null);
            // Try to get the latest progress
            ingestApi.getProgress().then(() => {
              setIsLoading(false);
            }).catch(() => {
              setIsLoading(false);
              setError('Failed to connect to server');
            });
          }}>Retry</button>
        </div>
      ) : ingestProgress && (ingestProgress.status === 'running' || 
            ingestProgress.status === 'scanning' || 
            ingestProgress.status === 'processing') ? (
        <div className="ingest-in-progress">
          <h3>Video Processing in Progress</h3>
          {error && <div className="error-message">{error}</div>}
        </div>
      ) : (
        // Show ingest form when not ingesting
        <>
          <div className="directory-selection">
            <button onClick={selectDirectory} className="select-directory-btn">
              <FiFolder /> Select Directory
            </button>
            
            {selectedDirectory && (
              <div className="selected-path">{selectedDirectory}</div>
            )}
          </div>

          <div className="ingest-options">
            <h3>Processing Options</h3>
            
            <label className="option-item">
              <button onClick={() => toggleOption('recursive')} className="checkbox">
                {ingestOptions.recursive ? <FiCheckSquare /> : <FiSquare />}
              </button>
              <div className="option-content">
                <span className="option-label">Recursive Scan</span>
                <span className="option-desc">Include subdirectories</span>
              </div>
            </label>

            <label className="option-item">
              <button onClick={() => toggleOption('ai_analysis')} className="checkbox">
                {ingestOptions.ai_analysis ? <FiCheckSquare /> : <FiSquare />}
              </button>
              <div className="option-content">
                <span className="option-label">AI Analysis</span>
                <span className="option-desc">Comprehensive video analysis</span>
              </div>
            </label>

            <label className="option-item">
              <button onClick={() => toggleOption('generate_embeddings')} className="checkbox">
                {ingestOptions.generate_embeddings ? <FiCheckSquare /> : <FiSquare />}
              </button>
              <div className="option-content">
                <span className="option-label">Generate Embeddings</span>
                <span className="option-desc">Enable semantic search</span>
              </div>
            </label>

            <label className="option-item">
              <button onClick={() => toggleOption('force_reprocess')} className="checkbox">
                {ingestOptions.force_reprocess ? <FiCheckSquare /> : <FiSquare />}
              </button>
              <div className="option-content">
                <span className="option-label">Re-ingest existing files</span>
                <span className="option-desc">Process files even if they've been ingested before</span>
              </div>
            </label>
          </div>

          <button 
            onClick={startIngest} 
            className="start-ingest-btn"
            disabled={!selectedDirectory}
          >
            <FiPlay /> Start Processing
          </button>
          {error && <div className="error-message">{error}</div>}
        </>
      )}

      {ingestProgress && showProgress && (
        <div className="ingest-progress-container">
          <h3>Ingest Progress</h3>
          <div className="progress-bar-container">
            <div className="progress-bar-background">
              <div 
                className={`progress-bar-fill ${ingestProgress?.status === 'failed' ? 'failed' : ''}`}
                style={{ width: `${ingestProgress?.progress || 0}%` }}
              />
            </div>
            <span className="progress-percentage">{ingestProgress?.progress || 0}%</span>
          </div>
          <p><strong>Status:</strong> {ingestProgress?.status}</p>
          <p><strong>Message:</strong> {ingestProgress?.message}</p>
          {ingestProgress?.processed_count !== undefined && (
            <p><strong>Processed:</strong> {ingestProgress.processed_count} files</p>
          )}
          {ingestProgress?.failed_count !== undefined && (
            <p><strong>Failed:</strong> {ingestProgress.failed_count} files</p>
          )}
        </div>
      )}
    </div>
  );
};

export default IngestPanel;
